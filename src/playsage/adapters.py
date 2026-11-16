"""Mock input and a deliberately read-only SRA MCP connection."""

import base64
import io
import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from .runtime import Frame


class MockAdapter:
    def __init__(self, window_id="mock:hsr", size=(1920, 1080)):
        self.window_id, self.size = window_id, size
        self.scene = "event_menu"
        self.stopped = False

    async def observe(self):
        return Frame(uuid.uuid4().hex, self.window_id, self.size, time.monotonic(), self.scene)

    async def detect(self, target, frame):
        found = target == {"type": "text", "value": "开始挑战"} and self.scene == "event_menu"
        return {"found": found, "target": "start" if found else None}

    async def act(self, action):
        if self.stopped:
            raise RuntimeError("mock backend stopped")
        if action.get("type") != "click_target" or action.get("target") != "start":
            raise ValueError("unsupported mock action")
        self.scene = "challenge_complete"
        return {"success": True, "simulated": True}

    async def stop(self):
        self.stopped = True


def validate_sra_url(url: str):
    parts = urlsplit(url)
    if (
        parts.scheme not in {"http", "https"}
        or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("SRA endpoint must be a loopback HTTP(S) URL without credentials/query")


@asynccontextmanager
async def sra_session(url: str):
    validate_sra_url(url)
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with (
        streamablehttp_client(url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


async def tool_inventory(session):
    tools = []
    cursor = None
    seen = set()
    while True:
        result = await session.list_tools(cursor=cursor)
        tools.extend(tool.model_dump(mode="json") for tool in result.tools)
        cursor = result.nextCursor
        if cursor is None:
            return tools
        if cursor in seen:
            raise ValueError("MCP tools/list repeated a pagination cursor")
        seen.add(cursor)


async def observe_sra(session, directory: Path):
    inventory = await tool_inventory(session)
    if "sra_screenshot" not in {tool["name"] for tool in inventory}:
        raise ValueError("server does not expose sra_screenshot")
    result = await session.call_tool("sra_screenshot", {})
    if result.isError:
        raise RuntimeError("sra_screenshot reported an error")
    texts = []
    images = []
    for content in result.content:
        if content.type == "text":
            texts.append(content.text)
        elif content.type == "image":
            raw = base64.b64decode(content.data, validate=True)
            with Image.open(io.BytesIO(raw)) as picture:
                picture.load()
                suffix = {"PNG": ".png", "JPEG": ".jpg"}.get(picture.format)
                if suffix is None:
                    raise ValueError("expected SRA PNG or JPEG screenshot")
                size = picture.size
            images.append((raw, size, suffix))
    if not images:
        raise ValueError("no inline image returned; a file path alone is not visual evidence")
    directory.mkdir(parents=True, exist_ok=False)
    files = []
    for number, (raw, size, suffix) in enumerate(images):
        file = directory / f"screenshot-{number}{suffix}"
        file.write_bytes(raw)
        files.append({"path": str(file.resolve()), "size": list(size)})
    report = {
        "source": "sra",
        "captured_at": time.time(),
        "images": files,
        "text": texts,
        "window_identity_verified": False,
        "input_enabled": False,
        "agent_visual_receipt_verified": False,
    }
    (directory / "observation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
