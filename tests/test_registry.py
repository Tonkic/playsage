import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from playsage.cli import main, scaffold
from playsage.models import load_package
from playsage.registry import Registry

EXAMPLE = Path(__file__).resolve().parents[1] / "event_packs" / "hsr" / "example-event"


@pytest.fixture
def workspace(tmp_path):
    target = tmp_path / "event_packs" / "hsr" / "example-event"
    shutil.copytree(EXAMPLE, target)
    return tmp_path, target


def update_manifest(package, mutate):
    file = package / "event.yaml"
    data = yaml.safe_load(file.read_text("utf-8"))
    mutate(data)
    file.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_index_search_history_and_change(workspace):
    root, package = workspace
    with Registry(root / "data" / "events.sqlite") as registry:
        registry.index(root / "event_packs")
        rows = registry.search("示例", "hsr", "mock", "simulated", [1920, 1080])
        assert len(rows) == 1
        assert rows[0]["rejection_reasons"] == ["not_verified"]
        assert registry.search("", "zzz") == []
        rules = package / "references" / "rules.md"
        rules.write_text("changed rules", encoding="utf-8")
        assert "package_changed" in registry.search()[0]["rejection_reasons"]
        assert registry.index(root / "event_packs")[0]["status"] == "stale"
        assert registry.index(root / "event_packs")[0]["status"] == "stale"


def test_verified_yaml_cannot_grant_replay(workspace):
    root, package = workspace
    update_manifest(package, lambda data: data.update(status="verified"))
    with Registry(root / "events.sqlite") as registry:
        assert registry.index(root / "event_packs")[0]["status"] == "candidate"
        assert not registry.search()[0]["replay_allowed"]


def test_compatibility_is_explicit(workspace):
    root, _ = workspace
    with Registry(root / "events.sqlite") as registry:
        registry.index(root / "event_packs")
        row = registry.search("", "hsr", "sra", "9.9", [800, 600])[0]
        assert set(row["rejection_reasons"]) == {
            "not_verified",
            "backend_unsupported",
            "game_version_mismatch",
            "resolution_mismatch",
        }


@pytest.mark.parametrize("entry", ["../../outside.py", "C:/outside.py", "scripts\\policy.py"])
def test_entrypoint_must_stay_inside_package(workspace, entry):
    _, package = workspace
    update_manifest(package, lambda data: data["entrypoints"]["mock"].update(path=entry))
    with pytest.raises(ValueError):
        load_package(package)


def test_missing_backend_entry_is_rejected(workspace):
    _, package = workspace
    update_manifest(package, lambda data: data["execution"]["supported_backends"].append("sra"))
    with pytest.raises(ValueError, match="entrypoint"):
        load_package(package)


def test_duplicate_id_is_transactional(workspace):
    root, package = workspace
    with Registry(root / "events.sqlite") as registry:
        registry.index(root / "event_packs")
        original = registry.get("hsr.example-event")
        shutil.copytree(package, package.parent / "duplicate")
        with pytest.raises(ValueError, match="duplicate"):
            registry.index(root / "event_packs")
        assert registry.get("hsr.example-event") == original


def test_deleted_package_not_selectable(workspace):
    root, package = workspace
    with Registry(root / "events.sqlite") as registry:
        registry.index(root / "event_packs")
        shutil.rmtree(package)
        assert "package_unavailable_or_invalid" in registry.search()[0]["rejection_reasons"]
        registry.index(root / "event_packs")
        assert registry.search() == []


def test_new_package_valid_and_no_overwrite(tmp_path):
    result = scaffold(tmp_path, "ww", "test-event", "测试：活动")
    manifest, _ = load_package(Path(result["path"]))
    assert manifest.status == "draft"
    with pytest.raises(FileExistsError):
        scaffold(tmp_path, "ww", "test-event", "another")
    with pytest.raises(ValueError):
        scaffold(tmp_path, "ww", "../escape", "bad")


def test_cli_demo_keeps_candidate(workspace, capsys):
    root, _ = workspace
    prefix = ["--root", str(root)]
    assert main(prefix + ["index"]) == 0
    assert main(prefix + ["demo"]) == 0
    assert main(prefix + ["demo"]) == 0
    with Registry(root / "data" / "events.sqlite") as registry:
        assert registry.get("hsr.example-event")["status"] == "candidate"
        history = registry.history("hsr.example-event")
        assert len(history) == 2
        assert all(row["mode"] == "simulation" and row["success"] == 1 for row in history)
        assert all(Path(row["trace_path"]).is_file() for row in history)


def test_cli_missing_event_returns_error(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "show", "hsr.missing"]) == 1
    assert "not indexed" in capsys.readouterr().err


def test_malformed_yaml_is_search_rejection(workspace):
    root, package = workspace
    with Registry(root / "events.sqlite") as registry:
        registry.index(root / "event_packs")
        (package / "event.yaml").write_text("id: [", encoding="utf-8")
        assert "package_unavailable_or_invalid" in registry.search()[0]["rejection_reasons"]


def test_changed_id_can_be_reindexed(workspace):
    root, package = workspace
    with Registry(root / "events.sqlite") as registry:
        registry.index(root / "event_packs")
        update_manifest(package, lambda data: data.update(id="hsr.renamed"))
        assert registry.index(root / "event_packs")[0]["id"] == "hsr.renamed"
        assert len(registry.search()) == 1


def test_package_root_link_rejected(workspace):
    root, package = workspace
    link = root / "linked-package"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(package)], check=True, capture_output=True
        )
    else:
        link.symlink_to(package, target_is_directory=True)
    with pytest.raises(ValueError, match="linked package roots"):
        load_package(link)


def test_cli_json_is_utf8_on_windows(workspace):
    root, _ = workspace
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "playsage",
            "--root",
            str(root),
            "validate",
            "event_packs/hsr/example-event",
        ],
        capture_output=True,
        check=True,
    )
    assert "示例活动（仅模拟）" in child.stdout.decode("utf-8")
