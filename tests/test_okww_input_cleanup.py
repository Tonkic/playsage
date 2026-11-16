"""Offline checks of trusted installed input code; no OS input is executed."""

import ast
import sys
from types import ModuleType, SimpleNamespace

import pytest
import test_okww_swipe

# Reuse the opt-in installation fixture without duplicating path handling.
installed_root = test_okww_swipe.installed_root


class InputFailure(Exception):
    pass


class Recorder:
    def __init__(self):
        self.events = []
        self.held = False
        self.focused = True
        self.position_value = (10, 20)
        self.failure = None
        self.fail_stage = None
        self.after_sleep = None
        self.release_failure = None

    @property
    def position(self):
        return self.position_value

    @position.setter
    def position(self, point):
        self.events.append(("move", point))
        self.position_value = point

    def press(self, key):
        self.events.append(("down", key))
        self.held = True
        if self.fail_stage == "press":
            raise self.failure("press failed")

    def release(self, key):
        self.events.append(("up", key))
        if self.release_failure is not None:
            raise self.release_failure
        self.held = False
        if self.fail_stage == "release":
            raise self.failure("release failed")

    def sleep(self, seconds):
        self.events.append(("sleep", seconds))
        if self.after_sleep:
            self.after_sleep()
        if self.held and self.fail_stage == "sleep":
            raise self.failure("sleep interrupted")


@pytest.fixture(params=["post_message", "pynput"])
def backend(request, installed_root, monkeypatch):
    name = request.param
    record = Recorder()
    constants = SimpleNamespace(
        WM_LBUTTONDOWN=1, WM_LBUTTONUP=2, MK_LBUTTON=1,
        WM_MBUTTONDOWN=3, WM_MBUTTONUP=4, MK_MBUTTON=16,
        WM_RBUTTONDOWN=5, WM_RBUTTONUP=6, MK_RBUTTON=2,
    )
    messages = []
    failures = {}

    def post(hwnd, message, wparam, lparam):
        messages.append((hwnd, message, wparam, lparam))
        if message in failures:
            raise failures[message]
        if message in (1, 3, 5):
            record.press(message)
        elif message in (2, 4, 6):
            record.release(message)

    class Base:
        hwnd = 123

        def click(self, *args, **kwargs):
            pass

        def send_key(self, *args, **kwargs):
            pass

        def send_key_down(self, key):
            record.press(key)

        def send_key_up(self, key):
            record.release(key)

        def clickable(self):
            return record.focused

        def _key_controller(self, key):
            return record, key

        def get_mouse_button(self, key):
            return key

        def move(self, x, y):
            record.position = (x, y)
            return (x, y)

        def update_mouse_pos(self, x, y, activate=True):
            return (x, y)

    fake_pynput = ModuleType("pynput")
    fake_pynput.mouse = SimpleNamespace(Controller=lambda: record)
    monkeypatch.setitem(sys.modules, "pynput", fake_pynput)
    path = installed_root / f"ok/device/interaction_methods/{name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    class_name = "PostMessageInteraction" if name == "post_message" else "PynputInteraction"
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == class_name)
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in {"click", "send_key", "post"}]
    isolated = ast.ClassDef(name=class_name, bases=[ast.Name(id="Base", ctx=ast.Load())],
                           keywords=[], body=methods, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[isolated], type_ignores=[]))
    namespace = {
        "Base": Base, "time": SimpleNamespace(sleep=record.sleep),
        "win32con": constants, "win32gui": SimpleNamespace(PostMessage=post),
        "logger": SimpleNamespace(error=lambda *args: None, info=lambda *args: None),
    }
    # Selected methods of a trusted installation only; this is not a sandbox.
    exec(compile(module, str(path), "exec"), namespace)  # noqa: S102
    target = namespace[class_name]()
    target.capture = SimpleNamespace(get_abs_cords=lambda x, y: (x + 20, y + 30))
    return SimpleNamespace(name=name, target=target, record=record,
                           messages=messages, failures=failures)


def perform(backend, action, **kwargs):
    if action == "click":
        backend.target.click(100, 200, **kwargs)
    else:
        backend.target.send_key("a", **kwargs)


@pytest.mark.parametrize("action", ["click", "send_key"])
@pytest.mark.parametrize("stage", ["press", "sleep"])
@pytest.mark.parametrize("failure", [InputFailure, KeyboardInterrupt])
def test_interruption_releases_own_press_once(backend, action, stage, failure):
    backend.record.fail_stage = stage
    backend.record.failure = failure
    with pytest.raises(failure):
        perform(backend, action)
    assert [e[0] for e in backend.record.events if e[0] in {"down", "up"}] == ["down", "up"]
    assert not backend.record.held


@pytest.mark.parametrize("action", ["click", "send_key"])
@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), -float("inf")])
def test_invalid_hold_time_is_rejected_before_any_input(backend, action, value):
    with pytest.raises(ValueError):
        perform(backend, action, down_time=value)
    assert backend.record.events == []
    assert backend.messages == []


@pytest.mark.parametrize("action", ["click", "send_key"])
def test_release_error_is_not_reported_as_success(backend, action):
    backend.record.fail_stage = "release"
    backend.record.failure = InputFailure
    with pytest.raises(InputFailure, match="release failed"):
        perform(backend, action)
    assert sum(e[0] == "up" for e in backend.record.events) == 1


@pytest.mark.parametrize("action", ["click", "send_key"])
def test_normal_hold_time_and_order_unchanged(backend, action):
    perform(backend, action, down_time=0.2)
    events = backend.record.events
    down = next(i for i, event in enumerate(events) if event[0] == "down")
    assert [e[0] for e in events[down:]] == ["down", "sleep", "up"]
    assert events[down + 1] == ("sleep", 0.2)


@pytest.mark.parametrize("button", ["left", "middle", "right"])
def test_click_releases_matching_button_and_coordinates(backend, button):
    backend.target.click(100, 200, key=button, down_time=0)
    if backend.name == "post_message":
        codes = {"left": (1, 2, 1), "middle": (3, 4, 16), "right": (5, 6, 2)}
        down, up, mask = codes[button]
        assert backend.messages == [(123, down, mask, (100, 200)),
                                    (123, up, 0, (100, 200))]
    else:
        assert backend.record.position == (120, 230)
        assert [event for event in backend.record.events if event[0] in {"down", "up"}] == [
            ("down", button), ("up", button)
        ]


@pytest.mark.parametrize("stage", ["initial", "before_press", "during_hold"])
def test_pynput_focus_loss_is_explicit_and_sends_no_further_move(backend, stage):
    if backend.name != "pynput":
        pytest.skip("PostMessage supports background input")
    if stage == "initial":
        backend.record.focused = False
    else:
        def lose_focus():
            if stage == "before_press" or backend.record.held:
                backend.record.focused = False
        backend.record.after_sleep = lose_focus
    with pytest.raises(RuntimeError, match="focus"):
        backend.target.click(100, 200, move_back=True)
    assert not backend.record.held
    if stage in {"initial", "before_press"}:
        assert not any(e[0] in {"down", "up"} for e in backend.record.events)
    else:
        assert backend.record.events[-1][0] == "up"
        assert sum(e[0] == "move" for e in backend.record.events) == 1


def test_pynput_key_does_not_silently_succeed_when_unfocused(backend):
    if backend.name != "pynput":
        pytest.skip("PostMessage supports background input")
    backend.record.focused = False
    with pytest.raises(RuntimeError, match="focus"):
        backend.target.send_key("a")
    assert backend.record.events == []


def test_post_failure_propagates_without_retry(backend):
    if backend.name != "post_message":
        pytest.skip("PostMessage-only failure reporting")
    error = InputFailure("invalid window")
    backend.failures[999] = error
    with pytest.raises(InputFailure) as caught:
        backend.target.post(999)
    assert caught.value is error
    assert backend.messages == [(123, 999, 0, 0)]


def test_click_release_stays_on_original_window(backend):
    if backend.name != "post_message":
        pytest.skip("PostMessage-only target window")
    def change_target():
        if backend.record.held:
            backend.target.hwnd = 456
    backend.record.after_sleep = change_target
    backend.target.click(100, 200)
    assert [message[0] for message in backend.messages] == [123, 123]


def test_pynput_move_back_still_works_on_success(backend):
    if backend.name != "pynput":
        pytest.skip("Existing PostMessage click does not move real cursor")
    backend.target.click(100, 200, move_back=True)
    assert backend.record.position == (10, 20)
    assert not backend.record.held


@pytest.mark.parametrize("action", ["click", "send_key"])
@pytest.mark.parametrize("stage", ["press", "sleep"])
@pytest.mark.parametrize("failure", [InputFailure, KeyboardInterrupt])
def test_double_failure_preserves_primary_error_and_release_note(backend, action, stage, failure):
    backend.record.fail_stage = stage
    backend.record.failure = failure
    backend.record.release_failure = InputFailure("release failed too")
    with pytest.raises(failure, match="press failed|sleep interrupted") as caught:
        perform(backend, action)
    assert any("release failed too" in note for note in caught.value.__notes__)
    assert sum(e[0] == "up" for e in backend.record.events) == 1
