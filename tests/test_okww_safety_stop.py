"""Offline tests of the client-side incident interlock; no native MCP calls."""
import ast
import asyncio
import importlib
import re
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    module = importlib.import_module("okww_mcp")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    calls = []

    def connection():
        calls.append("connection")
        return {"url": "http://test.invalid/mcp", "token": "fake", "child_session_id": 2}

    monkeypatch.setattr(module, "connection", connection)
    monkeypatch.setattr(module, "require_connected_child", lambda session: calls.append("session"))

    @asynccontextmanager
    async def transport(*args, **kwargs):
        calls.append("transport")
        yield None, None, None

    class Session:
        def __init__(self, *args):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def initialize(self):
            calls.append("initialize")

        async def call_tool(self, tool, arguments):
            calls.append((tool, arguments))
            return SimpleNamespace(isError=False, structuredContent={"ok": True})

    monkeypatch.setattr(module, "streamablehttp_client", transport)
    monkeypatch.setattr(module, "ClientSession", Session)
    marker = tmp_path / "runs/services/okww/safety-stop.json"
    args = SimpleNamespace(
        tool="run_task", file="task.py", run_id=None, skill=None, task_id=None,
        reason="stop after warning", expected_session_id=2,
    )
    return SimpleNamespace(module=module, calls=calls, marker=marker, args=args, session=Session)


def write_marker(client, contents="{}"):
    client.marker.parent.mkdir(parents=True, exist_ok=True)
    client.marker.write_text(contents, encoding="utf-8")


@pytest.mark.parametrize("contents", ["{}", "", "broken json", '{"active": false}',
                                      '{"expires_at": "2000-01-01T00:00:00Z"}'])
def test_existing_incident_blocks_before_connection(client, contents):
    write_marker(client, contents)
    with pytest.raises(RuntimeError, match="safety stop"):
        asyncio.run(client.module.main(client.args))
    assert client.calls == []


def test_marker_directory_also_blocks(client):
    client.marker.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="safety stop"):
        asyncio.run(client.module.main(client.args))
    assert client.calls == []


def test_marker_appearing_during_initialization_blocks_dispatch(client, monkeypatch):
    async def initialize(self):
        write_marker(client)

    monkeypatch.setattr(client.session, "initialize", initialize)
    with pytest.raises(RuntimeError, match="safety stop"):
        asyncio.run(client.module.main(client.args))
    assert not any(isinstance(call, tuple) for call in client.calls)


def test_marker_stat_failure_fails_closed(client, monkeypatch):
    original = Path.lstat

    def fail_marker_stat(path):
        if path == client.marker:
            raise PermissionError("marker cannot be inspected")
        return original(path)

    monkeypatch.setattr(Path, "lstat", fail_marker_stat)
    with pytest.raises((PermissionError, RuntimeError), match="marker|safety stop"):
        asyncio.run(client.module.main(client.args))
    assert client.calls == []


@pytest.mark.parametrize("tool", ["screenshot", "get_run_status", "stop_task", "exit_game",
                                   "list_tasks", "list_skills", "get_skill"])
def test_incident_preserves_inspection_and_stop_channels(client, tool):
    write_marker(client)
    client.args.tool = tool
    client.args.file = None
    client.args.run_id = "existing-run" if tool in {"get_run_status", "stop_task"} else None
    client.args.skill = "existing-skill" if tool == "get_skill" else None
    assert asyncio.run(client.module.main(client.args)) == {"ok": True}
    dispatched = [call for call in client.calls if isinstance(call, tuple)]
    assert len(dispatched) == 1
    assert dispatched[0][0] == tool
    assert client.marker.exists()


def test_no_marker_preserves_single_dispatch_without_retry(client):
    assert asyncio.run(client.module.main(client.args)) == {"ok": True}
    assert client.calls.count("session") == 1
    dispatched = [call for call in client.calls if isinstance(call, tuple)]
    assert len(dispatched) == 1
    assert dispatched[0][0] == "run_task"


@pytest.mark.parametrize("texts", [
    ["连接已断开", "重新登录"], ["反作弊检测异常", "登录"], ["账号封禁24小时"], [],
])
def test_legacy_kick_helper_captures_but_never_dismisses(texts):
    source = Path(__file__).resolve().parents[1] / "tools/okww/dismiss_kick.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    run = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "run")
    namespace = {"re": re}
    # Execute only the trusted task method with fake I/O, never import its backend.
    exec(compile(ast.Module(body=[run], type_ignores=[]), str(source), "exec"), namespace)  # noqa: S102
    captured = []
    clicks = []
    task = SimpleNamespace(
        next_frame=lambda: "frame",
        ocr=lambda *args, **kwargs: [SimpleNamespace(name=text, x=0, y=0) for text in texts],
        log_info=lambda text: None,
        screenshot=lambda name: captured.append(name),
        daily=SimpleNamespace(
            click_dialog_right_button=lambda: clicks.append("click"),
            in_team_and_world=lambda: False,
        ),
        wait_until=lambda *args, **kwargs: None,
        sleep=lambda seconds: None,
    )
    with pytest.raises(RuntimeError, match="manual review"):
        namespace["run"](task)
    assert captured == ["disconnect_requires_manual_review"]
    assert clicks == []
