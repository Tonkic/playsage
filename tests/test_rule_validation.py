import copy
import json
from pathlib import Path

import pytest
from test_evidence import observation

from playsage.evidence import EvidenceStore
from playsage.grid_route import Board, actions_for, advance, solve
from playsage.rule_validation import BoardSpec, state_for, validate_grid


@pytest.fixture
def validation(tmp_path):
    store = EvidenceStore(tmp_path)
    context = {"event_id": "zzz.test", "package_digest": "a" * 64,
               "game_version": "test-v1", "resolution": [8, 6]}
    before = store.import_observation(observation(tmp_path)[0], "run1", context)[0]
    after = store.import_observation(observation(tmp_path, "after")[0], "run1", context)[0]
    data = {"schema_version": 1, "context": context,
            "board": {"rows": 1, "columns": 3, "end": [0, 2]},
            "interactions": [{"prefix": [[0, 0]], "action": "d",
                              "before_ref": before["ref"], "after_ref": after["ref"],
                              "annotation_source": "manual test annotation",
                              "observed": {"prefix": [[0, 0], [0, 1]], "position": [0, 1],
                                           "collected": [], "turns": 0, "complete": False}}]}
    return store, data


def test_match_mismatch_and_missing_are_distinct(validation):
    store, data = validation
    match = validate_grid(data, store)
    assert match["status"] == "match" and match["success"]
    assert match["mode"] == "offline_annotation_check" and not match["replay_allowed"]
    assert match["goal_status"] == "not_evaluated"
    assert len(match["engine_sha256"]) == len(match["board_sha256"]) == 64
    data["interactions"][0]["observed"]["position"] = [0, 0]
    mismatch = validate_grid(data, store)
    assert mismatch["status"] == "mismatch"
    assert "position" in mismatch["results"][0]["differences"]
    data["interactions"][0]["after_ref"] = None
    assert validate_grid(data, store)["status"] == "insufficient_evidence"


@pytest.mark.parametrize("mutation", ["state", "partial", "source", "same", "missing", "unknown",
                                      "context", "unknown_rule", "boolean_dimension", "bad_key"])
def test_insufficient_evidence_never_matches(validation, mutation):
    store, data = validation
    step = data["interactions"][0]
    if mutation == "state":
        step["observed"] = None
    elif mutation == "partial":
        del step["observed"]["complete"]
    elif mutation == "source":
        step["annotation_source"] = None
    elif mutation == "same":
        step["after_ref"] = step["before_ref"]
    elif mutation == "missing":
        step["after_ref"] = "run1/missing"
    elif mutation == "unknown":
        data["context"]["game_version"] = "unknown"
    elif mutation == "context":
        data["context"]["package_digest"] = "b" * 64
    elif mutation == "unknown_rule":
        data["board"]["gravity"] = True
    elif mutation == "boolean_dimension":
        data["board"]["rows"] = True
    elif mutation == "bad_key":
        step["action"] = "execute_python"
    result = validate_grid(data, store)
    assert result["status"] == "insufficient_evidence" and not result["success"]
    assert not result["replay_allowed"]


def test_multiple_samples_report_individually(validation):
    store, data = validation
    mismatch = copy.deepcopy(data["interactions"][0])
    mismatch["observed"]["turns"] = 1
    missing = copy.deepcopy(mismatch)
    missing["after_ref"] = None
    data["interactions"].extend([mismatch, missing])
    assert validate_grid(data, store)["counts"] == {
        "match": 1, "mismatch": 1, "insufficient_evidence": 1,
    }


def test_forced_teleport_rotation_and_order():
    forced = Board(2, 4, frozenset(), frozenset({(0, 3)}), (1, 3),
                   forced={(0, 1): "d", (0, 2): "d"})
    assert advance(forced, [(0, 0)], "d") == [(0, 0), (0, 1), (0, 2), (0, 3)]
    portal = Board(2, 5, frozenset({(0, 2), (1, 2)}), frozenset({(0, 4)}), (1, 4),
                   teleports={(0, 1): (0, 3), (0, 3): (0, 1)})
    assert advance(portal, [(0, 0)], "d") == [(0, 0), (0, 1), (0, 3)]
    rotation = Board(3, 3, frozenset(), frozenset({(1, 2)}), (2, 2),
                     ports={(1, 1): "ws"}, rotations=frozenset({(1, 0)}))
    route = advance(rotation, [(0, 0)], "s")
    assert state_for(rotation, route)["turns"] == 1
    assert advance(rotation, route, "d")[-1] == (1, 1)
    ordered = Board(3, 3, frozenset(), frozenset({(0, 2), (1, 0)}), (2, 2),
                    ordered_targets=((0, 2), (1, 0)))
    with pytest.raises(ValueError, match="order"):
        advance(ordered, [(0, 0)], "s")
    with pytest.raises(ValueError):
        advance(forced, [(0, 0)], "a")
    with pytest.raises(ValueError, match="end"):
        advance(Board(1, 3, frozenset(), frozenset({(0, 2)}), (0, 1)), [(0, 0)], "d")


@pytest.mark.parametrize("path", sorted(
    (Path(__file__).resolve().parents[1] / "event_packs/zzz/cyber-healer/boards").glob("*.json")
))
def test_advance_matches_existing_solver_on_saved_boards(path):
    spec = json.loads(path.read_text("utf-8"))
    accepted = set(BoardSpec.model_fields)
    board = BoardSpec.model_validate({k: v for k, v in spec.items() if k in accepted}).board()
    prefix = list(map(tuple, spec["prefix"]))
    route = solve(board, prefix)
    for key, cells in actions_for(board, route, len(prefix)):
        predicted = advance(board, prefix, key)
        assert predicted == prefix + cells
        prefix = predicted
    assert prefix == route


def test_forced_and_portal_report_matches(validation):
    store, data = validation
    data["board"] = {"rows": 2, "columns": 4, "end": [1, 3],
                     "forced": [{"cell": [0, 1], "key": "d"}]}
    step = data["interactions"][0]
    step["observed"] = {"prefix": [[0, 0], [0, 1], [0, 2]], "position": [0, 2],
                        "collected": [], "turns": 0, "complete": False}
    assert validate_grid(data, store)["status"] == "match"
    data["board"] = {"rows": 2, "columns": 4, "end": [1, 3],
                     "teleports": [[[0, 1], [0, 3]]]}
    step["observed"].update(prefix=[[0, 0], [0, 1], [0, 3]], position=[0, 3])
    assert validate_grid(data, store)["status"] == "match"


@pytest.mark.parametrize("multiple_images", [False, True])
def test_one_observation_cannot_supply_independent_after_frame(validation, multiple_images):
    store, data = validation
    step = data["interactions"][0]
    before, _, _ = store.frame(step["before_ref"])
    source = Path(before["source"])
    if multiple_images:
        record = json.loads(source.read_text("utf-8"))
        record["images"].append(copy.deepcopy(record["images"][0]))
        source.write_text(json.dumps(record), encoding="utf-8")
        frames = store.import_observation(source, "run1", data["context"])
        step["before_ref"], step["after_ref"] = [frame["ref"] for frame in frames]
    else:
        step["after_ref"] = store.import_observation(source, "run1", data["context"])[0]["ref"]
    assert step["before_ref"] != step["after_ref"]
    result = validate_grid(data, store)
    assert result["status"] == "insufficient_evidence"
    assert not result["success"] and not result["replay_allowed"]
    assert "duplicate original observation" in json.dumps(result)


def test_independent_observations_can_have_identical_pixels(validation):
    store, data = validation
    step = data["interactions"][0]
    before, _, _ = store.frame(step["before_ref"])
    after, _, _ = store.frame(step["after_ref"])
    assert before["sha256"] == after["sha256"]
    assert before["source_sha256"] != after["source_sha256"]
    assert validate_grid(data, store)["status"] == "match"
