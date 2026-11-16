from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from .config import BuildProfile, RelicScoringConfig, SetEffect, StatWeightRule, TargetSetPlan

FRIBBELS_STAT_ALIASES = {
    "HP%": "HP_",
    "ATK%": "ATK_",
    "DEF%": "DEF_",
    "CRIT Rate": "CRIT Rate_",
    "CRIT DMG": "CRIT DMG_",
    "Effect Hit Rate": "Effect Hit Rate_",
    "Effect RES": "Effect RES_",
    "Break Effect": "Break Effect_",
}

FRIBBELS_SLOT_ALIASES = {
    "Body": "Body",
    "Feet": "Feet",
    "PlanarSphere": "Planar Sphere",
    "Planar Sphere": "Planar Sphere",
    "LinkRope": "Link Rope",
    "Link Rope": "Link Rope",
}


def build_profile_from_fribbels_metadata(
    character_id: str,
    metadata: Mapping[str, Any],
    *,
    profile_id: str | None = None,
    set_id_map: Mapping[str, str] | None = None,
    set_effect_catalog: Mapping[str, Sequence[Mapping[str, Any] | SetEffect]] | None = None,
    enhancement_stop_threshold: float | None = None,
    scoring_policy: str | None = None,
) -> BuildProfile:
    """Convert Fribbels ScoringMetadata into a March7th BuildProfile.

    Fribbels metadata gives us stat weights, acceptable main stats, and
    recommended relic/ornament sets. Set effect values are intentionally supplied
    by this project because coverage and conditional uptime are profile policy.
    """

    scoring = _scoring_metadata(metadata)
    simulation = _preferred_simulation(scoring)
    cavern_set = _target_cavern_set(simulation, set_id_map)
    planar_set = _target_planar_set(simulation, set_id_map)

    return BuildProfile(
        id=profile_id or f"{character_id}:fribbels_default",
        target_sets=TargetSetPlan(cavern=cavern_set, planar=planar_set),
        stat_weights=_convert_stat_weights(scoring.get("stats", {})),
        scoring_policy=scoring_policy or _default_scoring_policy(scoring),
        main_stats=_convert_main_stats(scoring.get("parts", {})),
        cavern_set_effects=_catalog_effects(set_effect_catalog, cavern_set),
        planar_set_effects=_catalog_effects(set_effect_catalog, planar_set),
        enhancement_stop_threshold=enhancement_stop_threshold,
    )


def build_config_from_fribbels_metadata(
    characters: Mapping[str, Mapping[str, Any]],
    *,
    global_stop_threshold: float = 0.0,
    set_id_map: Mapping[str, str] | None = None,
    set_effect_catalog: Mapping[str, Sequence[Mapping[str, Any] | SetEffect]] | None = None,
    profile_overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> RelicScoringConfig:
    """Build a RelicScoringConfig from Fribbels character metadata.

    ``characters`` can be either Fribbels DB character records containing
    ``scoringMetadata`` or a mapping of character id to raw ``ScoringMetadata``.
    Overrides are applied per character after template generation.
    """

    profiles: dict[str, BuildProfile] = {}
    active_profiles: dict[str, str] = {}
    for character_id, metadata in characters.items():
        override = dict((profile_overrides or {}).get(str(character_id), {}))
        threshold = override.pop("enhancement_stop_threshold", None)
        profile = build_profile_from_fribbels_metadata(
            str(character_id),
            metadata,
            set_id_map=set_id_map,
            set_effect_catalog=set_effect_catalog,
            enhancement_stop_threshold=None if threshold is None else float(threshold),
        )
        profile = apply_profile_override(profile, override)
        profiles[profile.id] = profile
        active_profiles[str(character_id)] = profile.id

    return RelicScoringConfig(
        global_stop_threshold=float(global_stop_threshold),
        profiles=profiles,
        active_profiles=active_profiles,
    )


def apply_profile_override(profile: BuildProfile, override: Mapping[str, Any]) -> BuildProfile:
    if not override:
        return profile

    target_sets = override.get("target_sets")
    if target_sets:
        profile = replace(
            profile,
            target_sets=TargetSetPlan(
                cavern=str(target_sets.get("cavern", profile.target_sets.cavern)),
                planar=str(target_sets.get("planar", profile.target_sets.planar)),
            ),
        )

    replacements: dict[str, Any] = {}
    if "stat_weights" in override:
        replacements["stat_weights"] = {
            **profile.stat_weights,
            **{
                normalize_fribbels_stat(str(k)): float(v)
                for k, v in override["stat_weights"].items()
            },
        }
    if "scoring_policy" in override:
        replacements["scoring_policy"] = str(override["scoring_policy"])
    if "require_target_set" in override:
        replacements["require_target_set"] = bool(override["require_target_set"])
    if "require_main_stat" in override:
        replacements["require_main_stat"] = bool(override["require_main_stat"])
    if "set_score_policy" in override:
        replacements["set_score_policy"] = str(override["set_score_policy"])
    if "main_stat_score_policy" in override:
        replacements["main_stat_score_policy"] = str(override["main_stat_score_policy"])
    if "main_stats" in override:
        replacements["main_stats"] = {
            **profile.main_stats,
            **{
                normalize_fribbels_slot(str(slot)): tuple(
                    normalize_fribbels_stat(str(stat)) for stat in stats
                )
                for slot, stats in override["main_stats"].items()
            },
        }
    if "cavern_set_effects" in override:
        replacements["cavern_set_effects"] = tuple(
            _effect_from_any(effect) for effect in override["cavern_set_effects"]
        )
    if "planar_set_effects" in override:
        replacements["planar_set_effects"] = tuple(
            _effect_from_any(effect) for effect in override["planar_set_effects"]
        )
    if "stat_weight_rules" in override:
        replacements["stat_weight_rules"] = {
            **profile.stat_weight_rules,
            **_stat_weight_rules_from_override(override["stat_weight_rules"]),
        }
    if "enhancement_stop_threshold" in override:
        raw_threshold = override["enhancement_stop_threshold"]
        replacements["enhancement_stop_threshold"] = (
            None if raw_threshold is None else float(raw_threshold)
        )

    return replace(profile, **replacements) if replacements else profile


def _stat_weight_rules_from_override(raw: Mapping[str, Any]) -> dict[str, tuple[StatWeightRule, ...]]:
    rules: dict[str, tuple[StatWeightRule, ...]] = {}
    for stat, raw_rules in raw.items():
        if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, str):
            continue
        rules[normalize_fribbels_stat(str(stat))] = tuple(
            StatWeightRule(
                stat=normalize_fribbels_stat(str(stat)),
                weight=float(rule["weight"]),
                after_units=float(rule.get("after_units", 0.0)),
            )
            for rule in raw_rules
            if isinstance(rule, Mapping) and "weight" in rule
        )
    return rules


def normalize_fribbels_stat(stat: str) -> str:
    return FRIBBELS_STAT_ALIASES.get(str(stat), str(stat))


def normalize_fribbels_slot(slot: str) -> str:
    return FRIBBELS_SLOT_ALIASES.get(str(slot), str(slot))


def _scoring_metadata(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    return metadata.get("scoringMetadata", metadata)


def _preferred_simulation(scoring: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("simulation", "supportSimulation", "healSimulation", "shieldSimulation"):
        value = scoring.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _default_scoring_policy(scoring: Mapping[str, Any]) -> str:
    if any(isinstance(scoring.get(key), Mapping) for key in ("supportSimulation", "healSimulation", "shieldSimulation")):
        return "set_first"
    return "additive"


def _convert_stat_weights(stats: Mapping[str, Any]) -> dict[str, float]:
    return {
        normalize_fribbels_stat(stat): _clamp_weight(float(value))
        for stat, value in stats.items()
        if stat != "minWeightedRolls"
    }


def _convert_main_stats(parts: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    converted: dict[str, tuple[str, ...]] = {}
    for slot, stats in parts.items():
        if not isinstance(stats, Sequence) or isinstance(stats, str):
            continue
        converted[normalize_fribbels_slot(slot)] = tuple(
            normalize_fribbels_stat(stat) for stat in stats
        )
    return converted


def _target_cavern_set(
    simulation: Mapping[str, Any],
    set_id_map: Mapping[str, str] | None,
) -> str:
    relic_sets = simulation.get("relicSets", [])
    if not relic_sets:
        return ""

    first_combo = relic_sets[0]
    if isinstance(first_combo, (str, Mapping)):
        return _resolve_set_id(first_combo, set_id_map)
    if isinstance(first_combo, Sequence):
        for set_ref in first_combo:
            resolved = _resolve_set_id(set_ref, set_id_map)
            if resolved:
                return resolved
    return ""


def _target_planar_set(
    simulation: Mapping[str, Any],
    set_id_map: Mapping[str, str] | None,
) -> str:
    ornament_sets = simulation.get("ornamentSets", [])
    if not ornament_sets:
        return ""
    if isinstance(ornament_sets, Sequence) and not isinstance(ornament_sets, str):
        return _resolve_set_id(ornament_sets[0], set_id_map)
    return _resolve_set_id(ornament_sets, set_id_map)


def _resolve_set_id(set_ref: Any, set_id_map: Mapping[str, str] | None) -> str:
    if set_ref is None:
        return ""
    if isinstance(set_ref, Mapping):
        for key in ("ingameId", "set_id", "setId"):
            if key in set_ref:
                return str(set_ref[key])
        for key in ("id", "setKey", "name"):
            if key in set_ref:
                return _resolve_set_id(set_ref[key], set_id_map)
        return ""

    value = str(set_ref)
    if value.isdigit():
        return value
    if set_id_map and value in set_id_map:
        return str(set_id_map[value])
    return ""


def _catalog_effects(
    set_effect_catalog: Mapping[str, Sequence[Mapping[str, Any] | SetEffect]] | None,
    set_id: str,
) -> tuple[SetEffect, ...]:
    if not set_effect_catalog or not set_id:
        return ()
    return tuple(_effect_from_any(effect) for effect in set_effect_catalog.get(set_id, ()))


def _effect_from_any(effect: Mapping[str, Any] | SetEffect) -> SetEffect:
    if isinstance(effect, SetEffect):
        return effect
    return SetEffect(
        stat=normalize_fribbels_stat(str(effect["stat"])),
        value=float(effect["value"]),
        coverage=float(effect.get("coverage", 1.0)),
        weight=None if effect.get("weight") is None else float(effect["weight"]),
    )


def _clamp_weight(value: float) -> float:
    return min(1.0, max(0.0, value))


