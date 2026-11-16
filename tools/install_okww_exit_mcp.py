"""Install the app-local exit_game tool into the existing OKWW MCP server."""

import argparse
import ast
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

ANCHOR = "    security = TransportSecuritySettings("
MARKER = "    # PlaySage OKWW exit-game extension."
HOOK = (
    MARKER + "\n"
    "    from src.playsage_exit_game_mcp import register_tools as register_playsage_tools\n"
    "    register_playsage_tools(mcp, runner)\n\n"
)


def build_server_source(source: str) -> str:
    if "def create_mcp_app(runner, token, port, request_exit=None):" not in source:
        raise ValueError("Unsupported OKWW MCP factory signature")
    if source.count(ANCHOR) != 1:
        raise ValueError("Expected exactly one transport-security anchor")
    newline = "\r\n" if "\r\n" in source else "\n"
    hook = HOOK.replace("\n", newline)
    if MARKER in source:
        if source.count(hook + ANCHOR) != 1:
            raise ValueError("Existing extension hook differs; refusing to overwrite")
        return source
    updated = source.replace(ANCHOR, hook + ANCHOR, 1)
    ast.parse(updated)
    return updated


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply after validation")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    app = Path(os.environ["LOCALAPPDATA"]) / "ok-ww/data/apps/ok-ww/working"
    server = app / "ok/core/mcp_server.py"
    runner = app / "ok/core/mcp_runner.py"
    destination = app / "src/playsage_exit_game_mcp.py"
    source = root / "tools/okww_exit_mcp.py"
    runner_source = runner.read_text(encoding="utf-8")
    for required in ("def _submit(", "def _phase("):
        if required not in runner_source:
            raise ValueError(f"Unsupported OKWW runner: missing {required}")
    before = server.read_bytes()
    updated = build_server_source(before.decode("utf-8")).encode("utf-8")
    extension = source.read_bytes()
    ast.parse(extension.decode("utf-8"))
    previous_extension = destination.read_bytes() if destination.exists() else None
    changes = [(server, before, updated), (destination, previous_extension, extension)]
    manifest = {
        "app": str(app),
        "apply": args.apply,
        "files": [
            {"path": str(path), "before_sha256": digest(old) if old is not None else None,
             "after_sha256": digest(new), "changed": old != new}
            for path, old, new in changes
        ],
    }
    if args.apply and any(old != new for _, old, new in changes):
        backup = root / "runs/services/okww/backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup.mkdir(parents=True, exist_ok=False)
        for path, old, _ in changes:
            if old is not None:
                (backup / path.name).write_bytes(old)
        # Check every source before changing either file.
        for path, old, _ in changes:
            current = path.read_bytes() if path.exists() else None
            if current != old:
                raise RuntimeError(f"Concurrent modification: {path}")
        # Install the implementation before enabling its registration hook.
        for path, old, new in reversed(changes):
            if old == new:
                continue
            temporary = path.with_name(path.name + ".playsage.tmp")
            with temporary.open("xb") as stream:
                stream.write(new)
            os.replace(temporary, path)
            if path.read_bytes() != new:
                raise RuntimeError(f"Installation verification failed: {path}")
        manifest["backup"] = str(backup)
        (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
