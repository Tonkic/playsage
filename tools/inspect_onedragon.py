"""Read-only handshake and observation for the locally cloned OneDragon backend."""

import asyncio
import json
from pathlib import Path

from child_backend import endpoint

from playsage.adapters import sra_session, tool_inventory


async def main():
    output = Path(__file__).resolve().parents[1] / "runs" / "services" / "child-session"
    output.mkdir(parents=True, exist_ok=True)
    async with asyncio.timeout(45):
        async with sra_session(endpoint()) as session:
            inventory = await tool_inventory(session)
            (output / "tools.json").write_text(
                json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps({"tools": [tool["name"] for tool in inventory]}, ensure_ascii=False))
            for name, arguments in [
                ("check_game_window", {}),
                ("get_run_status", {}),
                ("analyze_screen", {"save_image": True}),
            ]:
                result = await session.call_tool(name, arguments)
                data = result.model_dump(mode="json")
                (output / f"{name}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(json.dumps({"tool": name, "result": data}, ensure_ascii=False))


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
