"""Opt-in tests of installed OKWW swipe methods; never import an input backend.

Set OKWW_WORKING_DIR to the installation's working directory. Only selected
method ASTs are compiled; time, OS messages and pynput are replaced with fakes.
"""

import ast
import os
import sys
from pathlib import Path
from types import MethodType, ModuleType, SimpleNamespace

import pytest


class InjectedFailure(Exception):
    pass


class Clock:
    def __init__(self):
        self.now = 0.0
        self.after_sleep = None

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        assert seconds >= 0
        self.now += seconds
        if self.after_sleep:
            self.after_sleep()


class InputRecorder:
    def __init__(self, clock):
        self.clock = clock
        self.events = []
        self.held = False
        self.focused = True
        self.move_cost = 0.0
        self.fail_move = None
        self.fail_press = None
        self._position = (0, 0)

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, point):
        self.move(*point)

    def move(self, x, y, down_btn=0):
        if self.held and self.fail_move:
            raise self.fail_move("move interrupted")
        self._position = (x, y)
        self.events.append(("move", self.clock.now, (x, y), self.held, down_btn))
        self.clock.now += self.move_cost

    def press(self, button):
        self.held = True
        self.events.append(("down", self.clock.now, self.position, True))
        if self.fail_press:
            raise self.fail_press("press interrupted")

    def release(self, button):
        self.held = False
        self.events.append(("up", self.clock.now, self.position, False))

    def mouse_down(self, x, y):
        self.press("left")

    def mouse_up(self):
        self.release("left")


def load_method(root, relative, class_name, method_name, namespace):
    path = root / relative
    assert path.is_file(), f"Missing installed source: {path}"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                  and node.name == method_name)
    code = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    # Deliberately execute only this trusted installation's method, with fake I/O.
    exec(compile(code, str(path), "exec"), namespace)  # noqa: S102
    return namespace[method_name]


@pytest.fixture(scope="module")
def installed_root():
    location = os.environ.get("OKWW_WORKING_DIR")
    if not location:
        pytest.skip("Set OKWW_WORKING_DIR for offline installed-backend regression tests")
    root = Path(location)
    assert root.is_dir(), f"Invalid OKWW_WORKING_DIR: {root}"
    return root


@pytest.fixture(params=["post_message", "pynput"])
def backend(request, installed_root, monkeypatch):
    clock = Clock()
    recorder = InputRecorder(clock)
    fake_pynput = ModuleType("pynput")
    fake_pynput.mouse = SimpleNamespace(
        Controller=lambda: recorder, Button=SimpleNamespace(left="left")
    )
    monkeypatch.setitem(sys.modules, "pynput", fake_pynput)
    task = SimpleNamespace(
        move=recorder.move,
        mouse_down=recorder.mouse_down,
        mouse_up=recorder.mouse_up,
        clickable=lambda: recorder.focused,
        capture=SimpleNamespace(get_abs_cords=lambda x, y: (x + 20, y + 30)),
    )
    name = request.param
    method = load_method(
        installed_root, f"ok/device/interaction_methods/{name}.py",
        "PostMessageInteraction" if name == "post_message" else "PynputInteraction",
        "swipe", {"time": clock, "win32con": SimpleNamespace(MK_LBUTTON=1)},
    )
    task.swipe = MethodType(method, task)
    return SimpleNamespace(name=name, clock=clock, input=recorder, task=task)


def assert_released(backend):
    assert [event[0] for event in backend.input.events if event[0] != "move"] == ["down", "up"]
    assert not backend.input.held


@pytest.mark.parametrize("duration", [0, 1, 3, 9, 10, 50, 99, 100, 255, 500, 600, 1000, 3000])
def test_duration_endpoint_and_release(backend, duration):
    backend.task.swipe(100, 100, 600, 400, duration)
    assert_released(backend)
    events = backend.input.events
    down = next(event for event in events if event[0] == "down")
    held_moves = [event for event in events if event[0] == "move" and event[3]]
    endpoint = (620, 430) if backend.name == "pynput" else (600, 400)
    assert held_moves[-1][2] == endpoint
    assert held_moves[-1][1] - down[1] == pytest.approx(duration / 1000)
    assert events[-1][1] - down[1] == pytest.approx(duration / 1000)
    steps = max(1, (duration + 9) // 10)
    assert len(held_moves) == steps
    assert [event[1] - down[1] for event in held_moves] == pytest.approx(
        [duration / 1000 * step / steps for step in range(1, steps + 1)]
    )
    start = (120, 130) if backend.name == "pynput" else (100, 100)
    assert [event[2] for event in held_moves] == [
        (round(start[0] + 500 * step / steps), round(start[1] + 300 * step / steps))
        for step in range(1, steps + 1)
    ]
    if backend.name == "post_message":
        assert [event[4] for event in held_moves] == [1] * steps


@pytest.mark.parametrize("end", [(50, 40), (100, 100), (100, 400), (600, 100)])
def test_reverse_zero_length_and_axis_aligned_drag(backend, end):
    backend.task.swipe(100, 100, *end, 255)
    offset = (20, 30) if backend.name == "pynput" else (0, 0)
    assert backend.input.position == (end[0] + offset[0], end[1] + offset[1])
    assert_released(backend)


def test_settle_holds_at_endpoint_before_release(backend):
    backend.task.swipe(100, 100, 600, 400, 500, settle_time=0.2)
    events = backend.input.events
    last_move = [event for event in events if event[0] == "move"][-1]
    assert events[-1][0] == "up"
    assert events[-1][1] - last_move[1] == pytest.approx(0.2)
    assert_released(backend)


def test_schedule_accounts_for_input_overhead(backend):
    backend.input.move_cost = 0.002
    backend.task.swipe(100, 100, 600, 400, 500)
    events = backend.input.events
    down = next(event for event in events if event[0] == "down")
    last_move = [event for event in events if event[0] == "move"][-1]
    assert last_move[1] - down[1] == pytest.approx(0.5)
    assert events[-1][1] - down[1] == pytest.approx(0.502)


@pytest.mark.parametrize("failure", [InjectedFailure, KeyboardInterrupt])
@pytest.mark.parametrize("stage", ["move", "press", "sleep"])
def test_interruption_always_attempts_release(backend, failure, stage):
    if stage == "move":
        backend.input.fail_move = failure
    elif stage == "press":
        backend.input.fail_press = failure
    else:
        def interrupt():
            if backend.input.held:
                raise failure("sleep interrupted")
        backend.clock.after_sleep = interrupt
    with pytest.raises(failure):
        backend.task.swipe(100, 100, 600, 400, 500)
    assert_released(backend)


@pytest.mark.parametrize("invalid", [-1, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("argument", ["duration", "settle_time"])
def test_invalid_timing_is_rejected_before_input(backend, invalid, argument):
    kwargs = {"duration": 500, "settle_time": 0}
    kwargs[argument] = invalid
    with pytest.raises(ValueError):
        backend.task.swipe(100, 100, 600, 400, **kwargs)
    assert backend.input.events == []


@pytest.mark.parametrize("stage", ["initial", "before_press", "during_drag", "settle"])
def test_pynput_focus_loss_stops_without_stuck_button(backend, stage):
    if backend.name != "pynput":
        pytest.skip("PostMessage is intentionally a background backend")
    if stage == "initial":
        backend.input.focused = False
    else:
        def lose_focus():
            if (stage == "before_press"
                    or (stage == "during_drag" and backend.input.held)
                    or (stage == "settle" and backend.clock.now > 0.65)):
                backend.input.focused = False
        backend.clock.after_sleep = lose_focus
    with pytest.raises(RuntimeError, match="focus"):
        backend.task.swipe(100, 100, 600, 400, 500, settle_time=0.2)
    assert not backend.input.held
    if stage == "initial":
        assert backend.input.events == []
    elif stage == "before_press":
        assert all(event[0] == "move" for event in backend.input.events)
    else:
        assert_released(backend)
        if stage == "during_drag":
            assert not any(event[0] == "move" and event[3] for event in backend.input.events)


def test_task_layer_converts_seconds_to_milliseconds(backend, installed_root):
    class Box:
        def __init__(self, *args, **kwargs):
            pass

    method = load_method(
        installed_root, "ok/task/task.py", "ExecutorOperation", "swipe",
        {"communicate": SimpleNamespace(emit_draw_box=lambda *args: None), "Box": Box},
    )
    task = SimpleNamespace(
        executor=SimpleNamespace(nullable_frame=lambda: None, reset_scene=lambda: None,
                                 interaction=backend.task),
        sleep=backend.clock.sleep,
    )
    method(task, 100, 100, 600, 400, duration=0.5, after_sleep=0.1, settle_time=0.2)
    down = next(event for event in backend.input.events if event[0] == "down")
    assert backend.input.events[-1][1] - down[1] == pytest.approx(0.7)
    assert backend.clock.now == pytest.approx(0.9)
    assert_released(backend)


@pytest.mark.parametrize("failure_type", [InjectedFailure, KeyboardInterrupt])
@pytest.mark.parametrize("stage", ["press", "move", "sleep", "settle"])
def test_swipe_preserves_primary_error_when_release_also_fails(
    backend, monkeypatch, failure_type, stage,
):
    primary_error = failure_type(f"{stage} interrupted")
    release_error = RuntimeError("release dispatch failed")
    release_attempts = []

    def fail_release(button):
        release_attempts.append(button)
        raise release_error

    monkeypatch.setattr(backend.input, "release", fail_release)
    if stage in {"press", "move"}:
        setattr(backend.input, f"fail_{stage}", lambda _message: primary_error)
    else:
        def interrupt():
            if backend.input.held and (stage == "sleep" or backend.clock.now > 0.65):
                raise primary_error
        backend.clock.after_sleep = interrupt

    with pytest.raises(failure_type) as caught:
        backend.task.swipe(100, 100, 600, 400, 500, settle_time=0.2)

    assert caught.value is primary_error
    assert release_attempts == ["left"]
    assert any("release dispatch failed" in note for note in primary_error.__notes__)
    # A failed release attempt must not be mistaken for a confirmed release.
    assert backend.input.held


def test_swipe_release_failure_is_reported_without_retry(backend, monkeypatch):
    release_error = RuntimeError("release dispatch failed")
    release_attempts = []

    def fail_release(button):
        release_attempts.append(button)
        raise release_error

    monkeypatch.setattr(backend.input, "release", fail_release)
    with pytest.raises(RuntimeError) as caught:
        backend.task.swipe(100, 100, 600, 400, 500)
    assert caught.value is release_error
    assert release_attempts == ["left"]
    assert backend.input.held


def test_swipe_focus_error_survives_failed_release(backend, monkeypatch):
    if backend.name != "pynput":
        pytest.skip("PostMessage is intentionally a background backend")
    release_attempts = []

    def fail_release(button):
        release_attempts.append(button)
        raise RuntimeError("release dispatch failed")

    def lose_focus():
        if backend.input.held:
            backend.input.focused = False

    monkeypatch.setattr(backend.input, "release", fail_release)
    backend.clock.after_sleep = lose_focus
    with pytest.raises(RuntimeError, match="focus") as caught:
        backend.task.swipe(100, 100, 600, 400, 500)
    assert release_attempts == ["left"]
    assert any("release dispatch failed" in note for note in caught.value.__notes__)
    assert not any(event[0] == "move" and event[3] for event in backend.input.events)
    assert backend.input.held
