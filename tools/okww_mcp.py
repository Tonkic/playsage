"""Small SDK client for the installed OK-WW native MCP in the child session."""

import argparse
import asyncio
import ctypes
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from child_backend import powershell_json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(r"C:\Users\23614\AppData\Local\ok-ww\data\apps\ok-ww\working")


def child_session_id():
    wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
    child, current = ctypes.c_ulong(), ctypes.c_ulong()
    if not wts.WTSGetChildSessionId(ctypes.byref(child)) or child.value in (0, 0xFFFFFFFF):
        raise RuntimeError("No verified Windows child session")
    if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(current)):
        raise RuntimeError("Cannot identify the current desktop session")
    if child.value == current.value:
        raise RuntimeError("Child session must differ from the agent desktop")
    return child.value


def connection():
    launch = json.loads((ROOT / "runs/services/okww/launch.json").read_text("utf-8-sig"))
    child = child_session_id()
    if launch["session_id"] != child:
        raise RuntimeError("Launch metadata does not match the current Windows child session")
    project = Path(launch["project"]).resolve()
    if project != PROJECT.resolve():
        raise RuntimeError("Unexpected installed OK-WW project")
    record = json.loads((project / "logs/mcp/connection.json").read_text("utf-8"))
    parsed = urlsplit(record["url"])
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.path != "/mcp" or parsed.port != 23003
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise RuntimeError("Unexpected native MCP endpoint")
    if record["pid"] != launch["backend_pid"]:
        raise RuntimeError("Native MCP record does not match the launched backend")
    if Path(record["project_directory"]).resolve() != project:
        raise RuntimeError("Wrong OK-WW project")
    process = powershell_json(
        f"Get-CimInstance Win32_Process -Filter 'ProcessId = {int(record['pid'])}' | "
        "Select-Object ProcessId,SessionId,Name | ConvertTo-Json -Compress"
    )
    if process != {"ProcessId": record["pid"], "SessionId": child, "Name": "python.exe"}:
        raise RuntimeError("Backend process is missing or in the wrong session")
    listener = powershell_json(
        "Get-NetTCPConnection -LocalPort 23003 -State Listen -ErrorAction Stop | "
        "Select-Object LocalAddress,OwningProcess | ConvertTo-Json -Compress"
    )
    if listener != {"LocalAddress": "127.0.0.1", "OwningProcess": record["pid"]}:
        raise RuntimeError("Listener owner differs from the verified backend")
    games = powershell_json(
        "Get-CimInstance Win32_Process -Filter \"Name='Client-Win64-Shipping.exe'\" | "
        "Select-Object ProcessId,SessionId | ConvertTo-Json -Compress"
    )
    if games is not None and (not isinstance(games, dict) or games["SessionId"] != child):
        raise RuntimeError("Expected exactly one Wuthering Waves game in the child session")
    record["child_session_id"] = child
    return record


def require_connected_child(expected):
    """Input requires the isolated desktop to remain connected."""
    wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
    if child_session_id() != expected:
        raise RuntimeError("Windows child session changed before input")
    buffer, size = ctypes.c_void_p(), ctypes.c_ulong()
    if not wts.WTSQuerySessionInformationW(
        None, expected, 8, ctypes.byref(buffer), ctypes.byref(size)
    ):
        raise RuntimeError("Cannot verify child-session connection")
    try:
        if ctypes.cast(buffer, ctypes.POINTER(ctypes.c_int))[0] != 0:
            raise RuntimeError("Child session is disconnected; no input permitted")
    finally:
        wts.WTSFreeMemory(buffer)


def require_no_safety_stop():
    """An incident marker blocks new tasks until a human resolves the incident."""
    marker = ROOT / "runs/services/okww/safety-stop.json"
    try:
        marker.lstat()
    except FileNotFoundError:
        return
    # Existence alone is authoritative: malformed content or age cannot unlock it.
    raise RuntimeError(
        f"OKWW safety stop is active: {marker}. No run_task will be dispatched. "
        "Preserve the warning and resolve the incident manually; do not auto-retry."
    )


async def main(args):
    if args.tool == "run_task":
        require_no_safety_stop()
    record = connection()
    if args.tool in {"run_task", "exit_game"}:
        require_connected_child(record["child_session_id"])
    if args.tool == "exit_game" and args.expected_session_id != record["child_session_id"]:
        raise RuntimeError("Requested exit session differs from the verified child session")
    async with (
        streamablehttp_client(record["url"], headers={"Authorization": "Bearer " + record["token"]})
        as (read, write, _), ClientSession(read, write) as session,
    ):
        await session.initialize()
        if args.tool == "inventory":
            return [tool.model_dump(mode="json") for tool in (await session.list_tools()).tools]
        arguments = {}
        if args.file:
            arguments["file_path"] = str(Path(args.file).resolve())
        if args.run_id:
            arguments["run_id"] = args.run_id
        if args.skill:
            arguments["skill_id"] = args.skill
        if args.task_id:
            arguments["task_ids"] = args.task_id
        if args.tool == "exit_game":
            arguments["reason"] = args.reason
            arguments["expected_session_id"] = args.expected_session_id
        if args.tool == "run_task":
            require_no_safety_stop()
        result = await session.call_tool(args.tool, arguments)
        if result.isError:
            raise RuntimeError("\n".join(block.text for block in result.content if block.type == "text"))
        return result.structuredContent or [
            block.text for block in result.content if block.type == "text"
        ]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=["inventory", "list_skills", "get_skill", "list_tasks",
                                        "screenshot", "run_task", "get_run_status", "stop_task",
                                        "reload_tasks", "exit_game"])
    parser.add_argument("--file")
    parser.add_argument("--run-id")
    parser.add_argument("--skill")
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--reason")
    parser.add_argument("--expected-session-id", type=int)
    args = parser.parse_args()
    required = {"run_task": "file", "get_run_status": "run_id",
                "stop_task": "run_id", "get_skill": "skill"}.get(args.tool)
    if required and not getattr(args, required):
        parser.error(f"{args.tool} requires --{required.replace('_', '-')}")
    if args.tool == "exit_game" and (not args.reason or args.expected_session_id is None):
        parser.error("exit_game requires --reason and --expected-session-id")
    print(json.dumps(asyncio.run(main(args)), ensure_ascii=False, indent=2))
