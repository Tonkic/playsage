import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    module = importlib.import_module("okww_mcp")
    project = tmp_path / "installed"
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "PROJECT", project)
    monkeypatch.setattr(module, "child_session_id", lambda: 2)
    launch_dir = tmp_path / "runs/services/okww"
    launch_dir.mkdir(parents=True)
    (project / "logs/mcp").mkdir(parents=True)
    (launch_dir / "launch.json").write_text(json.dumps({
        "session_id": 2, "backend_pid": 123, "project": str(project),
    }))
    (project / "logs/mcp/connection.json").write_text(json.dumps({
        "url": "http://127.0.0.1:23003/mcp", "pid": 123,
        "project_directory": str(project), "token": "test-only",
    }))
    return module


@pytest.mark.parametrize("process,listener,games,error", [
    ({"ProcessId": 123, "SessionId": 1, "Name": "python.exe"}, None, None,
     "wrong session"),
    ({"ProcessId": 123, "SessionId": 2, "Name": "python.exe"},
     {"LocalAddress": "127.0.0.1", "OwningProcess": 456}, None, "Listener owner"),
    ({"ProcessId": 123, "SessionId": 2, "Name": "python.exe"},
     {"LocalAddress": "127.0.0.1", "OwningProcess": 123},
     {"ProcessId": 789, "SessionId": 1}, "exactly one"),
    ({"ProcessId": 123, "SessionId": 2, "Name": "python.exe"},
     {"LocalAddress": "127.0.0.1", "OwningProcess": 123},
     [{"ProcessId": 789, "SessionId": 2}, {"ProcessId": 987, "SessionId": 1}],
     "exactly one"),
])
def test_wrong_session_or_owner_is_rejected(bridge, monkeypatch, process, listener, games, error):
    results = iter([process, listener, games])
    monkeypatch.setattr(bridge, "powershell_json", lambda _: next(results))
    with pytest.raises(RuntimeError, match=error):
        bridge.connection()


def test_stale_session_after_reboot_is_rejected(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "child_session_id", lambda: 3)
    with pytest.raises(RuntimeError, match="current Windows child session"):
        bridge.connection()
