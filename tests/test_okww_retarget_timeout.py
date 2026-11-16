"""Opt-in offline timing tests; never import the installed game backend."""
from types import MethodType, SimpleNamespace

import pytest
import test_okww_swipe

installed_root = test_okww_swipe.installed_root


class LoopOverrun(Exception):
    pass


class Clock:
    def __init__(self, mode):
        self.now = 0.0
        self.mode = mode

    def monotonic(self):
        return self.now

    def time(self):
        if self.mode == "frozen":
            return 1000.0
        offset = 0.0
        if self.now >= 0.4:
            offset = {"backward": -3600.0, "forward": 3600.0}.get(self.mode, 0.0)
        return 1000.0 + self.now + offset


def make_task(installed_root, mode="normal"):
    clock = Clock(mode)
    clicks = []
    frames = []

    def click(interval=None):
        # Test watchdog only: abort instead of spending time in a broken loop.
        if len(clicks) >= 20:
            raise LoopOverrun("configured timeout did not stop repeated input")
        clicks.append(interval)
        clock.now += 0.2

    method = test_okww_swipe.load_method(
        installed_root, "src/combat/CombatCheck.py", "CombatCheck", "target_enemy",
        {"time": clock, "logger": SimpleNamespace(info=lambda message: None)},
    )
    task = SimpleNamespace(
        target_enemy_time_out=1.0,
        has_target=lambda: False,
        middle_click=click,
        next_frame=lambda: frames.append(clock.now),
        check_health_bar=lambda: False,
    )
    task.target_enemy = MethodType(method, task)
    return task, clock, clicks, frames


@pytest.mark.parametrize("mode", ["normal", "backward", "forward", "frozen"])
def test_retarget_timeout_uses_elapsed_time(installed_root, mode):
    task, clock, clicks, frames = make_task(installed_root, mode)
    assert task.target_enemy() is False
    assert clock.now == pytest.approx(1.0)
    assert clicks == [0.2] * 5
    assert len(frames) == 5


@pytest.mark.parametrize("mode", ["normal", "backward", "forward", "frozen"])
def test_health_loss_grace_uses_elapsed_time(installed_root, mode):
    task, clock, clicks, _ = make_task(installed_root, mode)
    assert task.target_enemy(time_out=10, check_health=True) is False
    # Preserve the existing >1.2-second grace, including one polling interval.
    assert 1.4 <= clock.now <= 1.8
    assert 7 <= len(clicks) <= 9


@pytest.mark.parametrize("timeout,click_count", [(0, 0), (0.6, 3), (1.0, 5)])
def test_explicit_timeout_overrides_default(installed_root, timeout, click_count):
    task, clock, clicks, _ = make_task(installed_root)
    task.target_enemy_time_out = 10
    assert task.target_enemy(time_out=timeout) is False
    assert len(clicks) == click_count
    assert clock.now == pytest.approx(timeout)


def test_existing_target_never_clicks(installed_root):
    task, _, clicks, frames = make_task(installed_root)
    task.has_target = lambda: True
    assert task.target_enemy() is True
    assert clicks == []
    assert frames == []


def test_target_acquired_stops_without_extra_input(installed_root):
    task, clock, clicks, frames = make_task(installed_root)
    task.has_target = lambda: clock.now >= 0.4
    assert task.target_enemy() is True
    assert clicks == [0.2, 0.2]
    assert frames == [0.2]


def test_non_waiting_behavior_is_unchanged(installed_root):
    task, _, clicks, frames = make_task(installed_root)
    assert task.target_enemy(wait=False) is None
    assert clicks == [None]
    assert frames == []


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt])
def test_frame_failure_or_cancellation_stops_retargeting(installed_root, failure):
    task, _, clicks, _ = make_task(installed_root)
    original = failure("observation interrupted")

    def fail_frame():
        raise original

    task.next_frame = fail_frame
    with pytest.raises(failure) as caught:
        task.target_enemy()
    assert caught.value is original
    assert clicks == [0.2]
