
from playsage.hsr_relics import HSR_RELIC_DATABASE, HSR_RELIC_SCORING
from playsage.hsr_relics.config import BuildProfile, TargetSetPlan
from playsage.hsr_relics.reliquary import ReliquaryRelic, ReliquarySubstat
from playsage.hsr_relics.scoring import RelicScorer


def test_migrated_hsr_data_and_config_are_present() -> None:
    assert (HSR_RELIC_DATABASE / "manifest.json").is_file()
    assert (HSR_RELIC_DATABASE / "relic_sets.json").is_file()
    assert (HSR_RELIC_SCORING / "relic_scoring.fribbels.generated.yaml").is_file()
    assert (HSR_RELIC_SCORING / "relic_scoring.overrides.yaml").is_file()


def test_relic_scorer_keeps_protected_identity_fields_and_scores_preview() -> None:
    profile = BuildProfile(
        id="test",
        target_sets=TargetSetPlan(cavern="set-a", planar="set-b"),
        stat_weights={"CRIT Rate": 1.0, "CRIT DMG": 1.0},
        main_stats={"Body": ("CRIT Rate",)},
    )
    relic = ReliquaryRelic(
        uid="relic-1",
        set_id="set-a",
        name="test",
        slot="Body",
        rarity=5,
        level=0,
        mainstat="CRIT Rate",
        substats=(ReliquarySubstat("CRIT DMG", 16.0),),
        preview_substats=(ReliquarySubstat("CRIT Rate", 3.2),),
        location="",
        lock=True,
        discard=False,
    )

    result = RelicScorer().score(relic, profile, threshold=0)

    assert result.relic_uid == "relic-1"
    assert result.matches_target_set is True
    assert result.full_enhancement_expected_score >= result.relic_score
    assert relic.lock is True
