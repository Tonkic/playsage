from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SetEffect:
    stat: str
    value: float
    coverage: float = 1.0
    weight: float | None = None


@dataclass(frozen=True)
class TargetSetPlan:
    cavern: str
    planar: str


@dataclass(frozen=True)
class StatWeightRule:
    stat: str
    weight: float
    after_units: float = 0.0


@dataclass(frozen=True)
class BuildProfile:
    id: str
    target_sets: TargetSetPlan
    stat_weights: dict[str, float]
    scoring_policy: str = "additive"
    main_stats: dict[str, tuple[str, ...]] = field(default_factory=dict)
    cavern_set_effects: tuple[SetEffect, ...] = ()
    planar_set_effects: tuple[SetEffect, ...] = ()
    enhancement_stop_threshold: float | None = None
    require_target_set: bool = True
    require_main_stat: bool = True
    set_score_policy: str = "gate_only"
    main_stat_score_policy: str = "gate_only"
    stat_weight_rules: dict[str, tuple[StatWeightRule, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scoring_policy not in {"additive", "set_first"}:
            raise ValueError(f"Unsupported relic scoring policy: {self.scoring_policy}")
        if self.set_score_policy not in {"gate_only", "scored"}:
            raise ValueError(f"Unsupported set score policy: {self.set_score_policy}")
        if self.main_stat_score_policy not in {"gate_only", "scored"}:
            raise ValueError(f"Unsupported main stat score policy: {self.main_stat_score_policy}")

    def effective_weight(self, stat: str) -> float:
        value = self.stat_weights.get(stat, 0.0)
        return _clamp_weight(value)

    def effective_weight_at_units(self, stat: str, current_units: float) -> float:
        rules = self.stat_weight_rules.get(stat)
        if not rules:
            return self.effective_weight(stat)
        selected = rules[0]
        for rule in rules:
            if current_units >= rule.after_units:
                selected = rule
            else:
                break
        return _clamp_weight(selected.weight)

    def accepts_main_stat(self, slot: str, stat: str) -> bool:
        if slot == "Head":
            return stat == "HP"
        if slot == "Hands":
            return stat == "ATK"
        allowed = self.main_stats.get(slot)
        if allowed is None:
            return self.effective_weight(stat) > 0
        return stat in allowed


@dataclass(frozen=True)
class RelicScoringConfig:
    global_stop_threshold: float
    profiles: dict[str, BuildProfile]
    active_profiles: dict[str, str] = field(default_factory=dict)

    def profile_for_character(self, character_id: str) -> BuildProfile:
        profile_id = self.active_profiles.get(character_id, character_id)
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"No active build profile configured for character {character_id}") from exc

    def effective_threshold(self, profile: BuildProfile) -> float:
        if profile.enhancement_stop_threshold is not None:
            return profile.enhancement_stop_threshold
        return self.global_stop_threshold

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelicScoringConfig:
        profiles = {
            profile_id: _profile_from_dict(profile_id, raw)
            for profile_id, raw in data.get("profiles", {}).items()
        }
        return cls(
            global_stop_threshold=float(data.get("global_stop_threshold", 0.0)),
            profiles=profiles,
            active_profiles=dict(data.get("active_profiles", {})),
        )


def _profile_from_dict(profile_id: str, raw: dict[str, Any]) -> BuildProfile:
    target_sets = raw.get("target_sets", {})
    return BuildProfile(
        id=profile_id,
        target_sets=TargetSetPlan(
            cavern=str(target_sets.get("cavern", "")),
            planar=str(target_sets.get("planar", "")),
        ),
        stat_weights={str(k): float(v) for k, v in raw.get("stat_weights", {}).items()},
        scoring_policy=str(raw.get("scoring_policy", "additive")),
        main_stats={
            str(slot): tuple(str(stat) for stat in stats)
            for slot, stats in raw.get("main_stats", {}).items()
        },
        cavern_set_effects=tuple(_effect_from_dict(x) for x in raw.get("cavern_set_effects", [])),
        planar_set_effects=tuple(_effect_from_dict(x) for x in raw.get("planar_set_effects", [])),
        enhancement_stop_threshold=(
            None
            if raw.get("enhancement_stop_threshold") is None
            else float(raw["enhancement_stop_threshold"])
        ),
        require_target_set=bool(raw.get("require_target_set", True)),
        require_main_stat=bool(raw.get("require_main_stat", True)),
        set_score_policy=str(raw.get("set_score_policy", "gate_only")),
        main_stat_score_policy=str(raw.get("main_stat_score_policy", "gate_only")),
        stat_weight_rules=_stat_weight_rules_from_dict(raw.get("stat_weight_rules", {})),
    )


def _effect_from_dict(raw: dict[str, Any]) -> SetEffect:
    return SetEffect(
        stat=str(raw["stat"]),
        value=float(raw["value"]),
        coverage=float(raw.get("coverage", 1.0)),
        weight=None if raw.get("weight") is None else float(raw["weight"]),
    )


def _stat_weight_rules_from_dict(raw: dict[str, Any]) -> dict[str, tuple[StatWeightRule, ...]]:
    rules: dict[str, tuple[StatWeightRule, ...]] = {}
    for stat, raw_rules in raw.items():
        parsed = []
        for raw_rule in raw_rules or []:
            parsed.append(
                StatWeightRule(
                    stat=str(stat),
                    weight=float(raw_rule["weight"]),
                    after_units=float(raw_rule.get("after_units", 0.0)),
                )
            )
        rules[str(stat)] = tuple(sorted(parsed, key=lambda rule: rule.after_units))
    return rules


def _clamp_weight(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
