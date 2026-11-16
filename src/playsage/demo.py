"""A built-in simulation; never imports unreviewed package code."""

from pathlib import Path

from .adapters import MockAdapter
from .models import load_package
from .runtime import GameContext, Trace, WindowLease, execute_policy


async def start_challenge(ctx):
    button = await ctx.detect({"type": "text", "value": "开始挑战"})
    if not button["found"]:
        return {"success": False}
    await ctx.act(
        {"type": "click_target", "target": button["target"], "frame_id": button["frame_id"]}
    )
    return await ctx.verify({"scene": "challenge_complete"})


async def run_demo(root: Path, registry):
    row = registry.get("hsr.example-event")
    manifest, digest = load_package(Path(row["path"]))
    if digest != row["digest"]:
        raise ValueError("package changed; re-index before running demo")
    trace = Trace(root / "runs" / "traces")
    result = {
        "run_id": trace.id,
        "event_id": manifest.id,
        "digest": digest,
        "mode": "simulation",
        "success": False,
        "trace_path": str(trace.path.resolve()),
        "policy_source": "playsage.demo.start_challenge (built-in)",
        "counts_as_live_verification": False,
    }
    trace.write("started", **result)
    try:
        with WindowLease(root / "data" / "locks", "mock:hsr"):
            context = GameContext(
                MockAdapter(),
                trace,
                "mock:hsr",
                tuple(manifest.compatibility.resolution),
                max_actions=manifest.limits.max_actions,
            )
            outcome = await execute_policy(
                start_challenge,
                context,
                manifest.limits.timeout_seconds,
                {"scene": manifest.verification.required_scene},
            )
            result.update(outcome)
    except Exception as exc:  # noqa: BLE001 -- persist failures before returning to the CLI.
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        trace.write("finished", **result)
        registry.record_run(result)
    return result
