"""One observed, bounded native MCP action per invocation; records real screenshots."""

import argparse
import asyncio
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

from child_backend import endpoint, identity
from PIL import Image, ImageChops, ImageStat

from playsage.adapters import sra_session
from playsage.runtime import WindowLease

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "third_party" / "OneDragon" / ".debug" / "zzz_od_mcp" / "screenshot"
OUTPUT = ROOT / "runs" / "onedragon"


async def call(session, name, arguments=None):
    result = await session.call_tool(name, arguments or {})
    if result.isError:
        raise RuntimeError(f"MCP error from {name}")
    data = result.structuredContent
    if data is None:
        texts = [block.text for block in result.content if block.type == "text"]
        data = json.loads("\n".join(texts))
    if isinstance(data, dict) and set(data) == {"result"}:
        data = data["result"]
    if isinstance(data, dict) and (data.get("error") or data.get("success") is False):
        raise RuntimeError(f"{name} failed: {data}")
    return data


async def bounded_input(session, name, arguments):
    """Keep the lease while a short native input finishes after cancellation.

    The native synchronous controller releases after press_time. Client cancellation
    does not prove server cancellation; never retry an uncertain input automatically.
    """
    if name not in {"key_tap", "click_game"} or not 0 <= arguments.get("press_time", 0) <= 0.2:
        raise ValueError("only short native taps are allowed")
    task = asyncio.create_task(call(session, name, arguments))
    try:
        result = await asyncio.shield(task)
        if isinstance(result, dict) and result.get("in_window") is False:
            raise RuntimeError("backend refused an out-of-window input")
        return result
    except asyncio.CancelledError:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=5)
        except Exception:  # noqa: BLE001 Any transport failure leaves input completion unknown.
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise RuntimeError(
                "native input completion unknown; stop and inspect before resuming"
            ) from None
        raise


async def observe(session):
    target = identity()
    window = await call(session, "check_game_window")
    if not window.get("is_win_valid") or window.get("win_title") != "绝区零":
        raise RuntimeError("expected a valid 绝区零 window")
    started = time.time()
    analysis = await call(session, "analyze_screen", {"save_image": True})
    source = Path(analysis["screenshot_path"]).resolve()
    if not source.is_relative_to(CAPTURES.resolve()) or not source.is_file():
        raise ValueError("screenshot path is outside this backend's capture directory")
    with Image.open(source) as picture:
        picture.load()
        if picture.size != (1920, 1080):
            raise ValueError("native action coordinates require a 1920x1080 screenshot")
    directory = OUTPUT / uuid.uuid4().hex
    directory.mkdir(parents=True)
    screenshot = directory / "screen.png"
    shutil.copyfile(source, screenshot)
    record = {
        "captured_at": started,
        "window": window,
        "analysis": analysis,
        "screenshot": str(screenshot),
        "backend": "onedragon",
        "simulation": False,
        "session_id": target["session_id"],
        "backend_pid": target["pid"],
    }
    record_path = directory / "observation.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record, record_path


def load_observation(path):
    path = Path(path).resolve()
    if not path.is_relative_to(OUTPUT.resolve()):
        raise ValueError("observation must come from runs/onedragon")
    data = json.loads(path.read_text("utf-8"))
    if data.get("backend") != "onedragon" or data.get("simulation") is not False:
        raise ValueError("not a live OneDragon observation")
    if not 0 <= time.time() - data["captured_at"] <= 90:
        raise ValueError("observation expired; observe again before input")
    image = Path(data["screenshot"]).resolve()
    if image.parent != path.parent:
        raise ValueError("observation screenshot must be in the same record directory")
    return data


def verify_transition(before, current, args):
    for field in ("session_id", "backend_pid"):
        if before.get(field) != current.get(field):
            raise ValueError("backend/session changed; observe again")
    for field in ("win_title", "x", "y", "width", "height"):
        if before["window"][field] != current["window"][field]:
            raise ValueError("window identity/geometry changed; observe again")
    if not current["window"].get("is_win_active"):
        raise ValueError("game is not the foreground window")
    scenes = lambda item: {
        s["screen_name"] for s in item["analysis"].get("screens", []) if s.get("is_precise")
    }
    if scenes(before) != scenes(current):
        raise ValueError("recognized scene changed; observe again")
    if args.command == "click":
        if args.x is None or args.y is None or not (0 <= args.x < 1920 and 0 <= args.y < 1080):
            raise ValueError("click coordinates must be inside 1920x1080")
        if anchor := getattr(args, "anchor", None):
            centers = []
            for observation in (before, current):
                matches = [
                    item
                    for item in observation["analysis"].get("ocr_texts", [])
                    if item["text"] == anchor
                ]
                if len(matches) != 1:
                    raise ValueError("OCR anchor is missing or ambiguous")
                item = matches[0]
                center = (item["x"] + item["width"] / 2, item["y"] + item["height"] / 2)
                if abs(center[0] - args.x) > 80 or abs(center[1] - args.y) > 80:
                    raise ValueError("click is too far from its inspected OCR anchor")
                centers.append(center)
            if max(abs(a - b) for a, b in zip(*centers)) > 8:
                raise ValueError("OCR anchor moved; observe again")
            return
        box = (
            max(0, args.x - 24),
            max(0, args.y - 24),
            min(1920, args.x + 25),
            min(1080, args.y + 25),
        )
        with Image.open(before["screenshot"]) as first, Image.open(current["screenshot"]) as second:
            delta = ImageChops.difference(
                first.convert("RGB").crop(box), second.convert("RGB").crop(box)
            )
            if max(ImageStat.Stat(delta).mean) > 25:
                raise ValueError("click target appearance changed; observe again")


def summarize(record, path):
    return {
        "observation": str(path),
        "screenshot": record["screenshot"],
        "window": record["window"],
        "scenes": [
            {"name": screen["screen_name"], "precise": screen["is_precise"]}
            for screen in record["analysis"].get("screens", [])
        ],
        "ocr": record["analysis"].get("ocr_texts", []),
    }


async def recorded_input(
    session, command, action, trace, store, run_id, context, frame, *, deadline=None,
):
    """Persist intent before dispatch; never retry input when post-dispatch evidence fails."""
    from playsage.evidence import atomic_write, json_bytes

    loop = asyncio.get_running_loop()
    deadline = loop.time() + 60 if deadline is None else deadline
    step = store.start_step(
        run_id, frame["ref"], *command, expected=action["expected"],
        reference=action["reference"],
    )
    action["evidence"] = {"run_id": run_id, "step_id": step["step_id"]}
    action["status"] = "intent_recorded"
    atomic_write(trace, json_bytes(action))
    dispatched = False
    try:
        # Synchronous scans/fsync may outlive the budget. Yield pending cancellation,
        # then recheck the absolute deadline and live source before creating an input task.
        await asyncio.sleep(0)
        if loop.time() >= deadline:
            raise TimeoutError("deadline expired before dispatch")
        load_observation(frame["source"])
        if loop.time() >= deadline:
            raise TimeoutError("deadline expired while checking observation")
        dispatched = True
        result = await bounded_input(session, *command)
        action.update(result=result, status="backend_returned")
        atomic_write(trace, json_bytes(action))
        store.update_step(run_id, step["step_id"], status="backend_returned", backend_result=result)
        await asyncio.sleep(2.5)
        after, after_path = await observe(session)
        action["after"] = str(after_path)
        atomic_write(trace, json_bytes(action))
        after_frame = store.import_observation(after_path, run_id, context)[0]
        change = store.compare(frame["ref"], after_frame["ref"])
        store.update_step(
            run_id, step["step_id"], after=after_frame["ref"], status="observed",
            actual={"observation": str(after_path), "analysis": after.get("analysis")},
            visual_change=change,
        )
        action.update(status="observed", goal_status="not_evaluated")
        atomic_write(trace, json_bytes(action))
        return {"action": action, **summarize(after, after_path)}
    except (Exception, asyncio.CancelledError) as exc:
        warning = (
            "输入可能已发生 / input may have occurred; do not retry; observe before resuming"
            if dispatched else "输入未发送 / input not dispatched; observe before resuming"
        )
        state = "incomplete" if dispatched else "not_dispatched"
        action.update(status=state, error=type(exc).__name__, warning=warning)
        failures = []
        try:
            atomic_write(trace, json_bytes(action))
        except Exception as write_error:  # noqa: BLE001 Preserve the original uncertain-input failure.
            failures.append(f"legacy record: {write_error}")
        try:
            store.update_step(run_id, step["step_id"], status=state,
                              error={"type": type(exc).__name__, "warning": warning})
        except Exception as write_error:  # noqa: BLE001 Evidence faults must never trigger a retry.
            failures.append(f"evidence record: {write_error}")
        print(warning + ("; " + "; ".join(failures) if failures else ""), file=sys.stderr)
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise RuntimeError(warning + f" ({type(exc).__name__}: {exc})") from exc


async def run(args):
    from playsage.evidence import DEFAULT_CAPACITY, EvidenceContext, EvidenceStore, identifier

    context = EvidenceContext(
        event_id=getattr(args, "event_id", None),
        package_digest=getattr(args, "package_digest", None),
        game_version=getattr(args, "game_version", None),
        resolution=[1920, 1080],
    ).model_dump()
    run_id = identifier(getattr(args, "run_id", None) or uuid.uuid4().hex)
    store = EvidenceStore(ROOT, getattr(args, "capacity_bytes", DEFAULT_CAPACITY))
    async with asyncio.timeout(60) as budget:
        async with sra_session(endpoint()) as session:
            with WindowLease(ROOT / "data" / "locks", "onedragon:绝区零"):
                if args.command == "observe":
                    record, path = await observe(session)
                    frames = store.import_observation(path, run_id, context)
                    return {**summarize(record, path), "evidence": [f["ref"] for f in frames]}
                if not args.observed:
                    raise ValueError("input requires --observed from an inspected observation")
                before = load_observation(args.observed)
                status = await call(session, "get_run_status")
                if status["state"] == "running":
                    raise RuntimeError("a native task already controls the game")
                current, current_path = await observe(session)
                verify_transition(before, current, args)
                command = (
                    (
                        "click_game",
                        {"x": args.x, "y": args.y, "press_time": 0.12, "pc_alt": args.pc_alt},
                    )
                    if args.command == "click"
                    else ("key_tap", {"key": args.key, "press_time": 0.12})
                )
                trace = current_path.parent / "action.json"
                action = {
                    "tool": command[0],
                    "arguments": command[1],
                    "reference": args.observed,
                    "before": str(current_path),
                    "requested_at": time.time(),
                    "result": "unknown",
                    "ocr_anchor": getattr(args, "anchor", None),
                }
                action["expected"] = getattr(args, "expected", None)
                frame = store.import_observation(current_path, run_id, context)[0]
                load_observation(current_path)  # Archiving must not make the current frame stale.
                return await recorded_input(
                    session, command, action, trace, store, run_id, context, frame,
                    deadline=budget.when(),
                )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["observe", "click", "key"])
    parser.add_argument("--observed")
    parser.add_argument("--x", type=int)
    parser.add_argument("--y", type=int)
    parser.add_argument("--pc-alt", action="store_true")
    parser.add_argument("--anchor", help="Exact nearby native OCR label for an animated control")
    parser.add_argument(
        "--key",
        choices=["esc", "enter", "space", "tab", "f", "w", "a", "s", "d", "f1", "f2", "f3", "f4"],
    )
    parser.add_argument("--run-id", help="Evidence run ID; generated if omitted")
    parser.add_argument("--event-id", help="Explicit activity identity, e.g. zzz.cyber-healer")
    parser.add_argument("--package-digest", help="Reviewed package SHA-256, if known")
    parser.add_argument("--game-version", help="Observed game version; not inferred")
    parser.add_argument("--expected", help="Expected visual effect; not a success declaration")
    parser.add_argument("--capacity-bytes", type=int, default=1024 * 1024 * 1024)
    args = parser.parse_args()
    if args.command == "key" and args.key is None:
        parser.error("key requires --key")
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))
