import asyncio
import importlib
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest


class Gone(Exception):
    pass


class Game:
    def __init__(self, path, pid=123):
        self.pid = pid
        self.info = {"pid": pid, "name": "Client-Win64-Shipping.exe"}
        self.path = path
        self.alive = True
        self.created = 100.0

    def exe(self):
        return str(self.path)

    def create_time(self):
        return self.created

    def is_running(self):
        return self.alive


class Runner:
    def __init__(self, device):
        self._lock = threading.RLock()
        self.executor = SimpleNamespace(
            lock=threading.Lock(), current_job=None, current_task=None,
            onetime_tasks=[], device_manager=device, check_enabled=lambda: None,
        )
        self.submissions = []

    def _phase(self, run_id, phase):
        self.phase = phase

    def _submit(self, execute, name, fields):
        # The native method takes this non-reentrant lock internally.
        assert self.executor.lock.acquire(blocking=False), "Executor lock held during submit"
        self.executor.lock.release()
        self.submissions.append((execute, name, fields))
        return {"run_id": "test-run", "state": "queued", **fields}

    def execute(self):
        return self.submissions[-1][0]("test-run")


@pytest.fixture
def state(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    module = importlib.import_module("okww_exit_mcp")
    game = Game(module.GAME_PATH)
    games = [game]
    calls = []

    def stop():
        calls.append("native-stop")
        game.alive = False

    device = SimpleNamespace(
        hwnd_window=SimpleNamespace(exe_full_path=str(module.GAME_PATH)), stop_hwnd=stop,
    )
    monkeypatch.setattr(module, "require_child", lambda expected: None)
    monkeypatch.setattr(module, "process_session", lambda pid: 2)
    monkeypatch.setattr(module, "process_library", lambda: SimpleNamespace(
        process_iter=lambda attrs: games, NoSuchProcess=Gone,
    ))
    return SimpleNamespace(module=module, game=game, games=games, calls=calls,
                           device=device, runner=Runner(device))


def test_native_exit_is_queued_and_verified(state):
    queued = state.module.request_exit_game(state.runner, "  switch games  ", 2)
    assert queued["state"] == "queued"
    assert state.calls == []
    assert queued["operation"] == "exit_game"
    result = state.runner.execute()
    assert result["state"] == "exited"
    assert result["pid"] == state.game.pid
    assert result["reason"] == "switch games"
    assert state.calls == ["native-stop"]


def test_absent_game_never_calls_native_stop_or_device_start(state):
    state.games.clear()
    state.device.hwnd_window = None
    state.module.request_exit_game(state.runner, "already stopped", 2)
    assert state.runner.execute()["state"] == "not_running"
    assert state.calls == []


@pytest.mark.parametrize("reason", ["", "   ", None, "x" * 501])
def test_invalid_reason_never_submits(state, reason):
    with pytest.raises(ValueError, match="reason"):
        state.module.request_exit_game(state.runner, reason, 2)
    assert state.runner.submissions == []


@pytest.mark.parametrize("kind", ["job", "task", "enabled"])
def test_busy_executor_is_not_preempted(state, kind):
    executor = state.runner.executor
    if kind == "job":
        executor.current_job = SimpleNamespace(future=SimpleNamespace(done=lambda: False))
    elif kind == "task":
        executor.current_task = SimpleNamespace(running=True)
    else:
        executor.onetime_tasks = [SimpleNamespace(enabled=True)]
    with pytest.raises(RuntimeError, match="busy"):
        state.module.request_exit_game(state.runner, "switch", 2)
    assert state.runner.submissions == []
    assert state.calls == []


@pytest.mark.parametrize("mutation,error", [
    ("multiple", "at most one"), ("session", "another session"),
    ("path", "executable"), ("attachment", "not attached"),
])
def test_wrong_target_never_calls_native_stop(state, monkeypatch, mutation, error):
    if mutation == "multiple":
        state.games.append(Game(state.module.GAME_PATH, pid=456))
    elif mutation == "session":
        monkeypatch.setattr(state.module, "process_session", lambda pid: 1)
    elif mutation == "path":
        state.game.path = Path("D:/another-game.exe")
    else:
        state.device.hwnd_window.exe_full_path = "D:/another-game.exe"
    state.module.request_exit_game(state.runner, "switch", 2)
    with pytest.raises(RuntimeError, match=error):
        state.runner.execute()
    assert state.calls == []


def test_identity_changes_before_dispatch_are_rejected(state, monkeypatch):
    replacement = Game(state.module.GAME_PATH, pid=456)
    answers = iter([state.game, replacement])
    monkeypatch.setattr(state.module, "find_game", lambda expected: next(answers))
    state.module.request_exit_game(state.runner, "switch", 2)
    with pytest.raises(RuntimeError, match="identity changed"):
        state.runner.execute()
    assert state.calls == []


def test_native_noop_is_not_reported_as_exit(state, monkeypatch):
    monkeypatch.setattr(state.module, "EXIT_TIMEOUT", 0)
    state.device.stop_hwnd = lambda: state.calls.append("native-noop")
    state.module.request_exit_game(state.runner, "switch", 2)
    with pytest.raises(RuntimeError, match="still alive"):
        state.runner.execute()
    assert state.calls == ["native-noop"]


def test_disconnection_before_execution_prevents_exit(state, monkeypatch):
    state.module.request_exit_game(state.runner, "switch", 2)

    def reject(expected):
        raise RuntimeError("disconnected")

    monkeypatch.setattr(state.module, "require_child", reject)
    with pytest.raises(RuntimeError, match="disconnected"):
        state.runner.execute()
    assert state.calls == []


def test_registration_exposes_native_mcp_tool(state):
    tools = {}

    class Mcp:
        def tool(self):
            def register(fn):
                tools[fn.__name__] = fn
                return fn
            return register

    state.module.register_tools(Mcp(), state.runner)
    result = asyncio.run(tools["exit_game"]("switch", 2))
    assert result["run_id"] == "test-run"
    assert state.runner.execute()["state"] == "exited"


@pytest.mark.parametrize("expected", [True, 0, 1, "2"])
def test_real_session_guard_rejects_non_child_ids(monkeypatch, expected):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    module = importlib.import_module("okww_exit_mcp")
    with pytest.raises(ValueError, match="isolated child session"):
        module.require_child(expected)


def test_real_session_guard_rejects_wrong_runtime(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    module = importlib.import_module("okww_exit_mcp")
    monkeypatch.setenv("QUESTWEAVER_CHILD_SESSION_ID", "2")
    monkeypatch.setattr(module, "process_session", lambda pid: 1)
    with pytest.raises(RuntimeError, match="expected child session"):
        module.require_child(2)
