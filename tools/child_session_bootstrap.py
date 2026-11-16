"""Start the existing native backend inside the explicitly selected child session."""

import argparse
import ctypes
import json
import os
import runpy
import site
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--session", required=True, type=int)
parser.add_argument("--mode", choices=["probe", "backend"], required=True)
args = parser.parse_args()
session = ctypes.c_ulong()
if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
    raise ctypes.WinError()
if session.value != args.session or session.value in {0, 1}:
    raise RuntimeError("Refusing to start outside the selected child session")
logs = root / "runs" / "services" / "child-session"
logs.mkdir(parents=True, exist_ok=True)
sys.stdout = (logs / f"{args.mode}.stdout.log").open("a", encoding="utf-8", buffering=1)
sys.stderr = (logs / f"{args.mode}.stderr.log").open("a", encoding="utf-8", buffering=1)
(logs / f"{args.mode}.json").write_text(
    json.dumps(
        {
            "session_id": session.value,
            "pid": os.getpid(),
            "elevated": bool(ctypes.windll.shell32.IsUserAnAdmin()),
            "mode": args.mode,
            "endpoint": "http://127.0.0.1:23002/mcp" if args.mode == "backend" else None,
        }
    ),
    encoding="utf-8",
)
if args.mode == "backend":
    backend = root / "third_party" / "OneDragon"
    # The venv redirector fails in this Windows child session. Run its exact base
    # interpreter and explicitly load the same installed dependency directory.
    site.addsitedir(str(backend / ".venv" / "Lib" / "site-packages"))
    os.chdir(backend)
    sys.path.insert(0, str(backend / "src"))
    os.environ["PYTHONUTF8"] = "1"
    sys.argv = ["server", "--host", "127.0.0.1", "--port", "23002"]
    runpy.run_module("zzz_od.backend.entry.server", run_name="__main__")
