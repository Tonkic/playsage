import asyncio
import base64
import io
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult, ImageContent, TextContent
from PIL import Image

from playsage.adapters import observe_sra, validate_sra_url


class FakeSession:
    def __init__(self, content, error=False):
        self.result = CallToolResult(content=content, isError=error)
        self.calls = []

    async def list_tools(self, cursor=None):
        tool = SimpleNamespace(model_dump=lambda **_: {"name": "sra_screenshot"})
        return SimpleNamespace(tools=[tool], nextCursor=None)

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return self.result


@pytest.mark.parametrize(
    ("image_format", "mime_type", "suffix"),
    [("PNG", "image/png", "png"), ("JPEG", "image/jpeg", "jpg"), ("JPEG", "image/png", "jpg")],
)
def test_inline_image_saved_and_no_input(tmp_path, image_format, mime_type, suffix):
    stream = io.BytesIO()
    Image.new("RGB", (1280, 720)).save(stream, format=image_format)
    session = FakeSession(
        [
            ImageContent(
                type="image",
                mimeType=mime_type,
                data=base64.b64encode(stream.getvalue()).decode(),
            )
        ]
    )
    report = asyncio.run(observe_sra(session, tmp_path / "capture"))
    assert report["images"][0]["size"] == [1280, 720]
    assert not report["window_identity_verified"] and not report["input_enabled"]
    assert session.calls == [("sra_screenshot", {})]
    saved = tmp_path / "capture" / f"screenshot-0.{suffix}"
    assert report["images"][0]["path"] == str(saved.resolve())
    assert saved.read_bytes() == stream.getvalue()


def test_path_only_is_not_image_evidence(tmp_path):
    session = FakeSession([TextContent(type="text", text="C:/screenshots/game.png")])
    with pytest.raises(ValueError, match="no inline image"):
        asyncio.run(observe_sra(session, tmp_path / "capture"))
    assert not (tmp_path / "capture").exists()


def test_server_error_is_not_success(tmp_path):
    session = FakeSession([], error=True)
    with pytest.raises(RuntimeError, match="reported an error"):
        asyncio.run(observe_sra(session, tmp_path / "capture"))


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/mcp",
        "file:///tmp/mcp",
        "http://localhost@evil.com/mcp",
        "http://user:password@localhost/mcp",
    ],
)
def test_non_loopback_endpoint_rejected(url):
    with pytest.raises(ValueError, match="loopback"):
        validate_sra_url(url)


def test_loopback_url_allowed():
    validate_sra_url("http://127.0.0.1:5000/mcp")
    validate_sra_url("http://[::1]:5000/mcp")


@pytest.mark.parametrize("image_format", ["GIF", "BMP"])
def test_unsupported_image_format_rejected(tmp_path, image_format):
    stream = io.BytesIO()
    Image.new("RGB", (32, 24)).save(stream, format=image_format)
    session = FakeSession(
        [
            ImageContent(
                type="image",
                mimeType="image/png",
                data=base64.b64encode(stream.getvalue()).decode(),
            )
        ]
    )
    with pytest.raises(ValueError, match="expected SRA"):
        asyncio.run(observe_sra(session, tmp_path / "capture"))
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize("data", ["not valid base64!", base64.b64encode(b"not an image").decode()])
def test_invalid_image_data_rejected(tmp_path, data):
    session = FakeSession([ImageContent(type="image", mimeType="image/jpeg", data=data)])
    with pytest.raises((ValueError, OSError)):
        asyncio.run(observe_sra(session, tmp_path / "capture"))
    assert not (tmp_path / "capture").exists()


def test_mixed_inline_formats_preserve_original_bytes(tmp_path):
    contents = []
    originals = []
    for image_format, mime_type in [("PNG", "image/png"), ("JPEG", "image/jpeg")]:
        stream = io.BytesIO()
        Image.new("RGB", (32, 24)).save(stream, format=image_format)
        originals.append(stream.getvalue())
        contents.append(
            ImageContent(
                type="image", mimeType=mime_type, data=base64.b64encode(stream.getvalue()).decode()
            )
        )
    report = asyncio.run(observe_sra(FakeSession(contents), tmp_path / "capture"))
    assert len(report["images"]) == 2
    for number, suffix in enumerate(["png", "jpg"]):
        saved = tmp_path / "capture" / f"screenshot-{number}.{suffix}"
        assert saved.read_bytes() == originals[number]
        assert report["images"][number]["path"] == str(saved.resolve())
