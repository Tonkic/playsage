"""Verify the local MCP listener belongs to the active isolated Windows session."""

import ctypes
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def identity():
    data = json.loads((ROOT / "runs/services/child-session/backend.json").read_text("utf-8"))
    if data["session_id"] <= 1 or data["endpoint"] != "http://127.0.0.1:23002/mcp":
        raise RuntimeError("Only the isolated child-session backend is permitted")
    # ProcessIdToSessionId returns access denied for this elevated process from
    # the parent session. CIM exposes session metadata without opening its token.
    process = powershell_json(
        f"Get-CimInstance Win32_Process -Filter 'ProcessId = {int(data['pid'])}' | "
        "Select-Object ProcessId,SessionId,Name | ConvertTo-Json -Compress"
    )
    if process != {"ProcessId": data["pid"], "SessionId": data["session_id"], "Name": "python.exe"}:
        raise RuntimeError("Backend process is missing or belongs to another session")
    wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
    buffer, size = ctypes.c_void_p(), ctypes.c_ulong()
    if not wts.WTSQuerySessionInformationW(
        None, data["session_id"], 8, ctypes.byref(buffer), ctypes.byref(size)
    ):
        raise RuntimeError("Cannot verify child-session connection")
    try:
        if ctypes.cast(buffer, ctypes.POINTER(ctypes.c_int))[0] != 0:
            raise RuntimeError("Child session is disconnected; no input permitted")
    finally:
        wts.WTSFreeMemory(buffer)
    return data


def powershell_json(command):
    query = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return json.loads(query.stdout) if query.stdout.strip() else None


def endpoint():
    data = identity()
    listener = powershell_json(
        "Get-NetTCPConnection -LocalPort 23002 -State Listen -ErrorAction Stop | "
        "Select-Object LocalAddress,OwningProcess | ConvertTo-Json -Compress"
    )
    if not isinstance(listener, dict) or listener != {
        "LocalAddress": "127.0.0.1",
        "OwningProcess": data["pid"],
    }:
        raise RuntimeError("MCP listener does not match the verified child backend")
    return data["endpoint"]
