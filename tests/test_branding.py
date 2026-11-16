"""PlaySage branding and old-entry compatibility, with no live backend access."""

import importlib.metadata
import json
import subprocess
import sys
import sysconfig
import tomllib
from pathlib import Path

import pytest

import playsage
import playsage.cli
import questweaver
import questweaver.cli

ROOT = Path(__file__).resolve().parents[1]


def test_distribution_keeps_both_entrypoints_and_single_implementation():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    assert config["project"]["name"] == "playsage"
    assert config["project"]["scripts"] == {
        "playsage": "playsage.cli:main", "questweaver": "questweaver.cli:main",
    }
    assert set(config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]) == {
        "src/playsage", "src/questweaver",
    }
    distribution = importlib.metadata.distribution("playsage")
    assert distribution.version == playsage.__version__ == questweaver.__version__
    assert playsage.cli.main is questweaver.cli.main
    assert {entry.name for entry in distribution.entry_points
            if entry.group == "console_scripts"} == {"playsage", "questweaver"}


@pytest.mark.parametrize("name", ["playsage", "questweaver"])
@pytest.mark.parametrize("entry_kind", ["module", "console"])
def test_cli_brand_and_offline_doctor(tmp_path, name, entry_kind):
    if entry_kind == "module":
        command = [sys.executable, "-m", name]
    else:
        suffix = ".exe" if sys.platform == "win32" else ""
        script = Path(sysconfig.get_path("scripts")) / (name + suffix)
        assert script.is_file(), f"Run uv sync --locked to install {name}"
        command = [str(script)]
    help_result = subprocess.run(command + ["--help"], capture_output=True,
                                 timeout=20, check=False, encoding="utf-8")
    assert help_result.returncode == 0, help_result.stderr
    assert "PlaySage" in help_result.stdout
    doctor = subprocess.run(command + ["--root", str(tmp_path), "doctor"],
                            capture_output=True, timeout=20, check=False, encoding="utf-8")
    assert doctor.returncode == 0, doctor.stderr
    value = json.loads(doctor.stdout)
    assert value["live_input_enabled"] is False
    assert value["next_check"].startswith("playsage ")
    assert Path(value["root"]) == tmp_path.resolve()
    assert not list(tmp_path.iterdir())


def test_new_and_old_entrypoints_share_memory_and_package(tmp_path):
    def run(name, *args):
        result = subprocess.run(
            [sys.executable, "-m", name, "--root", str(tmp_path), *map(str, args)],
            capture_output=True, timeout=20, check=False, encoding="utf-8",
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    run("questweaver", "new", "hsr", "rename-test", "--name", "兼容测试")
    before = run("playsage", "validate", "event_packs/hsr/rename-test")["digest"]
    payload = tmp_path / "entry.json"
    payload.write_text(json.dumps({"kind": "progress", "status": "hypothesis",
                                   "text": "Offline rename check", "source": "test fixture"}),
                       encoding="utf-8")
    run("questweaver", "memory", "add", "hsr.rename-test", "--file", payload,
        "--expected-revision", 0)
    current = run("playsage", "memory", "show", "hsr.rename-test")
    assert current["revision"] == 1 and not current["replay_allowed"]
    assert current == run("questweaver", "memory", "show", "hsr.rename-test")
    assert before == run("playsage", "validate", "event_packs/hsr/rename-test")["digest"]
    assert len(list((tmp_path / "data/event_memory").rglob("memory.json"))) == 1
