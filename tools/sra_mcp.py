"""Direct MCP client for the SRA server (new SRAServer, JPEG screenshots).

The playsage sra observe command validates and preserves inline PNG/JPEG.
This separate development helper calls an explicitly named tool, saves JPEG
results to runs/observations/sra/, and prints text content for review.
"""
import argparse
import asyncio
import base64
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:5000/mcp"
OUT = Path(__file__).resolve().parents[1] / "runs" / "observations" / "sra"


async def call(name, args):
    OUT.mkdir(parents=True, exist_ok=True)
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, args)
            print("isError:", result.isError)
            saved = None
            for block in result.content:
                if block.type == "text":
                    print("text:", block.text[:400])
                elif block.type == "image":
                    stamp = time.strftime("%H%M%S")
                    path = OUT / f"{stamp}_{name}.jpg"
                    path.write_bytes(base64.b64decode(block.data))
                    print("image saved:", path)
                    saved = str(path)
            if result.structuredContent:
                sc = json.dumps(result.structuredContent, ensure_ascii=False)
                print("structured:", sc[:400] if saved else sc[:1500])
            if result.isError:
                raise SystemExit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("tool")
    parser.add_argument("--args", default="{}")
    a = parser.parse_args()
    asyncio.run(call(a.tool, json.loads(a.args)))
