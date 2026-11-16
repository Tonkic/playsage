import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def backend(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    module = importlib.import_module("child_backend")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "runs/services/child-session").mkdir(parents=True)
    return module


def save_metadata(backend, **changes):
    data = {"session_id": 2, "pid": 123, "endpoint": "http://127.0.0.1:23002/mcp", **changes}
    (backend.ROOT / "runs/services/child-session/backend.json").write_text(json.dumps(data))


@pytest.mark.parametrize("changes", [{"session_id": 1}, {"endpoint": "http://127.0.0.1:23001/mcp"}])
def test_console_session_or_endpoint_is_rejected(backend, changes):
    save_metadata(backend, **changes)
    with pytest.raises(RuntimeError, match="isolated"):
        backend.identity()


def test_pid_in_another_session_is_rejected(backend, monkeypatch):
    save_metadata(backend)
    monkeypatch.setattr(
        backend,
        "powershell_json",
        lambda _: {"ProcessId": 123, "SessionId": 1, "Name": "python.exe"},
    )
    with pytest.raises(RuntimeError, match="another session"):
        backend.identity()


def test_foreign_listener_is_rejected(backend, monkeypatch):
    monkeypatch.setattr(
        backend, "identity", lambda: {"pid": 123, "endpoint": "http://127.0.0.1:23002/mcp"}
    )
    monkeypatch.setattr(
        backend, "powershell_json", lambda _: {"LocalAddress": "127.0.0.1", "OwningProcess": 456}
    )
    with pytest.raises(RuntimeError, match="listener"):
        backend.endpoint()
