"""Guard the app-local OKWW MCP registration patch."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "okww_exit_installer", Path(__file__).parents[1] / "tools/install_okww_exit_mcp.py"
)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def source(newline="\n"):
    return (
        "def create_mcp_app(runner, token, port, request_exit=None):\n"
        "    security = TransportSecuritySettings()\n"
        "    return security\n"
    ).replace("\n", newline)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_registration_is_idempotent_and_preserves_newlines(newline):
    updated = installer.build_server_source(source(newline))
    assert updated.count(installer.MARKER) == 1
    assert "register_playsage_tools(mcp, runner)" in updated
    assert installer.build_server_source(updated) == updated
    if newline == "\r\n":
        assert "\n" not in updated.replace("\r\n", "")


@pytest.mark.parametrize(
    "text",
    [
        "def unrelated():\n    pass\n",
        source().replace("request_exit=None", "changed=None"),
        source() + source(),
        source().replace("    security", installer.MARKER + "\n    security"),
    ],
)
def test_unknown_or_ambiguous_native_source_is_rejected(text):
    with pytest.raises((RuntimeError, ValueError)):
        installer.build_server_source(text)
