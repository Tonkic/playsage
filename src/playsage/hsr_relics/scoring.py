from __future__ import annotations

import math
from dataclasses import dataclass

from .config import BuildProfile, SetEffect
from .constants import (
    GRADE5_HIGH_ROLL,
    GRADE5_MAIN_STAT_MAX,
    GRADE5_MID_ROLL,
    MAX_ENHANCEMENT_BY_RARITY,
    STANDARD_ROLL_VALUE,
    is_cavern_slot,
    is_planar_slot,
    normalize_main_stat,
    normalize_substat_key,
)
from .reliquary import ReliquaryRelic


@dataclass(frozen=True)
class RelicScoreBreakdown:
    relic_uid: str
    profile_id: str
    scoring_policy: str
    matches_target_set: bool
    set_fit_score: float
    main_stat_score: float
    current_substat_score: float
    average_future_substat_score: float
    relic_score: float
    full_enhancement_expected_score: float
    threshold: float
    should_continue: bool
    is_final: bool


class RelicScorer:
    def __init__(self, global_stop_threshold: float = 0.0) -> None:
        self.global_stop_threshold = global_stop_threshold

    def score(
        self,
        relic: ReliquaryRelic,
        profile: BuildProfile,
        threshold: float | None = None,
    ) -> RelicScoreBreakdown:
        effective_threshold = self.global_stop_threshold if threshold is None else threshold
        matches_target_set = self.matches_target_set(relic, profile)
        accepts_main_stat = self.accepts_main_stat(relic, profile)
        set_fit_score = self.set_fit_score(relic, profile)
        main_stat_score = self.main_stat_score(relic, profile)
        current_substat_score = self.current_substat_score(relic, profile)
        average_future_substat_score = self.average_future_substat_score(relic, profile)
        set_score = set_fit_score if profile.set_score_policy == "scored" else 0.0
        relic_score = set_score + main_stat_score + current_substat_score
        full_score = set_score + main_stat_score + average_future_substat_score
        is_final = relic.level >= MAX_ENHANCEMENT_BY_RARITY.get(relic.rarity, 15)
        passes_profile_gates = (
            (matches_target_set or not profile.require_target_set)
            and (accepts_main_stat or not profile.require_main_stat)
        )
        return RelicScoreBreakdown(
            relic_uid=relic.uid,
            profile_id=profile.id,
            scoring_policy=profile.scoring_policy,
            matches_target_set=matches_target_set,
            set_fit_score=set_fit_score,
            main_stat_score=main_stat_score,
            current_substat_score=current_substat_score,
            average_future_substat_score=average_future_substat_score,
            relic_score=relic_score,
            full_enhancement_expected_score=full_score,
            threshold=effective_threshold,
            should_continue=(
                (not is_final)
                and full_score >= effective_threshold
                and passes_profile_gates
                and (profile.scoring_policy != "set_first" or matches_target_set)
            ),
            is_final=is_final,
        )

    def matches_target_set(self, relic: ReliquaryRelic, profile: BuildProfile) -> bool:
        if is_cavern_slot(relic.slot):
            return bool(profile.target_sets.cavern) and relic.set_id == profile.target_sets.cavern
        if is_planar_slot(relic.slot):
            return bool(profile.target_sets.planar) and relic.set_id == profile.target_sets.planar
        return False

    def set_fit_score(self, relic: ReliquaryRelic, profile: BuildProfile) -> float:
        if is_cavern_slot(relic.slot) and relic.set_id == profile.target_sets.cavern:
            return self.set_effect_score(profile.cavern_set_effects, profile) / 4.0
        if is_planar_slot(relic.slot) and relic.set_id == profile.target_sets.planar:
            return self.set_effect_score(profile.planar_set_effects, profile) / 2.0
        return 0.0

    def accepts_main_stat(self, relic: ReliquaryRelic, profile: BuildProfile) -> bool:
        stat = normalize_main_stat(relic.slot, relic.mainstat)
        return profile.accepts_main_stat(relic.slot, stat)

    def set_effect_score(self, effects: tuple[SetEffect, ...], profile: BuildProfile) -> float:
        total = 0.0
        totals_by_stat: dict[str, float] = {}
        for effect in effects:
            if effect.weight is None:
                previous_units = totals_by_stat.get(effect.stat, 0.0)
                total += potential_units_for_profile(effect.stat, effect.value, profile, previous_units) * _clamp_coverage(effect.coverage)
                totals_by_stat[effect.stat] = previous_units + raw_potential_units(effect.stat, effect.value)
            else:
                total += potential_units(effect.stat, effect.value, effect.weight) * _clamp_coverage(effect.coverage)
        return total

    def main_stat_score(self, relic: ReliquaryRelic, profile: BuildProfile) -> float:
        if profile.main_stat_score_policy == "gate_only":
            return 0.0
        stat = normalize_main_stat(relic.slot, relic.mainstat)
        if not profile.accepts_main_stat(relic.slot, stat):
            return 0.0
        value = GRADE5_MAIN_STAT_MAX.get(relic.slot, {}).get(stat)
        if value is None:
            return 0.0
        return potential_units_for_profile(stat, value, profile)

    def current_substat_score(self, relic: ReliquaryRelic, profile: BuildProfile) -> float:
        total = 0.0
        totals_by_stat: dict[str, float] = {}
        for substat in relic.substats:
            stat = normalize_substat_key(substat.key)
            previous_units = totals_by_stat.get(stat, 0.0)
            total += potential_units_for_profile(stat, substat.value, profile, previous_units)
            totals_by_stat[stat] = previous_units + raw_potential_units(stat, substat.value)
        return total

    def average_future_substat_score(self, relic: ReliquaryRelic, profile: BuildProfile) -> float:
        max_enhance = MAX_ENHANCEMENT_BY_RARITY.get(relic.rarity, 15)
        score, totals_by_stat = self._current_substat_score_with_totals(relic, profile)
        if relic.level >= max_enhance:
            return score

        existing_stats = [normalize_substat_key(sub.key) for sub in relic.substats]
        missing_substats = max(0, 4 - len(existing_stats))
        remaining_upgrade_rolls = math.ceil((max_enhance - relic.level) / 3) - missing_substats
        remaining_upgrade_rolls = max(0, remaining_upgrade_rolls)
        roll_mid_factor = remaining_upgrade_rolls / 4.0

        for stat in existing_stats:
            score += mid_roll_units_for_profile(stat, profile, totals_by_stat.get(stat, 0.0)) * roll_mid_factor

        future_existing_stats = set(existing_stats)
        preview_substats = tuple(relic.preview_substats[:missing_substats])
        for preview in preview_substats:
            stat = normalize_substat_key(preview.key)
            future_existing_stats.add(stat)
            previous_units = totals_by_stat.get(stat, 0.0)
            score += potential_units_for_profile(stat, preview.value, profile, previous_units)
            totals_by_stat[stat] = previous_units + raw_potential_units(stat, preview.value)
            score += mid_roll_units_for_profile(stat, profile, totals_by_stat.get(stat, 0.0)) * roll_mid_factor

        missing_substats -= len(preview_substats)
        if missing_substats:
            available = self._available_new_substats(relic, profile, future_existing_stats, totals_by_stat)
            average_new_stat = _average(available)
            score += missing_substats * average_new_stat * (1.0 + roll_mid_factor)

        return score

    def _current_substat_score_with_totals(
        self,
        relic: ReliquaryRelic,
        profile: BuildProfile,
    ) -> tuple[float, dict[str, float]]:
        total = 0.0
        totals_by_stat: dict[str, float] = {}
        for substat in relic.substats:
            stat = normalize_substat_key(substat.key)
            previous_units = totals_by_stat.get(stat, 0.0)
            total += potential_units_for_profile(stat, substat.value, profile, previous_units)
            totals_by_stat[stat] = previous_units + raw_potential_units(stat, substat.value)
        return total, totals_by_stat

    def _available_new_substats(
        self,
        relic: ReliquaryRelic,
        profile: BuildProfile,
        existing_stats: set[str],
        totals_by_stat: dict[str, float] | None = None,
    ) -> list[float]:
        main_stat = normalize_main_stat(relic.slot, relic.mainstat)
        values: list[float] = []
        totals_by_stat = totals_by_stat or {}
        for stat in GRADE5_HIGH_ROLL:
            if stat == main_stat or stat in existing_stats:
                continue
            values.append(mid_roll_units_for_profile(stat, profile, totals_by_stat.get(stat, 0.0)))
        return values


def raw_potential_units(stat: str, value: float) -> float:
    standard_roll = STANDARD_ROLL_VALUE.get(stat)
    if standard_roll is None or standard_roll <= 0:
        return 0.0
    return float(value) / standard_roll


def potential_units(stat: str, value: float, weight: float) -> float:
    return raw_potential_units(stat, value) * _clamp_weight(weight)


def potential_units_for_profile(
    stat: str,
    value: float,
    profile: BuildProfile,
    starting_units: float = 0.0,
) -> float:
    raw_units = raw_potential_units(stat, value)
    if raw_units <= 0:
        return 0.0
    return weighted_units_for_profile(stat, raw_units, profile, starting_units)


def weighted_units_for_profile(
    stat: str,
    raw_units: float,
    profile: BuildProfile,
    starting_units: float = 0.0,
) -> float:
    if raw_units <= 0:
        return 0.0
    rules = profile.stat_weight_rules.get(stat)
    if not rules:
        return raw_units * profile.effective_weight(stat)

    score = 0.0
    cursor = starting_units
    remaining = raw_units
    sorted_rules = tuple(sorted(rules, key=lambda rule: rule.after_units))
    while remaining > 1e-9:
        weight = profile.effective_weight_at_units(stat, cursor)
        next_after = next((rule.after_units for rule in sorted_rules if rule.after_units > cursor), math.inf)
        span = min(remaining, next_after - cursor)
        if not math.isfinite(span) or span <= 0:
            span = remaining
        score += span * weight
        cursor += span
        remaining -= span
    return score


def mid_roll_units(stat: str, weight: float) -> float:
    value = GRADE5_MID_ROLL.get(stat)
    if value is None:
        return 0.0
    return potential_units(stat, value, weight)


def mid_roll_units_for_profile(stat: str, profile: BuildProfile, starting_units: float = 0.0) -> float:
    value = GRADE5_MID_ROLL.get(stat)
    if value is None:
        return 0.0
    return potential_units_for_profile(stat, value, profile, starting_units)


def _clamp_weight(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _clamp_coverage(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
