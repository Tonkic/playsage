import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from test_evidence import observation

from playsage.cli import scaffold
from playsage.evidence import EvidenceStore, store_lock
from playsage.memory import EventMemory
from playsage.models import load_package
from playsage.registry import Registry


@pytest.fixture
def memory(tmp_path):
    package = Path(scaffold(tmp_path, "zzz", "test", "测试")['path'])
    manifest = package / "event.yaml"
    data = yaml.safe_load(manifest.read_text("utf-8"))
    data["compatibility"] = {"game_version": "test-v1", "resolution": [8, 6]}
    manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
    return EventMemory(tmp_path, "zzz.test")


def payload(**updates):
    return {"kind": "knowledge", "status": "hypothesis", "text": "可能向右移动",
            "source": "manual observation", "evidence_refs": [], **updates}


def test_revision_evidence_and_package_isolation(memory):
    root = memory.project
    before = load_package(memory.package)[1]
    with Registry(root / "data/events.sqlite") as registry:
        registry.index(root / "event_packs")
        registry.mark_stale("zzz.test")
        result = memory.change(payload(), 0)
        entry_id = result["entry"]["id"]
        with pytest.raises(ValueError, match="references"):
            memory.change({"status": "supported"}, 1, entry_id)
        frame = memory.store.import_observation(observation(root)[0], "session1", memory.context)[0]
        memory.change({"status": "supported", "evidence_refs": [frame["ref"]]}, 1, entry_id)
        reopened = EventMemory(root, "zzz.test")
        assert reopened.show()["revision"] == 2
        assert reopened.show()["applicability"] == "context_matches"
        assert not reopened.show()["replay_allowed"]
        with pytest.raises(ValueError, match="revision conflict"):
            memory.change(payload(), 1)
        exported = reopened.export()
        assert "[supported]" in Path(exported["paths"][0]).read_text("utf-8")
        assert load_package(memory.package)[1] == before
        assert registry.index(root / "event_packs")[0]["status"] == "stale"
        assert not registry.search()[0]["replay_allowed"]
        assert memory.store.cleanup_preview()["protected_runs"] == ["session1"]


def test_digest_and_compatibility_change_require_review(memory):
    memory.change(payload(), 0)
    old_digest = memory.context["package_digest"]
    other_version = EventMemory(memory.project, "zzz.test", "test-v2")
    assert "game_version_changed" in other_version.show()["review_reasons"]
    with pytest.raises(ValueError, match="compatibility changed"):
        other_version.change(payload(), 1)
    resized = EventMemory(memory.project, "zzz.test", resolution=[100, 100])
    assert "resolution_changed" in resized.show()["review_reasons"]
    rules = memory.package / "references/rules.md"
    rules.write_text("new rules", encoding="utf-8")
    with pytest.raises(ValueError, match="package changed"):
        memory.change(payload(), 1)
    reopened = EventMemory(memory.project, "zzz.test")
    assert reopened.show()["entries"] == []
    assert old_digest in reopened.show()["available_digests"]
    assert reopened.show(old_digest)["applicability"] == "needs_review"
    assert "package_digest_changed" in reopened.show(old_digest)["review_reasons"]
    reopened.change(payload(), 0)
    assert reopened.show(old_digest)["revision"] == 1


def test_bad_missing_cross_activity_and_cross_version_refs(memory):
    with pytest.raises((ValueError, FileNotFoundError)):
        memory.change(payload(status="observed", evidence_refs=["missing/frame"]), 0)
    root = memory.project
    source = observation(root)[0]
    for context in ({**memory.context, "event_id": "hsr.other"},
                    {**memory.context, "game_version": "test-v2"},
                    {**memory.context, "package_digest": "f" * 64}, {}):
        ref = memory.store.import_observation(source, context=context)[0]["ref"]
        with pytest.raises(ValueError):
            memory.change(payload(status="observed", evidence_refs=[ref]), 0)
    assert memory.show()["revision"] == 0


def test_tampered_or_missing_evidence_invalidates_view(memory):
    ref = memory.store.import_observation(observation(memory.project)[0], context=memory.context)[0]
    memory.change(payload(status="observed", evidence_refs=[ref["ref"]]), 0)
    _, _, image = memory.store.frame(ref["ref"])
    image.unlink()
    assert memory.show()["applicability"] == "needs_review"
    assert memory.show()["evidence_errors"]


def test_memory_write_failure_is_atomic(memory, monkeypatch):
    memory.change(payload(), 0)
    original = memory.path().read_bytes()
    def fail(*_):
        raise OSError("disk fault")
    monkeypatch.setattr("playsage.evidence.os.replace", fail)
    with pytest.raises(OSError):
        memory.change(payload(text="changed"), 1)
    assert memory.path().read_bytes() == original
    assert not list(memory.path().parent.glob("*.tmp"))


def test_process_lock_and_revision_prevent_lost_updates(memory):
    child = """
import json, sys
from playsage.memory import EventMemory
try:
    value = EventMemory(sys.argv[1], 'zzz.test').change(
        {'kind':'progress','status':'hypothesis','text':'child','source':'test'}, 0)
    print(json.dumps(value))
except (RuntimeError, ValueError) as error:
    print(type(error).__name__)
    sys.exit(2)
"""
    with store_lock(memory.root, "memory"):
        locked = subprocess.run([sys.executable, "-c", child, str(memory.project)],
                                capture_output=True, timeout=20, check=False)
        assert locked.returncode == 2 and b"RuntimeError" in locked.stdout
    memory.change(payload(), 0)
    stale = subprocess.run([sys.executable, "-c", child, str(memory.project)],
                           capture_output=True, timeout=20, check=False)
    assert stale.returncode == 2 and b"ValueError" in stale.stdout
    assert memory.show()["revision"] == 1


def test_history_keeps_evidence_protected(memory):
    ref = memory.store.import_observation(observation(memory.project)[0], "history", memory.context)[0]
    entry = memory.change(payload(status="observed", evidence_refs=[ref["ref"]]), 0)["entry"]
    memory.change({"status": "hypothesis", "evidence_refs": []}, 1, entry["id"])
    assert memory.show()["previous_entries"][0]["evidence_refs"] == [ref["ref"]]
    assert "history" in EvidenceStore(memory.project).cleanup_preview()["protected_runs"]


def test_unknown_version_never_becomes_supported(tmp_path):
    scaffold(tmp_path, "hsr", "unknown", "unknown")
    memory = EventMemory(tmp_path, "hsr.unknown", resolution=[8, 6])
    frame = memory.store.import_observation(observation(tmp_path)[0], context=memory.context)[0]
    with pytest.raises(ValueError, match="unknown game version"):
        memory.change(payload(status="supported", evidence_refs=[frame["ref"]]), 0)
    memory.change(payload(), 0)
    assert memory.show()["applicability"] == "needs_review"


def test_unsupported_schema_is_not_overwritten(memory):
    memory.change(payload(), 0)
    data = json.loads(memory.path().read_text("utf-8"))
    data["schema_version"] = 2
    memory.path().write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        memory.change(payload(), 1)


@pytest.mark.parametrize("override", [False, True])
def test_long_lived_memory_rechecks_package_before_show_and_export(memory, override):
    if override:
        memory = EventMemory(memory.project, "zzz.test", "explicit-v1", [8, 6])
    memory.change(payload(), 0)
    original = memory.path().read_bytes()
    old_digest = memory.context["package_digest"]
    manifest = memory.package / "event.yaml"
    data = yaml.safe_load(manifest.read_text("utf-8"))
    data["compatibility"] = {"game_version": "test-v2", "resolution": [16, 12]}
    manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
    view = memory.show()
    assert view["applicability"] == "needs_review"
    assert "package_digest_changed" in view["review_reasons"]
    assert view["context"]["package_digest"] == old_digest
    assert view["current_context"]["package_digest"] == load_package(memory.package)[1]
    assert view["current_context"]["game_version"] == ("explicit-v1" if override else "test-v2")
    assert view["current_context"]["resolution"] == ([8, 6] if override else [16, 12])
    exported = memory.export()
    assert exported["applicability"] == "needs_review" and not exported["replay_allowed"]
    for path in exported["paths"]:
        assert "Applicability: needs_review" in Path(path).read_text("utf-8")
    assert memory.path().read_bytes() == original
    assert not memory.path(view["current_context"]["package_digest"]).exists()
