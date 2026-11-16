"""Cooperative window ownership, fresh observations and bounded policy execution."""

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Frame:
    id: str
    window_id: str
    size: tuple[int, int]
    captured_at: float  # local monotonic clock, never compared across processes
    scene: str


class Adapter(Protocol):
    async def observe(self) -> Frame: ...
    async def detect(self, target: dict, frame: Frame) -> dict: ...
    async def act(self, action: dict) -> dict: ...
    async def stop(self) -> None: ...


class WindowLease:
    """OS lock automatically released on process exit; applies only to cooperating clients."""

    def __init__(self, directory: Path, window_id: str):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / (hashlib.sha256(window_id.encode()).hexdigest() + ".lock")
        self.file = None

    def __enter__(self):
        self.file = self.path.open("a+b")
        self.file.seek(0, os.SEEK_END)
        if not self.file.tell():
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise RuntimeError("window already has an active input owner") from exc
        return self

    def __exit__(self, *_):
        if self.file:
            self.file.close()
            self.file = None


class Trace:
    def __init__(self, directory: Path):
        self.id = uuid.uuid4().hex
        self.path = directory / self.id / "trace.jsonl"
        self.path.parent.mkdir(parents=True)

    def write(self, kind: str, **data):
        with self.path.open("a", encoding="utf-8") as output:
            output.write(
                json.dumps({"kind": kind, "time": time.time(), **data}, ensure_ascii=False) + "\n"
            )


class GameContext:
    def __init__(
        self,
        adapter: Adapter,
        trace: Trace,
        window_id: str,
        size: tuple[int, int],
        max_actions=20,
        max_frame_age=5.0,
        stop_timeout=5.0,
    ):
        self.adapter, self.trace = adapter, trace
        self.window_id, self.size = window_id, size
        self.max_actions, self.max_frame_age = max_actions, max_frame_age
        self.stop_timeout = stop_timeout
        self.frame = None
        self.actions = 0
        self.stopped = False

    async def observe(self) -> dict:
        if self.stopped:
            raise RuntimeError("session stopped")
        self.frame = await self.adapter.observe()
        self._check_frame(self.frame)
        data = asdict(self.frame)
        self.trace.write("observation", **data)
        return data

    def _check_frame(self, frame):
        if frame.window_id != self.window_id or frame.size != self.size:
            raise RuntimeError("window identity or dimensions changed")
        age = time.monotonic() - frame.captured_at
        if not 0 <= age <= self.max_frame_age:
            raise RuntimeError("observation expired")

    async def detect(self, target: dict) -> dict:
        await self.observe()
        detected = await self.adapter.detect(target, self.frame)
        return {**detected, "frame_id": self.frame.id}

    async def act(self, action: dict) -> dict:
        if self.stopped or self.actions >= self.max_actions:
            raise RuntimeError("session stopped or action budget exhausted")
        if self.frame is None or action.get("frame_id") != self.frame.id:
            raise RuntimeError("action must reference the latest observation")
        self._check_frame(self.frame)
        # Check identity again immediately before dispatch. Target matching is an adapter concern.
        current = await self.adapter.observe()
        self._check_frame(current)
        if current.scene != self.frame.scene:
            raise RuntimeError("scene changed before action")
        self.actions += 1
        self.trace.write("action_requested", action=action)
        self.frame = None  # one action per observation, including unsuccessful dispatches
        result = await self.adapter.act(action)
        self.trace.write("action_result", result=result)
        await self.observe()
        return result

    async def run_skill(self, name: str, args: dict) -> dict:
        raise NotImplementedError("native skill dispatch requires a validated backend adapter")

    async def verify(self, goal: dict) -> dict:
        frame = await self.observe()
        result = {
            "success": frame["scene"] == goal.get("scene"),
            "frame_id": frame["id"],
            "scene": frame["scene"],
        }
        self.trace.write("verification", **result)
        return result

    async def stop(self):
        self.stopped = True
        self.frame = None
        try:
            async with asyncio.timeout(self.stop_timeout):
                await self.adapter.stop()
        except TimeoutError as exc:
            self.trace.write("stop_failed", reason="timeout", backend_stop_confirmed=False)
            raise RuntimeError("backend stop timed out; stop was not confirmed") from exc
        self.trace.write("stopped")


async def execute_policy(policy, context: GameContext, timeout: int, goal: dict):
    try:
        async with asyncio.timeout(timeout):
            result = await policy(context)
            if not isinstance(result, dict) or result.get("success") is not True:
                return {"success": False, "reason": "policy did not report success"}
            # A policy's success claim cannot replace an independent final observation.
            return await context.verify(goal)
    finally:
        await context.stop()
