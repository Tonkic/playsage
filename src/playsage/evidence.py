"""Offline visual evidence. Historical frames never authorize live input."""

import hashlib
import io
import json
import math
import os
import re
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageStat
from pydantic import Field, model_validator

from .models import StrictModel, is_redirect
from .runtime import WindowLease

MAX_JSON = 2 * 1024 * 1024
MAX_IMAGE = 64 * 1024 * 1024
MAX_PIXELS = 16_000_000
DEFAULT_CAPACITY = 1024 * 1024 * 1024


def utc_now():
    return datetime.now(UTC).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}", value):
        raise ValueError("invalid identifier")
    if value.upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)],
                          *[f"LPT{i}" for i in range(10)]}:
        raise ValueError("reserved identifier")
    return value


def safe_path(root, *parts):
    """Reject traversal, symlinks and Windows junctions, including existing ancestors."""
    root = Path(root).absolute()
    path = root.joinpath(*parts)
    if ".." in path.parts or not path.is_relative_to(root):
        raise ValueError("path outside allowed root")
    for item in (path, *path.parents):
        if item.is_symlink() or (item.exists() and is_redirect(item)):
            raise ValueError("linked paths are not allowed")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("path outside allowed root")
    return path


def read_json(path):
    path = Path(path)
    if path.stat().st_size > MAX_JSON:
        raise ValueError("JSON size limit exceeded")
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return value


def json_bytes(value):
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
    if len(raw) > MAX_JSON:
        raise ValueError("JSON size limit exceeded")
    return raw


def atomic_write(path, raw):
    """Same-directory replace; fsync data before publication. Caller holds a lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def store_lock(root, name):
    directory = safe_path(root, ".locks")
    # Use the existing cooperative OS lock, not a stale lockfile protocol.
    lock = WindowLease(directory, name)
    safe_path(root, str(lock.path.relative_to(root)))
    with lock:
        yield


class EvidenceContext(StrictModel):
    event_id: str | None = Field(default=None, pattern=r"^(zzz|ww|ef|hsr)\.[a-z0-9][a-z0-9-]*$")
    package_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    game_version: str | None = Field(default=None, min_length=1, max_length=128)
    resolution: list[int] | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def coherent(self):
        if self.package_digest is not None and self.event_id is None:
            raise ValueError("package digest requires event identity")
        if self.resolution is not None and any(n <= 0 for n in self.resolution):
            raise ValueError("resolution must be positive")
        return self


def decode_image(raw):
    if len(raw) > MAX_IMAGE:
        raise ValueError("image byte limit exceeded")
    with Image.open(io.BytesIO(raw)) as image:
        if image.format not in {"PNG", "JPEG"}:
            raise ValueError("only PNG/JPEG evidence is supported")
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("image pixel limit exceeded")
        image.load()
        return image.copy(), image.format


def region(image, roi):
    if roi is None:
        return (0, 0, image.width, image.height)
    if len(roi) != 4 or any(type(n) is not int for n in roi):
        raise ValueError("ROI requires four integer coordinates")
    x1, y1, x2, y2 = roi
    if not (0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height):
        raise ValueError("ROI outside image")
    return tuple(roi)


class EvidenceStore:
    def __init__(self, project, capacity=DEFAULT_CAPACITY):
        self.project = Path(project).absolute()
        self.root = safe_path(self.project, "runs", "evidence")
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity

    def path(self, run, *parts):
        return safe_path(self.root, identifier(run), *parts)

    def _files(self):
        files = []
        for path in self.root.rglob("*"):
            safe_path(self.root, str(path.relative_to(self.root)))
            if path.is_file():
                files.append(path)
        return files

    def stats(self):
        files = self._files()
        used = sum(path.stat().st_size for path in files)
        return {"bytes": used, "files": len(files), "capacity_bytes": self.capacity,
                "over_capacity": used > self.capacity, "automatic_deletion": False}

    def _reserve(self, size):
        if self.stats()["bytes"] + size > self.capacity:
            raise ValueError("evidence capacity limit exceeded; nothing is automatically deleted")

    def _records(self, run=None):
        roots = [self.path(run)] if run else sorted(self.root.glob("*"))
        for directory in roots:
            if directory.name.startswith("."):
                continue
            identifier(directory.name)
            for kind in ("frames", "steps"):
                for file in sorted(directory.glob(f"{kind}/*.json")):
                    safe_path(self.root, str(file.relative_to(self.root)))
                    value = read_json(file)
                    if value.get("schema_version") != 1:
                        raise ValueError("unsupported evidence schema")
                    yield value

    def history(self, run=None, event_id=None, limit=100, offset=0):
        EvidenceContext(event_id=event_id)
        if not 1 <= limit <= 1000 or offset < 0:
            raise ValueError("history bounds invalid")
        records = [r for r in self._records(run)
                   if event_id is None or r["context"]["event_id"] == event_id]
        records.sort(key=lambda r: (r["recorded_at"], r["run_id"], r["sequence"]))
        return {"total": len(records), "records": records[offset:offset + limit],
                "historical_only": True}

    def _base(self, run, kind, context):
        context = EvidenceContext.model_validate(context or {}).model_dump()
        sequence = max((r["sequence"] for r in self._records(run)), default=0) + 1
        return {"schema_version": 1, "kind": kind, "run_id": identifier(run),
                "sequence": sequence, "recorded_at": utc_now(), "context": context,
                "historical_only": True}

    def import_observation(self, source, run=None, context=None):
        source = Path(source)
        if not source.is_absolute():
            source = self.project / source
        # Only import existing observation stores; no arbitrary filesystem image access.
        allowed = [safe_path(self.project, "runs", name) for name in ("onedragon", "observations")]
        if not any(source.absolute().is_relative_to(base) for base in allowed):
            raise ValueError("observation must be inside runs/onedragon or runs/observations")
        source = safe_path(self.project, str(source.absolute().relative_to(self.project)))
        with source.open("rb") as stream:
            source_raw = stream.read(MAX_JSON + 1)
        if len(source_raw) > MAX_JSON:
            raise ValueError("JSON size limit exceeded")
        record = json.loads(source_raw.decode("utf-8"))
        if not isinstance(record, dict):
            raise TypeError("expected a JSON object")
        source_digest = hashlib.sha256(source_raw).hexdigest()
        backend = record.get("backend", record.get("source"))
        if backend == "onedragon":
            images = [{"path": record["screenshot"]}]
        elif backend == "sra":
            images = record["images"]
        else:
            raise ValueError("unsupported observation source")
        if not isinstance(images, list) or not 1 <= len(images) <= 16:
            raise ValueError("observation image count limit")
        run = identifier(run or uuid.uuid4().hex)
        context = EvidenceContext.model_validate(context or {}).model_dump()
        prepared = []
        captured = record.get("captured_at")
        if captured is not None:
            if type(captured) not in (int, float) or not math.isfinite(captured):
                raise ValueError("invalid Unix capture time")
            captured = datetime.fromtimestamp(captured, UTC).isoformat()
        for item in images:
            image_path = Path(item["path"])
            if not image_path.is_absolute():
                image_path = source.parent / image_path
            image_path = safe_path(source.parent, image_path)
            if image_path.stat().st_size > MAX_IMAGE:
                raise ValueError("image byte limit exceeded")
            raw = image_path.read_bytes()
            image, fmt = decode_image(raw)
            size = list(image.size)
            if context["resolution"] is not None and context["resolution"] != size:
                raise ValueError("context resolution differs from evidence")
            if item.get("size") is not None and item["size"] != size:
                raise ValueError("reported image size differs from evidence")
            prepared.append((raw, fmt, size))
        results = []
        with store_lock(self.root, "evidence"):
            pending = []
            base = self._base(run, "frame", context)
            for index, (raw, fmt, size) in enumerate(prepared):
                frame = uuid.uuid4().hex
                suffix = ".png" if fmt == "PNG" else ".jpg"
                name = f"frames/{frame}{suffix}"
                value = {**base, "sequence": base["sequence"] + index, "frame_id": frame,
                         "ref": f"{run}/{frame}", "backend": backend,
                         "session_id": record.get("session_id"),
                         "backend_pid": record.get("backend_pid"), "window": record.get("window"),
                         "window_identity_verified": record.get("window_identity_verified"),
                         "simulation": record.get("simulation"), "size": size,
                         "captured_at_utc": captured, "source": str(source),
                         "source_sha256": source_digest,
                         "image": name, "sha256": hashlib.sha256(raw).hexdigest(),
                         "analysis": record.get("analysis"), "text": record.get("text"),
                         "goal_status": "not_evaluated"}
                pending.extend([(self.path(run, name), raw),
                                (self.path(run, f"frames/{frame}.json"), json_bytes(value))])
                results.append(value)
            self._reserve(sum(len(raw) for _, raw in pending))
            for index in range(0, len(pending), 2):
                image_path, image_raw = pending[index]
                metadata_path, metadata_raw = pending[index + 1]
                if image_path.exists() or metadata_path.exists():
                    raise FileExistsError("generated frame identity already exists")
                atomic_write(image_path, image_raw)
                try:
                    atomic_write(metadata_path, metadata_raw)
                except BaseException as exc:
                    # Only roll back this newly allocated, uncommitted image, never old evidence.
                    if not metadata_path.exists():
                        try:
                            image_path.unlink(missing_ok=True)
                        except OSError as cleanup_error:
                            exc.add_note(f"incomplete image retained: {image_path}: {cleanup_error}")
                    raise
        return results

    def frame(self, ref):
        parts = ref.split("/")
        if len(parts) != 2:
            raise ValueError("frame reference must be run_id/frame_id")
        run, frame = map(identifier, parts)
        value = read_json(self.path(run, f"frames/{frame}.json"))
        if (value.get("schema_version") != 1 or value.get("kind") != "frame"
                or value.get("ref") != ref or value.get("run_id") != run
                or value.get("frame_id") != frame):
            raise ValueError("invalid frame record identity")
        if value.get("image") not in {f"frames/{frame}.png", f"frames/{frame}.jpg"}:
            raise ValueError("invalid frame image path")
        path = self.path(run, value["image"])
        if path.stat().st_size > MAX_IMAGE:
            raise ValueError("image byte limit exceeded")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != value["sha256"]:
            raise ValueError("evidence image hash mismatch")
        image, _ = decode_image(raw)
        if list(image.size) != value["size"]:
            raise ValueError("evidence size mismatch")
        return value, image, path

    def _derived(self, run, image, operation):
        output = io.BytesIO()
        image.save(output, format="PNG")
        raw = output.getvalue()
        path = self.path(run, "derived", f"{operation}-{uuid.uuid4().hex}.png")
        with store_lock(self.root, "evidence"):
            self._reserve(len(raw))
            atomic_write(path, raw)
        return str(path)

    def inspect(self, ref, roi=None):
        record, image, path = self.frame(ref)
        box = region(image, roi)
        if roi is not None:
            path = self._derived(record["run_id"], image.crop(box), "crop")
        return {"record": record, "path": str(path), "roi": box,
                "derived": roi is not None, "historical_only": True}

    def pixels(self, ref, roi=None):
        _, image, _ = self.frame(ref)
        box = region(image, roi)
        if (box[2] - box[0]) * (box[3] - box[1]) > 4096:
            raise ValueError("pixel output limit is 4096; request a smaller ROI")
        cropped = image.convert("RGB").crop(box)
        return {"ref": ref, "roi": box, "mode": "RGB", "size": list(cropped.size),
                "pixels": [cropped.getpixel((x, y)) for y in range(cropped.height)
                           for x in range(cropped.width)], "historical_only": True}

    def compare(self, first, second, roi=None):
        a, left, _ = self.frame(first)
        _, right, _ = self.frame(second)
        if left.size != right.size:
            raise ValueError("comparison requires same dimensions")
        box = region(left, roi)
        delta = ImageChops.difference(left.convert("RGB").crop(box),
                                     right.convert("RGB").crop(box))
        return {"before": first, "after": second, "roi": box,
                "mean_absolute_rgb": ImageStat.Stat(delta).mean,
                "changed_bbox": delta.getbbox(), "goal_status": "not_evaluated",
                "path": self._derived(a["run_id"], delta, "diff"), "derived": True}

    def start_step(self, run, before, tool, arguments, expected=None, reference=None):
        frame, _, _ = self.frame(before)
        if frame["run_id"] != run:
            raise ValueError("step before frame must belong to the same run")
        step = uuid.uuid4().hex
        with store_lock(self.root, "evidence"):
            value = {**self._base(run, "step", frame["context"]), "step_id": step,
                     "before": before, "after": None, "tool": tool, "arguments": arguments,
                     "reference": reference, "expected": expected,
                     "expected_status": "provided" if expected else "not_provided",
                     "status": "intent_recorded", "backend_result": None,
                     "actual": None, "visual_change": None, "goal_status": "not_evaluated"}
            raw = json_bytes(value)
            self._reserve(len(raw))
            atomic_write(self.path(run, f"steps/{step}.json"), raw)
        return value

    def update_step(self, run, step, **updates):
        if set(updates) - {"after", "status", "backend_result", "actual", "visual_change", "error"}:
            raise ValueError("unsupported step update")
        if updates.get("status") not in {
            None, "backend_returned", "observed", "incomplete", "not_dispatched",
        }:
            raise ValueError("unsupported step status")
        with store_lock(self.root, "evidence"):
            path = self.path(run, f"steps/{identifier(step)}.json")
            value = read_json(path)
            if updates.get("after") is not None:
                frame, _, _ = self.frame(updates["after"])
                if frame["run_id"] != run or frame["context"] != value["context"]:
                    raise ValueError("step after frame context mismatch")
            value.update(updates, updated_at=utc_now())
            raw = json_bytes(value)
            self._reserve(len(raw))  # includes temporary replacement space
            atomic_write(path, raw)
        return value

    def cleanup_preview(self):
        """No deletion API. Any corrupt memory makes the preview fail closed."""
        referenced = set()
        memory_root = safe_path(self.project, "data", "event_memory")
        for file in memory_root.glob("*/*/*/memory.json"):
            safe_path(memory_root, str(file.relative_to(memory_root)))
            from .memory import MemoryDocument

            memory = MemoryDocument.model_validate(read_json(file))
            for entry in memory.entries + memory.previous_entries:
                referenced.update(entry.evidence_refs)
        list(self._records())  # Fail closed on corrupt published metadata.
        protected_runs = {ref.split("/")[0] for ref in referenced}
        runs = {identifier(p.name) for p in self.root.glob("*")
                if p.is_dir() and not p.name.startswith(".")}
        incomplete = [str(p) for p in self._files()
                      if p.parent.name == "frames" and p.suffix in {".png", ".jpg"}
                      and not p.with_suffix(".json").exists()]
        return {"stats": self.stats(), "delete_enabled": False,
                "protected_runs": sorted(protected_runs), "incomplete_files": incomplete,
                "unreferenced_runs": sorted(runs - protected_runs),
                "note": "Preview only; unreferenced does not imply safe to delete."}
