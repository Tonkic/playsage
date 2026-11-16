import asyncio
import json
import subprocess
import sys
import time
from dataclasses import replace

import pytest

from playsage.adapters import MockAdapter
from playsage.demo import start_challenge
from playsage.runtime import GameContext, Trace, WindowLease, execute_policy


def context(tmp_path, adapter=None, **kwargs):
    return GameContext(
        adapter or MockAdapter(), Trace(tmp_path), "mock:hsr", (1920, 1080), **kwargs
    )


def test_success_observes_after_input_and_stops(tmp_path):
    ctx = context(tmp_path)
    result = asyncio.run(execute_policy(start_challenge, ctx, 1, {"scene": "challenge_complete"}))
    assert result["success"] and ctx.adapter.stopped
    records = [json.loads(line) for line in ctx.trace.path.read_text("utf-8").splitlines()]
    kinds = [row["kind"] for row in records]
    assert kinds[kinds.index("action_result") + 1] == "observation"
    assert kinds[-1] == "stopped"


def test_fake_policy_success_fails_independent_verification(tmp_path):
    async def liar(ctx):
        return {"success": True}

    ctx = context(tmp_path)
    result = asyncio.run(execute_policy(liar, ctx, 1, {"scene": "challenge_complete"}))
    assert not result["success"]
    assert ctx.adapter.stopped


def test_timeout_stops_backend(tmp_path):
    async def forever(ctx):
        await asyncio.Event().wait()

    ctx = context(tmp_path)
    with pytest.raises(TimeoutError):
        asyncio.run(execute_policy(forever, ctx, 0.01, {"scene": "challenge_complete"}))
    assert ctx.adapter.stopped


def test_policy_error_stops_backend(tmp_path):
    async def broken(ctx):
        raise ValueError("policy failed")

    ctx = context(tmp_path)
    with pytest.raises(ValueError, match="policy failed"):
        asyncio.run(execute_policy(broken, ctx, 1, {"scene": "challenge_complete"}))
    assert ctx.adapter.stopped


def test_hanging_stop_is_bounded_and_not_reported_as_success(tmp_path):
    class HangingStop(MockAdapter):
        async def stop(self):
            await asyncio.Event().wait()

    ctx = context(tmp_path, adapter=HangingStop(), stop_timeout=0.01)
    with pytest.raises(RuntimeError, match="stop was not confirmed"):
        asyncio.run(execute_policy(start_challenge, ctx, 1, {"scene": "challenge_complete"}))
    records = [json.loads(line) for line in ctx.trace.path.read_text("utf-8").splitlines()]
    assert records[-1]["kind"] == "stop_failed"
    assert not records[-1]["backend_stop_confirmed"]


@pytest.mark.parametrize(
    "mutation,error",
    [
        (lambda frame: replace(frame, captured_at=time.monotonic() - 99), "expired"),
        (lambda frame: replace(frame, window_id="other"), "identity"),
        (lambda frame: replace(frame, size=(800, 600)), "dimensions"),
    ],
)
def test_stale_or_wrong_window_frame_rejected(tmp_path, mutation, error):
    async def scenario():
        ctx = context(tmp_path)
        await ctx.observe()
        ctx.frame = mutation(ctx.frame)
        with pytest.raises(RuntimeError, match=error):
            await ctx.act({"frame_id": ctx.frame.id})
        assert ctx.actions == 0

    asyncio.run(scenario())


def test_action_requires_latest_observation(tmp_path):
    async def scenario():
        ctx = context(tmp_path)
        old = await ctx.observe()
        await ctx.observe()
        with pytest.raises(RuntimeError, match="latest"):
            await ctx.act({"frame_id": old["id"]})

    asyncio.run(scenario())


def test_scene_change_between_detection_and_action_rejected(tmp_path):
    async def scenario():
        ctx = context(tmp_path)
        frame = await ctx.observe()
        ctx.adapter.scene = "another_menu"
        with pytest.raises(RuntimeError, match="scene changed"):
            await ctx.act({"frame_id": frame["id"]})
        assert ctx.actions == 0

    asyncio.run(scenario())


def test_action_budget(tmp_path):
    async def scenario():
        ctx = context(tmp_path, max_actions=0)
        frame = await ctx.observe()
        with pytest.raises(RuntimeError, match="budget"):
            await ctx.act({"frame_id": frame["id"]})

    asyncio.run(scenario())


def test_window_lock_cross_process_and_release(tmp_path):
    code = (
        "from pathlib import Path; from playsage.runtime import WindowLease; "
        "import sys; lease=WindowLease(Path(sys.argv[1]), 'game-window'); "
        "lease.__enter__(); lease.__exit__()"
    )
    with WindowLease(tmp_path, "game-window"):
        child = subprocess.run(
            [sys.executable, "-c", code, str(tmp_path)], capture_output=True, check=False
        )
        assert child.returncode != 0
        assert b"active input owner" in child.stderr
    child = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, check=False
    )
    assert child.returncode == 0, child.stderr.decode()
