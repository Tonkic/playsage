"""App-local MCP extension around OKWW's native DeviceManager.stop_hwnd.

Installed as src.playsage_exit_game_mcp in the existing OKWW application.
It does not implement capture, input, process killing, or a second server.
"""

import asyncio
import ctypes
import importlib
import os
import time
from pathlib import Path

GAME_NAME = "Client-Win64-Shipping.exe"
GAME_PATH = Path("D:/Wuthering Waves Game/Client/Binaries/Win64/Client-Win64-Shipping.exe")
EXIT_TIMEOUT = 15


def process_library():
    # psutil belongs to the consuming OKWW environment, not PlaySage's runtime.
    return importlib.import_module("psutil")


def process_session(pid):
    session = ctypes.c_ulong()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(session)):
        raise RuntimeError("Cannot verify process session")
    return session.value


def require_child(expected):
    if type(expected) is not int or expected <= 1:
        raise ValueError("expected_session_id must identify an isolated child session")
    declared = os.environ.get("PLAYSAGE_CHILD_SESSION_ID",
                              os.environ.get("QUESTWEAVER_CHILD_SESSION_ID"))
    if declared != str(expected) or process_session(os.getpid()) != expected:
        raise RuntimeError("Runtime does not belong to the expected child session")
    wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
    buffer, size = ctypes.c_void_p(), ctypes.c_ulong()
    if not wts.WTSQuerySessionInformationW(None, expected, 8, ctypes.byref(buffer), ctypes.byref(size)):
        raise RuntimeError("Cannot verify child-session connection")
    try:
        if ctypes.cast(buffer, ctypes.POINTER(ctypes.c_int))[0] != 0:
            raise RuntimeError("Child session is disconnected")
    finally:
        wts.WTSFreeMemory(buffer)


def find_game(expected):
    matches = [p for p in process_library().process_iter(["pid", "name"])
               if (p.info.get("name") or "").lower() == GAME_NAME.lower()]
    if not matches:
        return None
    if len(matches) != 1:
        raise RuntimeError("Expected at most one Wuthering Waves game across all sessions")
    game = matches[0]
    if process_session(game.pid) != expected:
        raise RuntimeError("Game belongs to another session")
    if Path(game.exe()).resolve() != GAME_PATH.resolve():
        raise RuntimeError("Game executable does not match the configured target")
    return game


def request_exit_game(runner, reason, expected_session_id):
    """Queue native exit without the normal run_task device-start/capture preparation."""
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValueError("reason must contain 1 to 500 characters")
    reason = reason.strip()
    require_child(expected_session_id)

    def execute(run_id):
        psutil = process_library()
        runner._phase(run_id, "exiting_game")
        require_child(expected_session_id)
        game = find_game(expected_session_id)
        if game is None:
            return {"state": "not_running", "session_id": expected_session_id,
                    "native_method": "DeviceManager.stop_hwnd", "reason": reason}
        created = game.create_time()
        device = runner.executor.device_manager
        window = device.hwnd_window
        if (window is None or not window.exe_full_path
                or Path(window.exe_full_path).resolve() != GAME_PATH.resolve()):
            raise RuntimeError("Native device is not attached to the expected game; no exit dispatched")
        runner.executor.check_enabled()
        require_child(expected_session_id)
        current = find_game(expected_session_id)
        if current is None:
            return {"state": "not_running", "session_id": expected_session_id,
                    "native_method": "DeviceManager.stop_hwnd", "reason": reason}
        if current.pid != game.pid or current.create_time() != created:
            raise RuntimeError("Game identity changed before exit; no exit dispatched")
        # The ONLY termination implementation is the existing native OKWW method.
        device.stop_hwnd()
        deadline = time.monotonic() + EXIT_TIMEOUT
        while time.monotonic() < deadline:
            try:
                exited = not game.is_running() or game.create_time() != created
            except psutil.NoSuchProcess:
                exited = True
            if exited:
                return {"state": "exited", "pid": game.pid,
                        "session_id": expected_session_id,
                        "native_method": "DeviceManager.stop_hwnd", "reason": reason}
            time.sleep(0.1)
        raise RuntimeError("Native stop_hwnd returned but the original game process is still alive")

    # Reuse the native runner's ownership, artifacts, status and cancellation.
    # In particular, never call runner.run_task(): that path can launch a game.
    with runner._lock:
        with runner.executor.lock:
            job = runner.executor.current_job
            task = runner.executor.current_task
            if ((job is not None and not job.future.done())
                    or (task is not None and task.running)
                    or any(t.enabled for t in runner.executor.onetime_tasks)):
                raise RuntimeError("Executor is busy; stop and verify the active task first")
        # Native acquire_exclusive takes the executor's non-reentrant lock itself.
        return runner._submit(execute, "mcp:exit_game", {
            "operation": "exit_game", "phase": "queued",
            "reason": reason, "expected_session_id": expected_session_id,
        })


def register_tools(mcp, runner):
    @mcp.tool()
    async def exit_game(reason: str, expected_session_id: int) -> dict:
        """End the configured game with native stop_hwnd; keep OKWW/MCP alive.

        This is process termination, NOT a graceful game-menu logout. Requires a
        connected isolated session and an idle executor. Never launches a game.
        Returns a run_id: poll get_run_status to a terminal state and inspect its
        result. A queued/stopping result is not proof that the game has exited.
        No arbitrary PID or executable path is accepted.
        """
        return await asyncio.to_thread(request_exit_game, runner, reason, expected_session_id)
