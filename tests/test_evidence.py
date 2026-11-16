import asyncio
import hashlib
import importlib
import json
import time
from pathlib import Path

import pytest
from PIL import Image

from playsage.evidence import EvidenceStore, atomic_write, json_bytes


def observation(root, name="before", fmt="PNG", color=(10, 20, 30), size=(8, 6), backend="sra"):
    directory = root / "runs" / ("onedragon" if backend == "onedragon" else "observations") / name
    directory.mkdir(parents=True, exist_ok=True)
    image = directory / "screen.data"  # Trust decoded format, not extension.
    Image.new("RGB", size, color).save(image, format=fmt)
    record = {"captured_at": time.time(), "simulation": True}
    if backend == "sra":
        record.update(source="sra", images=[{"path": str(image), "size": list(size)}],
                      window_identity_verified=False)
    else:
        record.update(backend="onedragon", screenshot=str(image), analysis={"screens": []},
                      window={"win_title": "test"}, session_id=2)
    path = directory / "observation.json"
    atomic_write(path, json_bytes(record))
    return path, image


@pytest.mark.parametrize("fmt,suffix", [("PNG", ".png"), ("JPEG", ".jpg")])
def test_original_bytes_history_and_inspection(tmp_path, fmt, suffix):
    source, image = observation(tmp_path, fmt=fmt)
    store = EvidenceStore(tmp_path)
    frame = store.import_observation(source, "run1")[0]
    record, _, copied = store.frame(frame["ref"])
    assert copied.suffix == suffix
    assert copied.read_bytes() == image.read_bytes()
    assert record["sha256"] == hashlib.sha256(image.read_bytes()).hexdigest()
    assert record["context"]["event_id"] is None
    assert record["window_identity_verified"] is False
    assert record["captured_at_utc"].endswith("+00:00")
    assert store.history("run1")["records"][0]["sequence"] == 1
    assert store.inspect(frame["ref"])["derived"] is False
    crop = store.inspect(frame["ref"], [1, 1, 4, 3])
    with Image.open(crop["path"]) as picture:
        assert picture.size == (3, 2)
    assert store.pixels(frame["ref"], [0, 0, 1, 1])["size"] == [1, 1]
    assert source.exists() and image.exists()


def test_comparison_and_step_do_not_assert_success(tmp_path):
    store = EvidenceStore(tmp_path)
    first = store.import_observation(observation(tmp_path)[0], "run1")[0]
    second = store.import_observation(observation(tmp_path, "after", color=(20, 40, 60))[0],
                                      "run1")[0]
    delta = store.compare(first["ref"], second["ref"])
    assert delta["mean_absolute_rgb"] == [10, 20, 30]
    assert delta["goal_status"] == "not_evaluated"
    assert store.pixels(first["ref"], [0, 0, 1, 1])["pixels"] == [(10, 20, 30)]
    step = store.start_step("run1", first["ref"], "key_tap", {"key": "d"})
    assert step["expected_status"] == "not_provided"
    result = store.update_step("run1", step["step_id"], after=second["ref"], status="observed")
    assert result["goal_status"] == "not_evaluated"
    assert [r["sequence"] for r in store.history("run1")["records"]] == [1, 2, 3]
    assert store.cleanup_preview()["delete_enabled"] is False


@pytest.mark.parametrize("bad", ["../escape", "con", "a/b", "A", "x:y", "a\\b"])
def test_bad_run_ids_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        EvidenceStore(tmp_path).import_observation(observation(tmp_path)[0], bad)


def test_invalid_images_paths_roi_limits_and_hash(tmp_path, monkeypatch):
    store = EvidenceStore(tmp_path)
    source, image = observation(tmp_path, size=(80, 80))
    frame = store.import_observation(source, "run1")[0]
    with pytest.raises(ValueError, match="ROI"):
        store.inspect(frame["ref"], [-1, 0, 1, 1])
    with pytest.raises(ValueError, match="pixel output"):
        store.pixels(frame["ref"])
    with pytest.raises(ValueError, match="capacity"):
        EvidenceStore(tmp_path, 1).import_observation(source)
    other = store.import_observation(observation(tmp_path, "small")[0])[0]
    with pytest.raises(ValueError, match="same dimensions"):
        store.compare(frame["ref"], other["ref"])
    with pytest.raises(ValueError, match="inside runs"):
        store.import_observation(tmp_path / "outside.json")
    record = json.loads(source.read_text())
    record["images"][0]["path"] = str(tmp_path / "elsewhere.png")
    atomic_write(source, json_bytes(record))
    with pytest.raises(ValueError, match="outside"):
        store.import_observation(source)
    _, _, copy = store.frame(frame["ref"])
    copy.write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        store.frame(frame["ref"])
    source, image = observation(tmp_path, "corrupt")
    image.write_bytes(b"not an image")
    with pytest.raises(OSError):
        store.import_observation(source)
    source, image = observation(tmp_path, "gif", fmt="GIF")
    with pytest.raises(ValueError, match="PNG/JPEG"):
        store.import_observation(source)
    source, _ = observation(tmp_path, "large")
    monkeypatch.setattr("playsage.evidence.MAX_PIXELS", 2)
    with pytest.raises(ValueError, match="pixel limit"):
        store.import_observation(source)


def test_atomic_failure_preserves_old_record(tmp_path, monkeypatch):
    path = tmp_path / "record.json"
    atomic_write(path, b"old")
    def fail(*_):
        raise OSError("disk fault")
    monkeypatch.setattr("playsage.evidence.os.replace", fail)
    with pytest.raises(OSError):
        atomic_write(path, b"new")
    assert path.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("failure", ["none", "cancel", "timeout", "transport", "observe", "write"])
def test_recorded_input_is_never_retried(tmp_path, monkeypatch, failure, capsys):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    native = importlib.import_module("onedragon_step")
    store = EvidenceStore(tmp_path)
    before, _ = observation(tmp_path, backend="onedragon")
    after, _ = observation(tmp_path, "after", backend="onedragon")
    frame = store.import_observation(before, "run1")[0]
    trace = before.parent / "action.json"
    calls = []
    async def input_call(*_):
        calls.append(1)
        if failure == "cancel":
            raise asyncio.CancelledError()
        if failure == "timeout":
            raise TimeoutError("timeout")
        if failure == "transport":
            raise OSError("connection lost")
        return {"success": True}
    async def observe(*_):
        if failure == "observe":
            raise OSError("screenshot failed")
        return json.loads(after.read_text("utf-8")), after
    async def sleep(*_):
        pass
    monkeypatch.setattr(native, "bounded_input", input_call)
    # This test targets post-dispatch failures, not live-observation admission.
    monkeypatch.setattr(native, "load_observation", lambda _: None)
    monkeypatch.setattr(native, "observe", observe)
    monkeypatch.setattr(native.asyncio, "sleep", sleep)
    if failure == "write":
        def fail(*_, **__):
            raise OSError("disk full")
        monkeypatch.setattr(store, "update_step", fail)
    action = {"expected": "move right", "reference": str(before), "result": "unknown"}
    coroutine = native.recorded_input(None, ("key_tap", {"key": "d"}), action, trace,
                                      store, "run1", frame["context"], frame)
    if failure == "none":
        result = asyncio.run(coroutine)
        assert result["action"]["status"] == "observed"
    else:
        error = asyncio.CancelledError if failure == "cancel" else RuntimeError
        with pytest.raises(error):
            asyncio.run(coroutine)
        assert "input may have occurred" in capsys.readouterr().err
        assert json.loads(trace.read_text("utf-8"))["status"] == "incomplete"
    assert len(calls) == 1
    steps = [r for r in store.history()["records"] if r["kind"] == "step"]
    assert len(steps) == 1
    assert steps[0]["goal_status"] == "not_evaluated"
    assert steps[0]["status"] == ("observed" if failure == "none" else
                                   "intent_recorded" if failure == "write" else "incomplete")


def test_failed_intent_prevents_input(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    native = importlib.import_module("onedragon_step")
    store = EvidenceStore(tmp_path)
    frame = store.import_observation(observation(tmp_path)[0], "run1")[0]
    def fail(*_, **__):
        raise OSError("no space for intent")
    monkeypatch.setattr(store, "start_step", fail)
    async def forbidden(*_):
        pytest.fail("input must not be called")
    monkeypatch.setattr(native, "bounded_input", forbidden)
    with pytest.raises(OSError):
        asyncio.run(native.recorded_input(
            None, ("key_tap", {}), {"expected": None, "reference": None},
            tmp_path / "action.json", store, "run1", frame["context"], frame,
        ))


@pytest.mark.parametrize("failure", ["expired", "deadline", "cancel"])
def test_slow_intent_prevents_dispatch(tmp_path, monkeypatch, failure, capsys):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    native = importlib.import_module("onedragon_step")
    source, _ = observation(tmp_path, backend="onedragon")
    data = json.loads(source.read_text("utf-8"))
    data["simulation"] = False  # Admission fixture only; input backend is forbidden below.
    atomic_write(source, json_bytes(data))
    monkeypatch.setattr(native, "OUTPUT", tmp_path / "runs/onedragon")
    native.load_observation(source)
    store = EvidenceStore(tmp_path)
    frame = store.import_observation(source, "run1")[0]
    original_start = store.start_step
    calls = []
    def delayed_start(*args, **kwargs):
        result = original_start(*args, **kwargs)
        if failure == "expired":
            monkeypatch.setattr(native.time, "time", lambda: data["captured_at"] + 91)
        elif failure == "deadline":
            time.sleep(0.03)  # Block the event loop, as a synchronous fsync can.
        else:
            asyncio.current_task().cancel()
        return result
    async def forbidden(*_):
        calls.append(1)
        pytest.fail("input must not be dispatched")
    monkeypatch.setattr(store, "start_step", delayed_start)
    monkeypatch.setattr(native, "bounded_input", forbidden)
    trace = source.parent / "action.json"
    async def execute():
        deadline = asyncio.get_running_loop().time() + (0.01 if failure == "deadline" else 60)
        await native.recorded_input(
            None, ("key_tap", {"key": "d"}), {"expected": None, "reference": str(source)},
            trace, store, "run1", frame["context"], frame, deadline=deadline,
        )
    error = asyncio.CancelledError if failure == "cancel" else RuntimeError
    with pytest.raises(error):
        asyncio.run(execute())
    assert calls == []
    assert json.loads(trace.read_text("utf-8"))["status"] == "not_dispatched"
    steps = [r for r in store.history()["records"] if r["kind"] == "step"]
    assert len(steps) == 1 and steps[0]["status"] == "not_dispatched"
    assert "input not dispatched" in capsys.readouterr().err


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_failed_frame_metadata_cleans_or_reports_uncommitted_image(
    tmp_path, monkeypatch, cleanup_fails,
):
    store = EvidenceStore(tmp_path)
    source, image = observation(tmp_path)
    published = store.import_observation(source, "published")[0]
    _, _, old_image = store.frame(published["ref"])
    old_bytes = old_image.read_bytes()
    original_unlink = Path.unlink
    def fail_metadata(path, raw):
        if path.suffix == ".json" and path.parent.name == "frames":
            raise OSError("metadata fault")
        atomic_write(path, raw)
    def fail_cleanup(path, *args, **kwargs):
        if cleanup_fails and path.parent.name == "frames" and path.suffix == ".png":
            raise OSError("cleanup fault")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr("playsage.evidence.atomic_write", fail_metadata)
    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    with pytest.raises(OSError, match="metadata fault") as error:
        store.import_observation(source, "failed")
    preview = store.cleanup_preview()
    assert len(preview["incomplete_files"]) == int(cleanup_fails)
    assert "failed" in preview["unreferenced_runs"]
    if cleanup_fails:
        assert "incomplete image retained" in " ".join(error.value.__notes__)
        assert Path(preview["incomplete_files"][0]).read_bytes() == image.read_bytes()
    assert store.history("failed")["records"] == []
    assert old_image.read_bytes() == old_bytes
    assert store.frame(published["ref"])[0] == published
    assert source.exists() and image.exists()
