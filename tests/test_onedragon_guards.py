import asyncio
import importlib
import time
from types import SimpleNamespace

import pytest
from PIL import Image


@pytest.fixture
def native(monkeypatch):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    return importlib.import_module("onedragon_step")


def snapshot(tmp_path, name, color=(30, 50, 70)):
    path = tmp_path / name
    Image.new("RGB", (1920, 1080), color).save(path)
    return {
        "captured_at": time.time(),
        "screenshot": str(path),
        "window": {
            "win_title": "绝区零",
            "x": 0,
            "y": 0,
            "width": 2560,
            "height": 1440,
            "is_win_active": True,
        },
        "analysis": {"screens": []},
    }


def test_foreground_and_geometry_changes_block_input(native, tmp_path):
    before = snapshot(tmp_path, "before.png")
    current = snapshot(tmp_path, "current.png")
    current["window"]["is_win_active"] = False
    with pytest.raises(ValueError, match="foreground"):
        native.verify_transition(before, current, SimpleNamespace(command="key"))
    current["window"]["is_win_active"] = True
    current["window"]["width"] = 1920
    with pytest.raises(ValueError, match="geometry"):
        native.verify_transition(before, current, SimpleNamespace(command="key"))


def test_changed_click_target_is_rejected(native, tmp_path):
    before = snapshot(tmp_path, "before.png")
    after = snapshot(tmp_path, "after.png", (255, 255, 255))
    with pytest.raises(ValueError, match="appearance"):
        native.verify_transition(before, after, SimpleNamespace(command="click", x=100, y=100))


def test_animated_click_requires_unique_nearby_stationary_anchor(native, tmp_path):
    before = snapshot(tmp_path, "before.png")
    after = snapshot(tmp_path, "after.png", (255, 255, 255))
    label = {"text": "限时奖励", "x": 80, "y": 140, "width": 40, "height": 20}
    before["analysis"]["ocr_texts"] = [label.copy()]
    after["analysis"]["ocr_texts"] = [label.copy()]
    args = SimpleNamespace(command="click", x=100, y=100, anchor="限时奖励")
    native.verify_transition(before, after, args)
    after["analysis"]["ocr_texts"].append(label.copy())
    with pytest.raises(ValueError, match="ambiguous"):
        native.verify_transition(before, after, args)
    after["analysis"]["ocr_texts"] = [{**label, "x": 90}]
    with pytest.raises(ValueError, match="moved"):
        native.verify_transition(before, after, args)
    after["analysis"]["ocr_texts"] = [{**label, "x": 500}]
    with pytest.raises(ValueError, match="too far"):
        native.verify_transition(before, after, args)


def test_backend_refused_input_is_not_accepted(native, monkeypatch):
    async def refused(*_args):
        return {"in_window": False}

    monkeypatch.setattr(native, "call", refused)
    with pytest.raises(RuntimeError, match="refused"):
        asyncio.run(native.bounded_input(None, "key_tap", {"key": "w", "press_time": 0.12}))


def test_cancel_waits_for_bounded_input_completion(native, monkeypatch):
    async def scenario():
        started, finished = asyncio.Event(), asyncio.Event()

        async def fake_call(*_args):
            started.set()
            await asyncio.sleep(0.02)
            finished.set()
            return {"success": True}

        monkeypatch.setattr(native, "call", fake_call)
        task = asyncio.create_task(native.bounded_input(None, "key_tap", {"press_time": 0.12}))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(scenario())


def test_grid_counter_and_position_mismatch_fail_closed(native, tmp_path):
    repair = importlib.import_module("repair_grid")
    from playsage.grid_route import Board

    record = snapshot(tmp_path, "grid.png")
    record["analysis"]["ocr_texts"] = [{"text": "当前关卡：1/4"}, {"text": "00/01"}]
    spec = {"stage": 1, "xs": [1141, 1262], "ys": [329]}
    board = Board(1, 2, frozenset(), frozenset({(0, 1)}), (0, 1))
    with pytest.raises(ValueError, match="position mismatch"):
        repair.check_board(record, record, spec, board, [(0, 0)])
    record["analysis"]["ocr_texts"][1]["text"] = "01/01"
    with pytest.raises(ValueError, match="counter mismatch"):
        repair.check_board(record, record, spec, board, [(0, 0)])
