"""Package-isolated working memory; never a replay authorization source."""

import uuid
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .evidence import (
    EvidenceContext,
    EvidenceStore,
    atomic_write,
    identifier,
    json_bytes,
    read_json,
    safe_path,
    store_lock,
    utc_now,
)
from .models import StrictModel, load_package


class MemoryEntry(StrictModel):
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    kind: Literal["knowledge", "progress", "failure", "hypothesis", "next_step"]
    status: Literal["hypothesis", "observed", "supported", "refuted"]
    text: str = Field(min_length=1, max_length=8000)
    source: str = Field(min_length=1, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=64)
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def evidence_required(self):
        if self.status != "hypothesis" and not self.evidence_refs:
            raise ValueError("observed/supported/refuted entries require evidence references")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("duplicate evidence references")
        return self


class MemoryDocument(StrictModel):
    schema_version: Literal[1] = 1
    context: EvidenceContext
    revision: int = Field(default=0, ge=0)
    entries: list[MemoryEntry] = Field(default_factory=list, max_length=1000)
    previous_entries: list[MemoryEntry] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def unique_entries(self):
        if len({entry.id for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate memory entry IDs")
        return self


class EventMemory:
    def __init__(self, project, event_id, game_version=None, resolution=None):
        self.project = Path(project).absolute()
        EvidenceContext(event_id=event_id)
        game, slug = event_id.split(".", 1)
        identifier(game)
        identifier(slug)
        self.package = safe_path(self.project, "event_packs", game, slug)
        manifest, digest = load_package(self.package)
        if manifest.id != event_id:
            raise ValueError("event identity differs from package path")
        self.root = safe_path(self.project, "data", "event_memory", game, slug)
        self.game_version_override = game_version
        self.resolution_override = resolution
        self.context = EvidenceContext(
            event_id=event_id, package_digest=digest,
            game_version=(manifest.compatibility.game_version if game_version is None
                          else game_version),
            resolution=(manifest.compatibility.resolution if resolution is None else resolution),
        ).model_dump()
        self.store = EvidenceStore(self.project)

    def path(self, digest=None):
        digest = digest or self.context["package_digest"]
        EvidenceContext(event_id=self.context["event_id"], package_digest=digest)
        return safe_path(self.root, digest, "memory.json")

    def _load(self, digest=None):
        path = self.path(digest)
        if not path.exists():
            if digest is not None and digest != self.context["package_digest"]:
                raise FileNotFoundError("historical memory not found")
            return MemoryDocument(context=EvidenceContext(**self.context))
        document = MemoryDocument.model_validate(read_json(path))
        if (document.context.event_id != self.context["event_id"]
                or document.context.package_digest != path.parent.name):
            raise ValueError("memory identity differs from storage namespace")
        return document

    def _check_refs(self, entry, context):
        for ref in entry.evidence_refs:
            frame, _, _ = self.store.frame(ref)
            if frame["context"]["event_id"] != context["event_id"]:
                raise ValueError("cross-activity or unidentified evidence")
            # Even a hypothesis must not silently attach another package's evidence.
            if frame["context"] != context or frame["size"] != context["resolution"]:
                raise ValueError("evidence context requires revalidation")
        if entry.status != "hypothesis" and context["game_version"] in {None, "unknown"}:
            raise ValueError("unknown game version cannot support a confirmed entry")

    def _current_context(self):
        manifest, digest = load_package(self.package)
        if manifest.id != self.context["event_id"]:
            raise ValueError("event identity changed; reopen memory")
        return EvidenceContext(
            event_id=manifest.id, package_digest=digest,
            game_version=(manifest.compatibility.game_version
                          if self.game_version_override is None else self.game_version_override),
            resolution=(manifest.compatibility.resolution
                        if self.resolution_override is None else self.resolution_override),
        ).model_dump()

    def show(self, digest=None):
        document = self._load(digest)
        context = document.context.model_dump()
        current_context = self._current_context()
        reasons = [f"{key}_changed" for key in current_context
                   if context[key] != current_context[key]]
        if context["game_version"] in {None, "unknown"}:
            reasons.append("unknown_game_version")
        errors = []
        for entry in document.entries:
            try:
                self._check_refs(entry, context)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                errors.append({"entry_id": entry.id, "error": str(exc)})
        if errors:
            reasons.append("evidence_unavailable_or_invalid")
        return {**document.model_dump(), "current_context": current_context,
                "applicability": "needs_review" if reasons else "context_matches",
                "review_reasons": reasons, "evidence_errors": errors,
                "available_digests": sorted(p.parent.name for p in self.root.glob("*/memory.json")),
                "replay_allowed": False, "fresh_observation_required": True}

    def change(self, payload, expected_revision, entry_id=None):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected revision must be a nonnegative integer")
        allowed = {"kind", "status", "text", "source", "evidence_refs"}
        if not isinstance(payload, dict):
            raise TypeError("memory payload must be an object")
        if not payload or set(payload) - allowed:
            raise ValueError("unsupported or empty memory update")
        with store_lock(self.root, "memory"):
            # Detect package edits made since constructing this object.
            manifest, digest = load_package(self.package)
            if digest != self.context["package_digest"] or manifest.id != self.context["event_id"]:
                raise ValueError("package changed; reopen memory before writing")
            document = self._load()
            if document.revision != expected_revision:
                raise ValueError(f"revision conflict: current revision is {document.revision}")
            if document.context.model_dump() != self.context:
                raise ValueError("memory compatibility changed; inspect old memory; no automatic merge")
            now = utc_now()
            if entry_id is None:
                entry = MemoryEntry.model_validate(
                    {"id": uuid.uuid4().hex, "created_at": now, "updated_at": now, **payload}
                )
                self._check_refs(entry, self.context)
                document.entries.append(entry)
            else:
                identifier(entry_id)
                index = next((i for i, e in enumerate(document.entries) if e.id == entry_id), None)
                if index is None:
                    raise ValueError("memory entry not found")
                original = document.entries[index]
                entry = MemoryEntry.model_validate(
                    {**original.model_dump(), **payload, "updated_at": now}
                )
                self._check_refs(entry, self.context)
                document.previous_entries.append(original)
                document.entries[index] = entry
            document.revision += 1
            # Revalidate mutated collections and enforce bounded JSON before replace.
            value = MemoryDocument.model_validate(document.model_dump()).model_dump()
            atomic_write(self.path(), json_bytes(value))
        return {"revision": document.revision, "entry": entry.model_dump(), "replay_allowed": False}

    def export(self, digest=None):
        with store_lock(self.root, "memory"):
            view = self.show(digest)
            directory = self.path(digest).parent
            paths = []
            for name, kinds in (("GUIDE.md", {"knowledge"}),
                                ("WORKING.md", {"progress", "failure", "hypothesis", "next_step"})):
                lines = [f"# {name}", "", "Generated view; edit memory.json through the CLI, not this file.",
                         f"Revision: {view['revision']}", f"Applicability: {view['applicability']}",
                         f"Review reasons: {view['review_reasons']}",
                         "Analysis only. Fresh observation required; replay is not authorized.", ""]
                for entry in view["entries"]:
                    if entry["kind"] in kinds:
                        lines.extend([f"## {entry['id']} [{entry['status']}]", entry["text"],
                                      f"Source: {entry['source']}",
                                      f"Evidence: {', '.join(entry['evidence_refs']) or 'none'}", ""])
                path = safe_path(directory, name)
                atomic_write(path, "\n".join(lines).encode("utf-8"))
                paths.append(str(path))
            return {"revision": view["revision"], "paths": paths,
                    "applicability": view["applicability"], "replay_allowed": False}
