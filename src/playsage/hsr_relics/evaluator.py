from __future__ import annotations

from dataclasses import dataclass

from .config import RelicScoringConfig
from .reliquary import ReliquaryImport
from .scoring import RelicScoreBreakdown, RelicScorer


@dataclass(frozen=True)
class RelicEvaluationResult:
    character_id: str
    profile_id: str
    scores: tuple[RelicScoreBreakdown, ...]

    @property
    def candidates(self) -> tuple[RelicScoreBreakdown, ...]:
        return tuple(score for score in self.scores if score.should_continue)


def evaluate_relics_for_character(
    archive: ReliquaryImport,
    config: RelicScoringConfig,
    character_id: str,
    *,
    include_discarded: bool = False,
) -> RelicEvaluationResult:
    profile = config.profile_for_character(character_id)
    scorer = RelicScorer(global_stop_threshold=config.global_stop_threshold)
    threshold = config.effective_threshold(profile)
    scores = []
    for relic in archive.relics:
        if relic.discard and not include_discarded:
            continue
        scores.append(scorer.score(relic, profile, threshold=threshold))
    scores.sort(key=_score_sort_key, reverse=True)
    return RelicEvaluationResult(
        character_id=character_id,
        profile_id=profile.id,
        scores=tuple(scores),
    )


def _score_sort_key(score: RelicScoreBreakdown) -> tuple[bool, float] | tuple[float]:
    if score.scoring_policy == "set_first":
        return (score.matches_target_set, score.full_enhancement_expected_score)
    return (score.full_enhancement_expected_score,)
