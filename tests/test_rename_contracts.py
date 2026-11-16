"""Canonical branding, legacy identity, and session-contract regression checks."""

import importlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "runtime", "models", "adapters", "registry", "demo", "evidence",
    "grid_route", "memory", "rule_validation", "offline_cli", "cli",
)


@pytest.mark.parametrize("first", ["playsage", "questweaver"])
def test_import_orders_share_all_modules_and_class_identities(first):
    code = """
import importlib, json, sys
from pathlib import Path
first, modules = sys.argv[1], json.loads(sys.argv[2])
for name in modules:
    importlib.import_module(f'{first}.{name}')
for name in modules:
    canonical = importlib.import_module(f'playsage.{name}')
    legacy = importlib.import_module(f'questweaver.{name}')
    assert canonical is legacy, name
    assert Path(canonical.__file__).parent.name == 'playsage', name
from playsage.models import EventManifest
from questweaver.models import EventManifest as LegacyManifest
from playsage.runtime import WindowLease
from questweaver.runtime import WindowLease as LegacyLease
assert EventManifest is LegacyManifest
assert WindowLease is LegacyLease
assert EventManifest.__module__ == 'playsage.models'
"""
    result = subprocess.run(
        [sys.executable, "-c", code, first, json.dumps(MODULES)],
        capture_output=True, encoding="utf-8", timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_canonical_source_and_active_tools_do_not_use_legacy_implementation():
    for directory in (ROOT / "src/playsage", ROOT / "tools"):
        for path in directory.rglob("*"):
            if path.suffix not in {".py", ".ps1", ".cs", ".csproj", ".manifest"}:
                continue
            if any(part in {"obj", "bin", "__pycache__"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8-sig")
            assert "from questweaver" not in text, path
            assert "import questweaver" not in text, path
            assert "D:\\QuestWeaver" not in text, path
            assert "questweaver_" not in text, path


def test_viewer_project_manifest_and_start_script_agree():
    folder = ROOT / "tools/child-session"
    project = folder / "PlaySage.ChildSession.csproj"
    assert project.is_file()
    assert not (folder / "QuestWeaver.ChildSession.csproj").exists()
    ET.parse(project)
    manifest = ET.parse(folder / "app.manifest")
    identity = manifest.find("{urn:schemas-microsoft-com:asm.v1}assemblyIdentity")
    assert identity.attrib["name"] == "PlaySage.ChildSession"
    assert "PlaySage.ChildSession.exe" in (ROOT / "tools/start-child-session.ps1").read_text()
    assert 'Text = "PlaySage ' in (folder / "Program.cs").read_text(encoding="utf-8")
    launcher = (folder / "SessionLauncher.cs").read_text(encoding="utf-8")
    assert '"PlaySage-ChildSession-"' in launcher
    assert 'Author = "PlaySage"' in launcher


@pytest.mark.parametrize("canonical", [True, False])
def test_exit_guard_accepts_canonical_and_legacy_environment(monkeypatch, canonical):
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    module = importlib.import_module("okww_exit_mcp")
    monkeypatch.delenv("PLAYSAGE_CHILD_SESSION_ID", raising=False)
    monkeypatch.delenv("QUESTWEAVER_CHILD_SESSION_ID", raising=False)
    if canonical:
        monkeypatch.setenv("PLAYSAGE_CHILD_SESSION_ID", "2")
        # The canonical value wins over a stale inherited legacy value.
        monkeypatch.setenv("QUESTWEAVER_CHILD_SESSION_ID", "3")
    else:
        monkeypatch.setenv("QUESTWEAVER_CHILD_SESSION_ID", "2")
    monkeypatch.setattr(module, "process_session", lambda pid: 2)
    connection = module.ctypes.c_int(0)
    freed = []

    def query(server, session, info, buffer, size):
        assert session == 2 and info == 8
        buffer._obj.value = module.ctypes.addressof(connection)
        size._obj.value = module.ctypes.sizeof(connection)
        return True

    wts = SimpleNamespace(WTSQuerySessionInformationW=query,
                          WTSFreeMemory=lambda buffer: freed.append(True))
    monkeypatch.setattr(module.ctypes, "WinDLL", lambda *a, **k: wts, raising=False)
    module.require_child(2)
    assert freed == [True]


def test_session_launcher_exports_canonical_environment():
    source = (ROOT / "tools/switch-child-ww.ps1").read_text(encoding="utf-8")
    assert "$env:PLAYSAGE_CHILD_SESSION_ID = [string]$SessionId" in source
    assert "$env:QUESTWEAVER_CHILD_SESSION_ID = $env:PLAYSAGE_CHILD_SESSION_ID" in source
