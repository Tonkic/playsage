"""Offline Honkai: Star Rail relic scoring migrated from RelicForge."""

from pathlib import Path

from .catalog import GameDataCatalog, RelicSetInfo
from .config import BuildProfile, RelicScoringConfig, SetEffect, TargetSetPlan
from .evaluator import RelicEvaluationResult, evaluate_relics_for_character
from .fribbels import (
    apply_profile_override,
    build_config_from_fribbels_metadata,
    build_profile_from_fribbels_metadata,
    normalize_fribbels_slot,
    normalize_fribbels_stat,
)
from .reliquary import (
    ReliquaryCharacter,
    ReliquaryImport,
    ReliquaryRelic,
    ReliquarySubstat,
    load_reliquary_import,
)
from .scoring import RelicScoreBreakdown, RelicScorer

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
HSR_DATA_ROOT = PACKAGE_ROOT / "data" / "hsr"
HSR_RELIC_DATABASE = HSR_DATA_ROOT / "relic_database"
HSR_RELIC_SCORING = PACKAGE_ROOT / "game_packs" / "hsr" / "relic_scoring"

__all__ = [
    "HSR_DATA_ROOT",
    "HSR_RELIC_DATABASE",
    "HSR_RELIC_SCORING",
    "BuildProfile",
    "GameDataCatalog",
    "RelicEvaluationResult",
    "RelicScoreBreakdown",
    "RelicScorer",
    "RelicScoringConfig",
    "RelicSetInfo",
    "ReliquaryCharacter",
    "ReliquaryImport",
    "ReliquaryRelic",
    "ReliquarySubstat",
    "SetEffect",
    "TargetSetPlan",
    "apply_profile_override",
    "build_config_from_fribbels_metadata",
    "build_profile_from_fribbels_metadata",
    "evaluate_relics_for_character",
    "load_reliquary_import",
    "normalize_fribbels_slot",
    "normalize_fribbels_stat",
]
