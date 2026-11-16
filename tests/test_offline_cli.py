import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_evidence import observation

from playsage.cli import scaffold
from playsage.models import load_package
from playsage.registry import Registry


@pytest.mark.parametrize("module", ["playsage", "questweaver"])
def test_complete_offline_cli_workflow(tmp_path, module):
    """Real CLI processes, synthetic images only; never connects to a game backend."""
    package = Path(scaffold(tmp_path, "zzz", "offline", "离线样例")["path"])
    digest = load_package(package)[1]
    with Registry(tmp_path / "data/events.sqlite") as registry:
        registry.index(tmp_path / "event_packs")
        registry.mark_stale("zzz.offline")
    def cli(*args, expected=0):
        result = subprocess.run(
            [sys.executable, "-m", module, "--root", str(tmp_path), *map(str, args)],
            capture_output=True, check=False, timeout=20,
        )
        assert result.returncode == expected, result.stderr.decode("utf-8")
        return json.loads(result.stdout.decode("utf-8") or result.stderr.decode("utf-8"))
    first, _ = observation(tmp_path)
    second, _ = observation(tmp_path, "after", color=(30, 40, 50), fmt="JPEG")
    context_flags = ["--event-id", "zzz.offline", "--package-digest", digest,
                     "--game-version", "fixture-v1", "--resolution", "8", "6"]
    before = cli("evidence", "import", first, "--run-id", "offline", *context_flags)["frames"][0]
    after = cli("evidence", "import", second, "--run-id", "offline", *context_flags)["frames"][0]
    assert cli("evidence", "history", "--event-id", "zzz.offline")["total"] == 2
    assert cli("evidence", "history", "--run-id", "offline", "--limit", 1,
               "--offset", 1)["records"][0]["ref"] == after["ref"]
    crop = cli("evidence", "inspect", before["ref"], "--roi", 0, 0, 2, 2)
    assert Path(crop["path"]).exists() and crop["derived"]
    assert len(cli("evidence", "pixels", before["ref"], "--roi", 0, 0, 1, 1)["pixels"]) == 1
    assert cli("evidence", "compare", before["ref"], after["ref"])["goal_status"] == "not_evaluated"
    assert cli("evidence", "stats")["bytes"] > 0
    memory_flags = ["--game-version", "fixture-v1", "--resolution", "8", "6"]
    payload = tmp_path / "entry.json"
    payload.write_text(json.dumps({"kind": "progress", "status": "observed",
                                   "text": "已保存离线样例", "source": "synthetic fixture",
                                   "evidence_refs": [before["ref"], after["ref"]]}), encoding="utf-8")
    added = cli("memory", "add", "zzz.offline", "--file", payload, "--expected-revision", 0,
                *memory_flags)
    assert added["revision"] == 1
    restored = cli("memory", "show", "zzz.offline", *memory_flags)
    assert restored["revision"] == 1 and restored["fresh_observation_required"]
    payload.write_text(json.dumps({"status": "supported"}), encoding="utf-8")
    cli("memory", "update", "zzz.offline", added["entry"]["id"], "--file", payload,
        "--expected-revision", 1, *memory_flags)
    exports = cli("memory", "export", "zzz.offline", *memory_flags)
    assert all(Path(file).exists() for file in exports["paths"])
    assert cli("evidence", "cleanup-preview")["protected_runs"] == ["offline"]
    sample = {"schema_version": 1, "context": before["context"],
              "board": {"rows": 1, "columns": 3, "end": [0, 2]},
              "interactions": [{"prefix": [[0, 0]], "action": "d",
                                "before_ref": before["ref"], "after_ref": after["ref"],
                                "annotation_source": "synthetic fixture, not real gameplay",
                                "observed": {"prefix": [[0, 0], [0, 1]], "position": [0, 1],
                                             "collected": [], "turns": 0, "complete": False}}]}
    request = tmp_path / "grid.json"
    request.write_text(json.dumps(sample), encoding="utf-8")
    report = cli("model", "validate-grid", request, "--report")
    assert report["status"] == "match" and not report["replay_allowed"]
    assert json.loads(Path(report["report"]).read_text("utf-8"))["status"] == "match"
    sample["interactions"][0]["after_ref"] = None
    request.write_text(json.dumps(sample), encoding="utf-8")
    assert cli("model", "validate-grid", request, expected=1)["status"] == "insufficient_evidence"
    assert load_package(package)[1] == digest
    with Registry(tmp_path / "data/events.sqlite") as registry:
        assert registry.get("zzz.offline")["status"] == "stale"
        assert not registry.search()[0]["replay_allowed"]
    assert cli("evidence", "inspect", "../escape", expected=1)["error"]
