"""Offline GameScaling-S3 RSI records and Champion/Challenger evaluation.

This module intentionally stops at dataset bookkeeping and offline evaluation. It does
not load model weights, capture screens, or dispatch game input.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .evidence import MAX_JSON, safe_path, store_lock
from .models import StrictModel

SCHEMA_VERSION = 1
_COLLECTIONS = {
    "episodes": "episodes.jsonl",
    "takeovers": "takeovers.jsonl",
    "models": "model_versions.jsonl",
    "evaluations": "evaluations.jsonl",
    "decisions": "decisions.jsonl",
}
_EPISODE_ID = r"[a-z0-9][a-z0-9_-]{0,95}"
_VERSION_ID = r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}"
_FAILURE_TYPES = Literal[
    "low_confidence",
    "parse_error",
    "no_progress",
    "stuck",
    "combat_failure",
    "ui_mistake",
    "timeout",
    "other",
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("numeric values must be finite")
    return value


class FrameRecord(StrictModel):
    frame_id: str = Field(pattern=_EPISODE_ID)
    t_ms: int = Field(ge=0)
    ref: str = Field(min_length=1, max_length=512)
    resolution: list[int] | None = Field(default=None, min_length=2, max_length=2)
    scene: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def valid_resolution(self):
        if self.resolution is not None and any(value <= 0 for value in self.resolution):
            raise ValueError("frame resolution must be positive")
        return self


class ActionRecord(StrictModel):
    action_id: str = Field(pattern=_EPISODE_ID)
    t_ms: int = Field(ge=0)
    duration_ms: int = Field(default=0, ge=0, le=60_000)
    mouse_dx: int = Field(default=0, ge=-100_000, le=100_000)
    mouse_dy: int = Field(default=0, ge=-100_000, le=100_000)
    keys_down: list[str] = Field(default_factory=list, max_length=32)
    keys_up: list[str] = Field(default_factory=list, max_length=32)
    buttons_down: list[str] = Field(default_factory=list, max_length=8)
    buttons_up: list[str] = Field(default_factory=list, max_length=8)
    confidence: float | None = Field(default=None, ge=0, le=1)
    parse_error: bool = False

    @model_validator(mode="after")
    def finite_confidence(self):
        if self.confidence is not None:
            _finite(self.confidence)
        return self


class FailureRecord(StrictModel):
    failure_id: str = Field(pattern=_EPISODE_ID)
    type: _FAILURE_TYPES
    t_ms: int = Field(ge=0)
    detail: str = Field(default="", max_length=2000)


class TakeoverRecord(StrictModel):
    takeover_id: str = Field(pattern=_EPISODE_ID)
    episode_id: str = Field(pattern=_EPISODE_ID)
    start_ms: int = Field(ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    reason: Literal["low_confidence", "stuck", "failure", "safety", "operator_request", "other"]
    operator: str = Field(default="human", min_length=1, max_length=128)
    detail: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def ordered_interval(self):
        if self.end_ms is not None and self.end_ms < self.start_ms:
            raise ValueError("takeover end_ms must be >= start_ms")
        return self


class EpisodeRecord(StrictModel):
    episode_id: str = Field(pattern=_EPISODE_ID)
    game: str = Field(pattern=r"[a-z0-9][a-z0-9_-]{0,31}")
    task: str = Field(min_length=1, max_length=512)
    model_version: str = Field(min_length=1, max_length=128)
    outcome: Literal["success", "failure", "aborted", "unknown"] = "unknown"
    goal_progress: float = Field(default=0, ge=0, le=1)
    min_confidence: float | None = Field(default=None, ge=0, le=1)
    parse_failures: int = Field(default=0, ge=0)
    stuck_events: int = Field(default=0, ge=0)
    frames: list[FrameRecord] = Field(default_factory=list, max_length=100_000)
    actions: list[ActionRecord] = Field(default_factory=list, max_length=100_000)
    failures: list[FailureRecord] = Field(default_factory=list, max_length=10_000)
    takeovers: list[TakeoverRecord] = Field(default_factory=list, max_length=1_000)
    context: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_trace(self):
        if self.min_confidence is not None:
            _finite(self.min_confidence)
        frame_times = [frame.t_ms for frame in self.frames]
        if frame_times != sorted(frame_times):
            raise ValueError("frames must be ordered by t_ms")
        action_times = [action.t_ms for action in self.actions]
        if action_times != sorted(action_times):
            raise ValueError("actions must be ordered by t_ms")
        if self.parse_failures < sum(action.parse_error for action in self.actions):
            raise ValueError("parse_failures cannot be lower than action parse errors")
        if self.stuck_events < sum(failure.type == "stuck" for failure in self.failures):
            raise ValueError("stuck_events cannot be lower than stuck failure records")
        for takeover in self.takeovers:
            if takeover.episode_id != self.episode_id:
                raise ValueError("embedded takeover belongs to another episode")
        return self


class ModelVersionRecord(StrictModel):
    version: str = Field(pattern=_VERSION_ID)
    base_model: str = Field(min_length=1, max_length=256)
    adapter: str | None = Field(default=None, max_length=256)
    game: str | None = Field(default=None, pattern=r"[a-z0-9][a-z0-9_-]{0,31}")
    role: Literal["baseline", "champion", "challenger", "candidate"] = "candidate"
    artifact_ref: str | None = Field(default=None, max_length=512)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class CaseResult(StrictModel):
    case_id: str = Field(pattern=_EPISODE_ID)
    success: bool
    parse_failures: int = Field(default=0, ge=0)
    unsafe_actions: int = Field(default=0, ge=0)
    completed: bool = True
    detail: str = Field(default="", max_length=2000)


class EvaluationRecord(StrictModel):
    evaluation_id: str = Field(pattern=_EPISODE_ID)
    suite_id: str = Field(pattern=_EPISODE_ID)
    model_version: str = Field(pattern=_VERSION_ID)
    cases: list[CaseResult] = Field(min_length=1, max_length=100_000)
    source: str = Field(default="offline", min_length=1, max_length=256)

    @model_validator(mode="after")
    def unique_cases(self):
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation case_id values must be unique")
        return self


class RsiStore:
    """Filesystem-backed JSONL store for offline RSI artifacts."""

    def __init__(self, project: Path):
        self.project = Path(project).absolute()
        self.root = safe_path(self.project, "runs", "gamescaling_rsi")

    def _path(self, collection: str) -> Path:
        try:
            filename = _COLLECTIONS[collection]
        except KeyError as exc:
            raise ValueError(f"unknown RSI collection: {collection}") from exc
        return safe_path(self.root, filename)

    def _read(self, collection: str) -> list[dict]:
        path = self._path(collection)
        if not path.exists():
            return []
        values = []
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid {collection} JSONL at line {line_number}") from exc
                if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
                    raise ValueError(f"unsupported {collection} record at line {line_number}")
                values.append(value)
        return values

    @staticmethod
    def _field(value: dict, path: str):
        current = value
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _append_many(self, collection: str, values: list[dict], id_field: str) -> None:
        if not values:
            return
        path = self._path(collection)
        existing = {self._field(value, id_field) for value in self._read(collection)}
        incoming = [self._field(value, id_field) for value in values]
        if any(value is None for value in incoming) or len(incoming) != len(set(incoming)):
            raise ValueError(f"duplicate or missing {id_field}")
        if existing.intersection(incoming):
            raise ValueError(f"{id_field} already exists")
        raw = b"".join((json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8") for value in values)
        with store_lock(self.root, "gamescaling-rsi"):
            # Re-read after taking the lock so two offline writers cannot publish duplicates.
            existing = {self._field(value, id_field) for value in self._read(collection)}
            if existing.intersection(incoming):
                raise ValueError(f"{id_field} already exists")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("ab") as stream:
                stream.write(raw)
                stream.flush()
        safe_path(self.root, path.name)

    @staticmethod
    def _envelope(value: dict) -> dict:
        return {"schema_version": SCHEMA_VERSION, "recorded_at": utc_now(), **value}

    def episodes(self) -> list[EpisodeRecord]:
        return [EpisodeRecord.model_validate(value["record"]) for value in self._read("episodes")]

    def takeovers(self) -> list[TakeoverRecord]:
        return [TakeoverRecord.model_validate(value["record"]) for value in self._read("takeovers")]

    def models(self) -> list[ModelVersionRecord]:
        return [ModelVersionRecord.model_validate(value["record"]) for value in self._read("models")]

    def evaluations(self) -> list[EvaluationRecord]:
        return [EvaluationRecord.model_validate(value["record"]) for value in self._read("evaluations")]

    def record_episodes(self, records: list[EpisodeRecord]) -> list[EpisodeRecord]:
        if not records:
            raise ValueError("at least one episode is required")
        values = [self._envelope({"record": record.model_dump()}) for record in records]
        self._append_many("episodes", values, "record.episode_id")
        return records

    def record_takeover(self, takeover: TakeoverRecord) -> TakeoverRecord:
        if not any(episode.episode_id == takeover.episode_id for episode in self.episodes()):
            raise ValueError("takeover episode does not exist")
        value = self._envelope({"record": takeover.model_dump()})
        self._append_many("takeovers", [value], "record.takeover_id")
        return takeover

    def register_model(self, model: ModelVersionRecord) -> ModelVersionRecord:
        value = self._envelope({"record": model.model_dump()})
        self._append_many("models", [value], "record.version")
        return model

    def record_evaluation(self, evaluation: EvaluationRecord) -> EvaluationRecord:
        if not any(model.version == evaluation.model_version for model in self.models()):
            raise ValueError("evaluation model_version is not registered")
        value = self._envelope({"record": evaluation.model_dump()})
        self._append_many("evaluations", [value], "record.evaluation_id")
        return evaluation

    def import_trajectory(self, source: Path) -> list[EpisodeRecord]:
        source = Path(source)
        if not source.is_absolute():
            source = self.project / source
        source = source.absolute()
        if not source.is_relative_to(self.project):
            raise ValueError("trajectory source must be inside project root")
        source = safe_path(self.project, str(source.relative_to(self.project)))
        raw = source.read_bytes()
        if len(raw) > MAX_JSON * 16:
            raise ValueError("trajectory input size limit exceeded")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            records = []
            for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"invalid trajectory JSONL at line {line_number}") from exc
        else:
            if isinstance(parsed, dict) and "episodes" in parsed:
                records = parsed["episodes"]
            elif isinstance(parsed, list):
                records = parsed
            else:
                records = [parsed]
        if not isinstance(records, list) or not records:
            raise ValueError("trajectory input must contain at least one episode")
        episodes = [EpisodeRecord.model_validate(record) for record in records]
        return self.record_episodes(episodes)

    def hard_examples(self, limit: int = 100, min_score: int = 1) -> dict:
        if not 1 <= limit <= 10_000 or min_score < 1:
            raise ValueError("hard example bounds invalid")
        external_takeovers: dict[str, list[TakeoverRecord]] = {}
        for takeover in self.takeovers():
            external_takeovers.setdefault(takeover.episode_id, []).append(takeover)
        selected = []
        for episode in self.episodes():
            reasons: list[str] = []
            score = 0
            takeovers = [*episode.takeovers, *external_takeovers.get(episode.episode_id, [])]
            if takeovers:
                reasons.append("human_takeover")
                score += 4
            if episode.outcome in {"failure", "aborted"}:
                reasons.append("unsuccessful_outcome")
                score += 2
            if episode.goal_progress < 0.8:
                reasons.append("low_progress")
                score += 2
            if episode.min_confidence is not None:
                if episode.min_confidence < 0.45:
                    reasons.append("low_confidence")
                    score += 2
                elif episode.min_confidence < 0.65:
                    reasons.append("medium_confidence")
                    score += 1
            if episode.parse_failures:
                reasons.append("parse_error")
                score += 3
            if episode.stuck_events:
                reasons.append("stuck")
                score += 2
            failure_types = {failure.type for failure in episode.failures}
            for failure_type, weight in {
                "combat_failure": 2,
                "ui_mistake": 2,
                "no_progress": 1,
                "timeout": 1,
            }.items():
                if failure_type in failure_types:
                    reasons.append(failure_type)
                    score += weight
            if score >= min_score:
                selected.append({
                    "episode_id": episode.episode_id,
                    "game": episode.game,
                    "task": episode.task,
                    "model_version": episode.model_version,
                    "score": score,
                    "reasons": reasons,
                    "frame_refs": [frame.ref for frame in episode.frames],
                    "action_count": len(episode.actions),
                    "outcome": episode.outcome,
                    "goal_progress": episode.goal_progress,
                })
        selected.sort(key=lambda item: (-item["score"], item["episode_id"]))
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": "offline_hard_example_selection",
            "historical_only": True,
            "total": len(selected),
            "examples": selected[:limit],
        }

    def _latest_evaluation(self, model_version: str, suite_id: str) -> EvaluationRecord:
        matches = [
            evaluation for evaluation in self.evaluations()
            if evaluation.model_version == model_version and evaluation.suite_id == suite_id
        ]
        if not matches:
            raise ValueError(f"no evaluation for {model_version} in suite {suite_id}")
        return matches[-1]

    @staticmethod
    def _rates(evaluation: EvaluationRecord) -> dict[str, float]:
        count = len(evaluation.cases)
        return {
            "success_rate": sum(case.success for case in evaluation.cases) / count,
            "parse_failure_rate": sum(case.parse_failures > 0 for case in evaluation.cases) / count,
            "unsafe_action_rate": sum(case.unsafe_actions > 0 for case in evaluation.cases) / count,
            "completed_rate": sum(case.completed for case in evaluation.cases) / count,
        }

    def compare_models(self, champion: str, challenger: str, suite_id: str) -> dict:
        if champion == challenger:
            raise ValueError("champion and challenger must differ")
        champion_eval = self._latest_evaluation(champion, suite_id)
        challenger_eval = self._latest_evaluation(challenger, suite_id)
        champion_ids = {case.case_id for case in champion_eval.cases}
        challenger_ids = {case.case_id for case in challenger_eval.cases}
        if champion_ids != challenger_ids:
            raise ValueError("champion and challenger must use the same fixed task set")
        champion_rates = self._rates(champion_eval)
        challenger_rates = self._rates(challenger_eval)
        deltas = {
            key: challenger_rates[key] - champion_rates[key] for key in champion_rates
        }
        accepted = (
            deltas["success_rate"] > 0
            and deltas["parse_failure_rate"] <= 0
            and deltas["unsafe_action_rate"] <= 0
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": "offline_champion_challenger",
            "historical_only": True,
            "suite_id": suite_id,
            "champion": champion,
            "challenger": challenger,
            "case_count": len(champion_eval.cases),
            "champion_rates": champion_rates,
            "challenger_rates": challenger_rates,
            "deltas": deltas,
            "decision": "promote" if accepted else "reject",
            "runtime_switch": False,
            "weights_modified": False,
        }

    def promote(self, champion: str, challenger: str, suite_id: str) -> dict:
        comparison = self.compare_models(champion, challenger, suite_id)
        if comparison["decision"] != "promote":
            raise ValueError("challenger did not pass offline promotion gates")
        decision = {
            **comparison,
            "decision_id": uuid.uuid4().hex,
            "recorded_at": utc_now(),
            "action": "recorded_promotion",
        }
        self._append_many("decisions", [decision], "decision_id")
        return decision

    def decisions(self) -> list[dict]:
        return self._read("decisions")


def load_record(path: Path, model_type):
    """Load one bounded JSON object for CLI commands."""
    path = Path(path)
    raw = path.read_bytes()
    if len(raw) > MAX_JSON:
        raise ValueError("JSON size limit exceeded")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("expected a JSON object")
    return model_type.model_validate(value)
