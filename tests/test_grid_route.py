from pathlib import Path

import pytest

from playsage.grid_route import Board, actions_for, keys_for, solve


def test_live_first_board_route_visits_all_targets_without_revisiting():
    board = Board(
        5,
        6,
        frozenset({(1, 0), (1, 4), (3, 1), (3, 5)}),
        frozenset({(0, 2), (1, 2), (2, 1), (2, 4), (3, 3), (4, 3)}),
        (4, 1),
    )
    prefix = [(0, 4), (0, 3), (0, 2)]
    route = solve(board, prefix)
    assert route[:3] == prefix and route[-1] == board.end
    assert board.targets <= set(route)
    assert len(route) == len(set(route))
    assert not board.blocked & set(route)
    assert len(keys_for(route)) == len(route) - 1


def test_disconnected_target_is_rejected():
    with pytest.raises(ValueError, match="no route"):
        solve(Board(2, 3, frozenset({(0, 1), (1, 1)}), frozenset({(0, 2)}), (1, 0)), [(0, 0)])


def test_early_end_and_revisited_prefix_are_rejected():
    board = Board(2, 3, frozenset(), frozenset({(0, 2)}), (1, 0))
    with pytest.raises(ValueError, match="no route"):
        solve(board, [(0, 0), (1, 0)])
    with pytest.raises(ValueError, match="revisits"):
        solve(board, [(0, 0), (0, 1), (0, 0)])


def test_search_budget_is_enforced():
    with pytest.raises(RuntimeError, match="budget"):
        solve(Board(2, 3, frozenset(), frozenset({(0, 2)}), (1, 0)), [(0, 0)], max_nodes=1)


def test_numbered_targets_must_be_collected_in_order():
    order = ((0, 2), (1, 0))
    board = Board(3, 3, frozenset(), frozenset(order), (2, 2), ordered_targets=order)
    route = solve(board, [(0, 0)])
    assert tuple(cell for cell in route if cell in board.targets) == order
    with pytest.raises(ValueError, match="target order"):
        solve(board, [(0, 0), (1, 0)])


def test_ports_constrain_both_entry_and_exit():
    board = Board(3, 3, frozenset(), frozenset({(1, 1)}), (2, 2), {(1, 1): "ws"})
    route = solve(board, [(0, 0)])
    index = route.index((1, 1))
    assert route[index - 1][1] == route[index + 1][1] == 1
    assert not board.allows((1, 0), (1, 1))
    assert not board.allows((1, 1), (1, 2))


def test_quick_channels_force_exit_and_combine_automatic_edges():
    board = Board(2, 4, frozenset(), frozenset({(0, 3)}), (1, 3),
                  forced={(0, 1): "d", (0, 2): "d"})
    assert not board.allows((0, 2), (0, 1))
    assert not board.allows((0, 1), (1, 1))
    route = solve(board, [(0, 0)])
    assert list(actions_for(board, route, 1)) == [
        ("d", [(0, 1), (0, 2), (0, 3)]), ("s", [(1, 3)])
    ]
    with pytest.raises(ValueError, match="settles"):
        board.validate([(0, 0), (0, 1)])


def test_rotation_changes_ports_clockwise_and_validates_prefix():
    board = Board(
        3, 3, frozenset(), frozenset({(1, 2)}), (2, 2), {(1, 1): "ws"}, frozenset({(1, 0)})
    )
    assert not board.allows((1, 0), (1, 1), 0)
    assert board.allows((1, 0), (1, 1), 1)
    route = solve(board, [(0, 0), (1, 0)])
    assert route[-1] == (2, 2) and (1, 2) in route
    board.validate(route)


def test_teleport_crosses_barrier_and_groups_jump_without_extra_key():
    board = Board(2, 4, frozenset({(0, 2), (1, 2)}), frozenset({(0, 3)}), (1, 3),
                  teleports={(0, 1): (1, 0), (1, 0): (0, 1)})
    with pytest.raises(ValueError, match="no route"):
        solve(board, [(0, 0)])
    board = Board(2, 4, frozenset({(0, 2), (1, 2)}), frozenset({(0, 3)}), (1, 1),
                  teleports={(0, 1): (1, 3), (1, 3): (0, 1),
                             (0, 3): (1, 0), (1, 0): (0, 3)})
    # Targets cannot be portal tiles; fail closed on malformed observations.
    with pytest.raises(ValueError, match="overlaps"):
        solve(board, [(0, 0)])
    # Use a disconnected exit tile without treating it as an input direction.
    board = Board(2, 5, frozenset({(0, 2), (1, 2)}), frozenset({(0, 4)}), (1, 4),
                  teleports={(0, 1): (0, 3), (0, 3): (0, 1)})
    route = solve(board, [(0, 0)])
    assert next(iter(actions_for(board, route, 1))) == ("d", [(0, 1), (0, 3)])
    assert route[-1] == (1, 4) and (0, 4) in route
    board.validate(route[:3])
    with pytest.raises(ValueError, match="teleport settles"):
        board.validate(route[:2])


@pytest.mark.parametrize(
    "path",
    sorted(
        (Path(__file__).resolve().parents[1] / "event_packs/zzz/cyber-healer/boards").glob("*.json")
    ),
)
def test_saved_live_boards_have_valid_complete_routes(path):
    import json

    spec = json.loads(path.read_text("utf-8"))
    board = Board(
        spec["rows"],
        spec["columns"],
        frozenset(map(tuple, spec["blocked"] + spec.get("excluded", []))),
        frozenset(map(tuple, spec["targets"])),
        tuple(spec["end"]),
        {tuple(item["cell"]): item["ports"] for item in spec.get("ports", [])},
        frozenset(map(tuple, spec.get("rotations", []))),
        tuple(map(tuple, spec.get("ordered_targets", []))),
        {tuple(item["cell"]): item["key"] for item in spec.get("forced", [])},
        {tuple(a): tuple(b) for pair in spec.get("teleports", []) for a, b in (pair, pair[::-1])},
    )
    route = solve(board, list(map(tuple, spec["prefix"])))
    board.validate(route)
    assert route[-1] == board.end
    assert board.targets <= set(route)
    if board.ordered_targets:
        assert tuple(cell for cell in route if cell in board.targets) == board.ordered_targets
