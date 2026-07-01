"""JX4 AltrunUnityDriver protocol adapter.

Wire format
----------
Request::

    CommandName;arg1;arg2;...;argN;&

- Fields separated by semicolon ``;``
- Terminated by ``&``
- No length-prefix on requests

Response::

    payload_bytes &

- Read until ``&`` terminator (byte-by-byte recv)
- Decode as UTF-8 string
- Screenshot responses are base64-encoded PNG
"""

from __future__ import annotations

import base64
import json
import socket
from typing import Any

from autotest_ide.core.errors import PocoConnectionError, PocoProtocolError
from autotest_ide.core.log import getLogger
from autotest_ide.core.protocol_base import PocoProtocol

logger = getLogger(__name__)

SEPARATOR = ";"
TERMINATOR = "&"
DEFAULT_PORT = 13000
MAX_PORT_RETRIES = 5


# ── wire-level helpers ──────────────────────────────────────────────

def _encode_request(method: str, args: tuple, kwargs: dict) -> bytes:
    """Build a JX4 request frame::

        CommandName;arg1;arg2;key1=val1;&
    """
    parts = [method]
    for a in args:
        parts.append(str(a))
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    cmd = SEPARATOR.join(parts) + SEPARATOR + TERMINATOR
    return cmd.encode("utf-8")


def _read_response(sock: socket.socket) -> str:
    """Read one response frame terminated by ``&``.

    Returns the decoded UTF-8 string **without** the trailing ``&``.
    """
    buf = b""
    while not buf.endswith(b"&"):
        chunk = sock.recv(1)
        if not chunk:
            raise PocoConnectionError("connection closed")
        buf += chunk
    text = buf.decode("utf-8")
    # strip trailing & and any whitespace
    return text.rstrip("&").strip()


def _parse_json_response(raw: str) -> Any:
    """Try to parse a response string as JSON; fallback to raw string."""
    raw = raw.strip()
    if not raw:
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


# ── JX4 protocol adapter ─────────────────────────────────────────────

class JX4Protocol(PocoProtocol):
    """AltrunUnityDriver protocol (semicolon-separated, &-terminated)."""

    # Map our public API names to JX4 command names.
    METHOD_MAP = {
        "dump_hierarchy": "getUiautatorTree",
        "get_attributes": "getNodeAttrById",
        "inspect_by_point": "getNodeByPos",
        "click": "tap",
        "set_text": "setText",
        "screenshot": "screenshot",
        "get_server_version": "getServerVersion",
    }

    # ── PocoProtocol interface ──────────────────────────────────

    def create_connection(
        self,
        host: str,
        port: int,
        timeout: float = 60.0,
    ) -> tuple[socket.socket, int]:
        """JX4: try port … port+4, return first success."""
        return self.connect_with_port_scan(host, port, timeout)

    def send_request(
        self,
        sock: socket.socket,
        method: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        data = _encode_request(method, args, kwargs)
        sock.sendall(data)

    def read_response(
        self,
        sock: socket.socket,
        expect_binary: bool,
    ) -> Any:
        raw = _read_response(sock)
        if expect_binary:
            # JX4 screenshots are base64-encoded
            try:
                return base64.b64decode(raw)
            except Exception as e:
                raise PocoProtocolError(f"invalid base64 screenshot: {e}")
        return _parse_json_response(raw)

    def handshake(self, client: Any) -> str | None:
        from autotest_ide.core.errors import PocoTimeoutError

        try:
            result = client._request_json("get_server_version")
        except PocoTimeoutError:
            raise PocoConnectionError(
                "handshake failed: AltrunUnityDriver did not respond to getServerVersion"
            )
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "version" in result:
            return result["version"]
        return str(result) if result else None

    # ── JX4-specific connection logic ────────────────────────────

    @staticmethod
    def connect_with_port_scan(
        host: str = "127.0.0.1",
        start_port: int = DEFAULT_PORT,
        timeout: float = 60.0,
    ) -> tuple[socket.socket, int]:
        """Try ports start_port … start_port+MAX_PORT_RETRIES-1.

        Returns (connected_socket, actual_port).
        Raises ``PocoConnectionError`` if all ports fail.
        """
        for offset in range(MAX_PORT_RETRIES):
            port = start_port + offset
            try:
                sock = socket.create_connection((host, port), timeout=5)
                sock.settimeout(timeout)
                return sock, port
            except OSError:
                continue
        raise PocoConnectionError(
            f"AltrunUnityDriver not found on {host}:{start_port}-{start_port + MAX_PORT_RETRIES - 1}"
        )

    # ── JX4-specific helpers ─────────────────────────────────────

    @staticmethod
    def encode_bool(value: bool, style: str = "true_false") -> str:
        """Encode a Python bool to the JX4 wire representation.

        *style* selects the encoding variant:
          - ``"true_false"`` → ``"true"`` / ``"false"``  (enableLogging, setCameraControl, setDlss)
          - ``"1_0"``        → ``"1"`` / ``"0"``          (openLogic, camera_observer)
          - ``"True_False"`` → ``"True"`` / ``"False"``  (isAutoPath return value)
        """
        if style == "1_0":
            return "1" if value else "0"
        if style == "True_False":
            return "True" if value else "False"
        # default: "true" / "false"
        return "true" if value else "false"

    @staticmethod
    def parse_bool(raw: str) -> bool | None:
        """Parse JX4's inconsistent bool encodings back to Python bool."""
        if raw in ("true", "True", "1"):
            return True
        if raw in ("false", "False", "0"):
            return False
        return None
