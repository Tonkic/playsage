"""Evidence-linked, annotation-based grid checks; no game input or dynamic imports."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from . import grid_route
from .evidence import EvidenceContext
from .grid_route import Board, advance
from .models import StrictModel

Coordinate = Annotated[list[int], Field(min_length=2, max_length=2)]
Cells = Annotated[list[Coordinate], Field(max_length=4096)]


class Port(StrictModel):
    cell: Coordinate
    ports: str = Field(min_length=1, max_length=4, pattern=r"^[wsad]+$")


class Forced(StrictModel):
    cell: Coordinate
    key: Literal["w", "s", "a", "d"]


class BoardSpec(StrictModel):
    rows: int = Field(ge=1, le=64)
    columns: int = Field(ge=1, le=64)
    blocked: Cells = Field(default_factory=list)
    excluded: Cells = Field(default_factory=list)
    targets: Cells = Field(default_factory=list)
    end: Coordinate
    ports: list[Port] = Field(default_factory=list, max_length=4096)
    rotations: Cells = Field(default_factory=list)
    ordered_targets: Cells = Field(default_factory=list)
    forced: list[Forced] = Field(default_factory=list, max_length=4096)
    teleports: list[Annotated[list[Coordinate], Field(min_length=2, max_length=2)]] = Field(
        default_factory=list, max_length=2048,
    )

    @model_validator(mode="after")
    def no_duplicates(self):
        groups = [self.blocked, self.excluded, self.targets, self.rotations, self.ordered_targets,
                  [p.cell for p in self.ports], [f.cell for f in self.forced],
                  [cell for pair in self.teleports for cell in pair]]
        if any(len(group) != len(set(map(tuple, group))) for group in groups):
            raise ValueError("duplicate board coordinates")
        return self

    def board(self):
        return Board(
            self.rows, self.columns, frozenset(map(tuple, self.blocked + self.excluded)),
            frozenset(map(tuple, self.targets)), tuple(self.end),
            {tuple(p.cell): p.ports for p in self.ports}, frozenset(map(tuple, self.rotations)),
            tuple(map(tuple, self.ordered_targets)), {tuple(f.cell): f.key for f in self.forced},
            {tuple(a): tuple(b) for pair in self.teleports for a, b in (pair, pair[::-1])},
        )


class GridState(StrictModel):
    prefix: Cells = Field(min_length=1)
    position: Coordinate
    collected: Cells
    turns: int = Field(ge=0, le=3)
    complete: bool


class Interaction(StrictModel):
    prefix: Cells = Field(min_length=1)
    action: str = Field(min_length=1, max_length=32)
    before_ref: str | None = None
    after_ref: str | None = None
    annotation_source: str | None = Field(default=None, min_length=1, max_length=2000)
    observed: dict | None = None


class ValidationInput(StrictModel):
    schema_version: Literal[1] = 1
    model_revision: str = Field(default="grid-v1", min_length=1, max_length=128)
    context: EvidenceContext
    board: BoardSpec
    interactions: list[Interaction] = Field(min_length=1, max_length=1000)


def state_for(board, route):
    seen = set(route)
    return {"prefix": [list(cell) for cell in route], "position": list(route[-1]),
            "collected": [list(cell) for cell in sorted(board.targets & seen)],
            "turns": len(board.rotations & seen) % 4,
            "complete": route[-1] == board.end and board.targets <= seen}


def check_evidence(store, interaction, context):
    if (not interaction.before_ref or not interaction.after_ref
            or not interaction.annotation_source or interaction.observed is None):
        raise ValueError("before/after evidence and sourced observed state are required")
    if (any(context[k] is None for k in context) or context["game_version"] == "unknown"):
        raise ValueError("unknown activity/package/version/resolution; re-observe and annotate")
    before, _, _ = store.frame(interaction.before_ref)
    after, _, _ = store.frame(interaction.after_ref)
    for frame in (before, after):
        if frame["context"] != context or frame["size"] != context["resolution"]:
            raise ValueError("evidence context mismatch")
    if before["source_sha256"] == after["source_sha256"]:
        raise ValueError("duplicate original observation cannot supply an independent after frame")
    if before["run_id"] != after["run_id"] or before["sequence"] >= after["sequence"]:
        raise ValueError("before/after must be distinct ordered frames in one run")
    for field in ("backend", "session_id", "backend_pid", "size", "simulation"):
        if before[field] != after[field]:
            raise ValueError(f"evidence {field} changed")
    if (before["captured_at_utc"] is not None and after["captured_at_utc"] is not None
            and before["captured_at_utc"] > after["captured_at_utc"]):
        raise ValueError("capture time runs backwards")
    return {"before": before["ref"], "after": after["ref"],
            "simulation": before["simulation"], "annotation_source": interaction.annotation_source}


def validate_grid(data, store):
    report = {
        "schema_version": 1, "mode": "offline_annotation_check", "replay_allowed": False,
        "goal_status": "not_evaluated",
        "limitation": "Match means agreement with supplied annotations, not visual or live verification.",
        "engine_sha256": hashlib.sha256(Path(grid_route.__file__).read_bytes()).hexdigest(),
        "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    try:
        request = ValidationInput.model_validate(data)
    except ValidationError as exc:
        return {**report, "status": "insufficient_evidence", "success": False,
                "error": str(exc), "recommendation": "repair input or bypass unsupported model",
                "results": []}
    context = request.context.model_dump()
    spec = request.board.model_dump()
    report.update(context=context, model_revision=request.model_revision,
                  board_sha256=hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest())
    board = request.board.board()
    results = []
    for number, item in enumerate(request.interactions, 1):
        result = {"index": number, "action": item.action, "before_ref": item.before_ref,
                  "after_ref": item.after_ref, "status": "insufficient_evidence",
                  "differences": {}, "predicted": None, "observed": item.observed}
        try:
            result["evidence"] = check_evidence(store, item, context)
            observed = GridState.model_validate(item.observed).model_dump()
            # Sorting a set-valued observation is presentation, not a rule inference.
            if len(observed["collected"]) != len(set(map(tuple, observed["collected"]))):
                raise ValueError("duplicate collected target annotation")
            observed["collected"] = sorted(observed["collected"])
            predicted = state_for(board, advance(board, list(map(tuple, item.prefix)), item.action))
            differences = {key: {"predicted": predicted[key], "observed": observed[key]}
                           for key in predicted if predicted[key] != observed[key]}
            result.update(predicted=predicted, observed=observed, differences=differences,
                          status="mismatch" if differences else "match",
                          recommendation=("review annotation/rules; bypass model until resolved"
                                          if differences else "continue offline checking; no input authorization"))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            result.update(error=str(exc), recommendation="re-observe/annotate or bypass unsupported model")
        results.append(result)
    counts = {status: sum(r["status"] == status for r in results)
              for status in ("match", "mismatch", "insufficient_evidence")}
    status = ("mismatch" if counts["mismatch"] else
              "insufficient_evidence" if counts["insufficient_evidence"] else "match")
    return {**report, "status": status, "success": status == "match", "counts": counts,
            "results": results}
