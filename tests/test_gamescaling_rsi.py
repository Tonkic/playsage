import json

import pytest

from playsage.gamescaling_rsi import (
    ActionRecord,
    CaseResult,
    EpisodeRecord,
    EvaluationRecord,
    FailureRecord,
    FrameRecord,
    ModelVersionRecord,
    RsiStore,
    TakeoverRecord,
)


def episode(episode_id="ep1", outcome="failure"):
    return EpisodeRecord(
        episode_id=episode_id,
        game="zzz",
        task="synthetic navigation",
        model_version="s3-base",
        outcome=outcome,
        goal_progress=0.2,
        min_confidence=0.3,
        parse_failures=1,
        stuck_events=1,
        frames=[FrameRecord(frame_id=f"{episode_id}-f", t_ms=0, ref=f"evidence/{episode_id}/f")],
        actions=[ActionRecord(action_id=f"{episode_id}-a", t_ms=0, parse_error=True)],
        failures=[
            FailureRecord(failure_id=f"{episode_id}-failure", type="stuck", t_ms=100),
        ],
    )


def evaluation(evaluation_id, model_version, successes, parse_failures=None, unsafe=None):
    parse_failures = parse_failures or [0] * len(successes)
    unsafe = unsafe or [0] * len(successes)
    return EvaluationRecord(
        evaluation_id=evaluation_id,
        suite_id="fixed-v1",
        model_version=model_version,
        cases=[
            CaseResult(
                case_id=f"case-{index}",
                success=success,
                parse_failures=parse_failures[index],
                unsafe_actions=unsafe[index],
            )
            for index, success in enumerate(successes)
        ],
    )


def test_trajectory_hard_examples_and_external_takeover(tmp_path):
    store = RsiStore(tmp_path)
    source = tmp_path / "trajectory.jsonl"
    source.write_text(json.dumps(episode().model_dump()) + "\n", encoding="utf-8")

    imported = store.import_trajectory(source)
    assert [item.episode_id for item in imported] == ["ep1"]
    store.record_takeover(TakeoverRecord(
        takeover_id="takeover-1",
        episode_id="ep1",
        start_ms=200,
        end_ms=500,
        reason="stuck",
    ))

    result = store.hard_examples()
    assert result["historical_only"]
    assert result["examples"][0]["episode_id"] == "ep1"
    assert "human_takeover" in result["examples"][0]["reasons"]
    assert (tmp_path / "runs" / "gamescaling_rsi" / "episodes.jsonl").exists()


def test_champion_challenger_promotion_requires_fixed_suite(tmp_path):
    store = RsiStore(tmp_path)
    store.register_model(ModelVersionRecord(version="champion", base_model="GameScaling-S3",
                                            role="champion"))
    store.register_model(ModelVersionRecord(version="challenger", base_model="GameScaling-S3",
                                            adapter="lora/zzz", role="challenger"))
    store.record_evaluation(evaluation("eval-champion", "champion", [True, False]))
    store.record_evaluation(evaluation("eval-challenger", "challenger", [True, True]))

    comparison = store.compare_models("champion", "challenger", "fixed-v1")
    assert comparison["decision"] == "promote"
    assert comparison["runtime_switch"] is False
    assert store.promote("champion", "challenger", "fixed-v1")["action"] == "recorded_promotion"
    assert len(store.decisions()) == 1


def test_promotion_rejects_regression_in_safety_metrics(tmp_path):
    store = RsiStore(tmp_path)
    for version in ("champion", "challenger"):
        store.register_model(ModelVersionRecord(version=version, base_model="GameScaling-S3"))
    store.record_evaluation(evaluation("eval-champion", "champion", [True, False]))
    store.record_evaluation(evaluation("eval-challenger", "challenger", [True, True], unsafe=[0, 1]))

    comparison = store.compare_models("champion", "challenger", "fixed-v1")
    assert comparison["decision"] == "reject"
    with pytest.raises(ValueError, match="promotion gates"):
        store.promote("champion", "challenger", "fixed-v1")


def test_duplicate_episode_is_rejected_without_partial_import(tmp_path):
    store = RsiStore(tmp_path)
    store.record_episodes([episode()])
    with pytest.raises(ValueError, match="already exists"):
        store.record_episodes([episode()])
    assert len(store.episodes()) == 1
