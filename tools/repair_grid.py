"""Explicitly reviewed live runner for one manually observed Cyber Healer board.

No automatic package import. Each key requires the expected highlight, native OCR
stage/count, unchanged untouched cells and foreground/window checks. Stops at the
end of ONE board for independent visual result review.
"""

import argparse
import asyncio
import json
import re
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from child_backend import endpoint
from onedragon_step import (
    ROOT,
    bounded_input,
    call,
    load_observation,
    observe,
    summarize,
    verify_transition,
)
from PIL import Image, ImageChops, ImageStat

from playsage.adapters import sra_session
from playsage.grid_route import Board, actions_for, solve
from playsage.runtime import WindowLease


def load_board(path):
    spec = json.loads(Path(path).read_text("utf-8"))
    board = Board(
        spec["rows"],
        spec["columns"],
        frozenset(map(tuple, spec["blocked"] + spec.get("excluded", []))),
        frozenset(map(tuple, spec["targets"])),
        tuple(spec["end"]),
        {tuple(item["cell"]): item["ports"] for item in spec.get("ports", [])},
        frozenset(map(tuple, spec.get("rotations", []))),
        tuple(map(tuple, spec.get("ordered_targets", []))),
        {tuple(item["cell"]): item["key"] for item in spec.get("forced", [])},
        {tuple(a): tuple(b) for pair in spec.get("teleports", []) for a, b in (pair, pair[::-1])},
    )
    prefix = list(map(tuple, spec["prefix"]))
    route = solve(board, prefix)
    if len(route) > 48 or spec["rows"] != 5 or spec["columns"] != 6:
        raise ValueError("only the observed 5x6 board and <=48 cells are supported")
    return spec, board, prefix, route


def check_board(record, baseline, spec, board, prefix, *, max_age=15):
    if not 0 <= time.time() - record["captured_at"] <= max_age:
        raise ValueError("current board observation expired")
    texts = [item["text"].replace(" ", "") for item in record["analysis"]["ocr_texts"]]
    if not any(
        f"当前关卡：{spec['stage']}/4" in text or f"当前关卡:{spec['stage']}/4" in text
        for text in texts
    ):
        raise ValueError("native OCR did not confirm the expected stage")
    expected_count = len(board.targets & set(prefix))
    counts = [
        tuple(map(int, match.groups()))
        for text in texts
        if (match := re.fullmatch(r"(\d{2})/(\d{2})", text))
    ]
    if counts != [(expected_count, len(board.targets))]:
        raise ValueError(f"data counter mismatch: {counts}, expected {expected_count}")
    with Image.open(record["screenshot"]) as image, Image.open(baseline["screenshot"]) as original:
        image, original = image.convert("RGB"), original.convert("RGB")
        highlighted = []
        for row in range(board.rows):
            for col in range(board.columns):
                x, y = spec["xs"][col], spec["ys"][row]
                # Outer rim away from center arrows and the animated inner fill.
                color = ImageStat.Stat(image.crop((x + 15, y - 53, x + 25, y - 50))).mean
                if min(color) > 140:
                    highlighted.append((row, col))
                if (row, col) not in prefix:
                    box = (x - 36, y - 36, x + 37, y + 37)
                    expected = original.crop(box)
                    if (row, col) in board.ports:
                        initial_turns = len(board.rotations & set(map(tuple, spec["prefix"])))
                        turns = len(board.rotations & set(prefix)) - initial_turns
                        expected = expected.rotate(-90 * turns)
                    delta = ImageChops.difference(image.crop(box), expected)
                    if max(ImageStat.Stat(delta).mean) > 18:
                        raise ValueError(f"untouched tile changed at {(row, col)}")
        if highlighted != [prefix[-1]]:
            raise ValueError(f"position mismatch: {highlighted}, expected {prefix[-1]}")


async def run(args):
    spec, board, prefix, route = load_board(args.board)
    baseline = load_observation(args.observed)
    check_board(baseline, baseline, spec, board, prefix, max_age=90)
    directory = ROOT / "runs" / "repair" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    (directory / "plan.json").write_text(
        json.dumps(
            {"spec": spec, "route": route, "reference": args.observed}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    log = directory / "trace.jsonl"

    def record(event):
        with log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": time.time(), **event}, ensure_ascii=False) + "\n")

    try:
        async with asyncio.timeout(240):
            async with sra_session(endpoint()) as session:
                with WindowLease(ROOT / "data" / "locks", "onedragon:绝区零"):
                    current, path = await observe(session)
                    for key, traversed in actions_for(board, route, len(prefix)):
                        cell = traversed[-1]
                        if (await call(session, "get_run_status"))["state"] == "running":
                            raise RuntimeError("native task running")
                        verify_transition(baseline, current, SimpleNamespace(command="key"))
                        check_board(current, baseline, spec, board, prefix)
                        # Recheck foreground immediately before the bounded native key tap.
                        window = await call(session, "check_game_window")
                        verify_transition(
                            current, {**current, "window": window}, SimpleNamespace(command="key")
                        )
                        record(
                            {
                                "event": "request",
                                "key": key,
                                "before": str(path),
                                "expected_position": cell,
                                "expected_traversed": traversed,
                            }
                        )
                        result = await bounded_input(
                            session, "key_tap", {"key": key, "press_time": 0.12}
                        )
                        record({"event": "response", "result": result})
                        await asyncio.sleep(0.4 + 0.25 * (len(traversed) - 1))
                        current, path = await observe(session)
                        record({"event": "observe", "path": str(path)})
                        if cell != board.end:
                            check_board(current, baseline, spec, board, [*prefix, *traversed])
                        # End animation can replace the board immediately. Never infer
                        # completion here: return needs_visual_review for a fresh check.
                        prefix.extend(traversed)
                    record({"event": "awaiting_independent_result_review", "path": str(path)})
                    return {
                        "trace": str(log),
                        "outcome": "needs_visual_review",
                        **summarize(current, path),
                    }
    except BaseException as exc:
        record({"event": "stopped", "error": str(exc)})
        raise


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", required=True)
    parser.add_argument("--observed", required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))
