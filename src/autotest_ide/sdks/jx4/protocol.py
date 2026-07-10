"""JX4 AltrunUnityDriver protocol adapter.

Wire format (see docs/jx4/AltrunUnityDriver接口协议文档.md)
---------------------------------------------------------
Request::

    CommandName;arg1;arg2;...;argN;&

- Fields separated by semicolon ``;``
- Terminated by ``;&``

Response::

    altstart::<payload>::altLog::<log>::altend

- Read until ``::altend`` suffix (loop recv, accumulate buffer)
- Decode as UTF-8
- Strip the ``altstart::`` prefix and ``::altend`` suffix
- Split on ``::altLog::`` to separate payload from Unity log
- payload may be JSON, plain string, or base64 (screenshots)
- If response doesn't start with ``altstart::`` or contain ``::altend``,
  return empty string (per spec §2.2 "异常情况")
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

RESPONSE_PREFIX = "altstart::"
RESPONSE_SUFFIX = "::altend"
RESPONSE_LOG_SEP = "::altLog::"


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
    """Read one JX4 response frame.

    Reads until the buffer ends with ``::altend`` (per spec §2.2),
    then strips the ``altstart::`` prefix and ``::altend`` suffix,
    and returns only the payload (without the ``::altLog::`` log part).

    Returns empty string if the response is malformed.
    """
    buf = b""
    while not buf.endswith(b"::altend"):
        chunk = sock.recv(4096)
        if not chunk:
            raise PocoConnectionError("connection closed")
        buf += chunk
        # Safety cap: avoid unbounded buffering if a malformed server
        # never sends ::altend. 16 MB is well above any sane screenshot.
        if len(buf) > 16 * 1024 * 1024:
            raise PocoProtocolError("response too large without ::altend")
    text = buf.decode("utf-8", errors="replace")
    # Extract payload: altstart::<payload>::altLog::<log>::altend
    if RESPONSE_PREFIX not in text or RESPONSE_SUFFIX not in text:
        logger.warning("Malformed JX4 response (missing altstart/altend): %r", text[:200])
        return ""
    # Strip prefix + suffix
    inner = text.split(RESPONSE_PREFIX, 1)[1]
    inner = inner.rsplit(RESPONSE_SUFFIX, 1)[0]
    # Split off the log part if present
    if RESPONSE_LOG_SEP in inner:
        payload, _log = inner.split(RESPONSE_LOG_SEP, 1)
    else:
        payload = inner
    return payload.strip()


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
    # See docs/jx4/AltrunUnityDriver接口协议文档.md §9
    METHOD_MAP = {
        "dump_hierarchy": "getHierarchy",
        "get_attributes": "getInspector",
        "inspect_by_point": "getNodeByPos",
        "click": "tap",
        "find_and_tap": "findObjectAndTap",
        "set_text": "setText",
        "get_server_version": "getServerVersion",
        # getScreen returns screen size JSON (width/height).
        "get_screen_size": "getScreen",
        # --- new mappings ---
        "long_click":        "LongClick",
        "swipe":             "Swipe",
        "wait_for_node":     "WaitForNode",
        "wait_for_gone":     "WaitForNodeDisappear",
        "drag":              "dragObject",
        "get_node_by_path":  "findObject",
    }

    # ── PocoProtocol interface ──────────────────────────────────

    def get_default_remote_ports(self) -> list[int] | None:
        """JX4: scan ports 13000-13004 for ADB forwarding."""
        return list(range(13000, 13005))

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

    def before_close(self, sock: socket.socket) -> None:
        """Send ``CloseConnection`` farewell before socket close.

        Mirrors ``AltrunUnityDriver.stop()`` in docs/jx4/runner.py line 82.
        Best-effort — errors are swallowed by the caller.
        """
        try:
            data = _encode_request("CloseConnection", (), {})
            sock.sendall(data)
        except OSError:
            pass

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
        connect_timeout: float = 5.0,
    ) -> tuple[socket.socket, int]:
        """Try ports start_port … start_port+MAX_PORT_RETRIES-1.

        Mirrors ``AltrunUnityDriver.__init__`` in docs/jx4/runner.py:
        - ``socket.socket(AF_INET, SOCK_STREAM)``
        - ``connect((host, port))`` with a short timeout
        - on ``ConnectionRefusedError``, bump port and retry (up to 5 times)
        - on success, ``settimeout(timeout)`` for the subsequent handshake

        Returns (connected_socket, actual_port).
        Raises ``PocoConnectionError`` if all ports fail.
        """
        last_err: Exception | None = None
        port = start_port
        for _ in range(MAX_PORT_RETRIES):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(connect_timeout)
                sock.connect((host, port))
                # Match runner.py: long timeout for handshake + slow commands
                sock.settimeout(timeout)
                logger.info("JX4 connected to %s:%d", host, port)
                return sock, port
            except ConnectionRefusedError as e:
                last_err = e
                sock.close()
                logger.debug("JX4 connect refused on %s:%d, trying %d",
                             host, port, port + 1)
                port += 1
                continue
            except OSError as e:
                last_err = e
                sock.close()
                logger.debug("JX4 connect failed on %s:%d: %s", host, port, e)
                port += 1
                continue
        raise PocoConnectionError(
            f"AltrunUnityDriver not found on {host}:{start_port}-"
            f"{start_port + MAX_PORT_RETRIES - 1}: {last_err}"
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

    # ── hierarchy conversion ─────────────────────────────────────

    def transform_result(self, method: str, result: Any) -> Any:
        """Convert JX4 results to Poco-compatible format.

        JX4 ``getHierarchy`` returns a tree whose nodes look like::

            {"id": -21912, "name": "BtnStart", "x": 100, "y": 200,
             "children": [...]}

        sometimes wrapped in ``{"objs": {…}}``.

        Poco expects::

            {"name": "BtnStart", "type": "GameObject",
             "payload": {"text": "", "x": 100, "y": 200},
             "node_id": "-21912", "children": [...]}

        JX4 ``getNodeByPos`` may return a path string (e.g. ``"A/B/C"``)
        when supported, or an error string (starting with ``"error:"``)
        when the SDK command is missing.  Error strings are raised as
        ``PocoProtocolError`` so that PocoWorker falls through to
        ``inspect_failed``.
        """
        if method == "dump_hierarchy" and isinstance(result, dict):
            return _convert_jx4_node(result)
        if method == "inspect_by_point" and isinstance(result, str):
            if result.startswith("error:") or "Exception" in result:
                raise PocoProtocolError(result)
            return _path_to_node(result)
        return result

    # ── PC-native screenshot ──────────────────────────────────────

    def capture_screenshot(self) -> bytes:
        """Capture the primary screen using Pillow (PC only).

        JX4 SDK has no binary screenshot command over socket, so we always
        use local screen capture.  ``ImageGrab.grab`` is the default; if
        it fails (fullscreen GPU window, etc.), we fall back to a ctypes
        ``PrintWindow``-based grab that does not lock the Desktop Window
        Station.
        """
        from io import BytesIO
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(include_layered_windows=False)
        except OSError:
            # ImageGrab.grab() fails on fullscreen DirectX/OpenGL windows.
            # Fall back to a non-blocking capture that doesn't lock the
            # Window Station.
            img = self._grab_via_bitblt()
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _grab_via_bitblt(self):
        """Fallback screen grab using ctypes BitBlt — avoids Window Station lock."""
        import ctypes
        from ctypes import wintypes
        from PIL import Image

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        SRCCOPY = 0x00CC0020

        # Get screen dimensions
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)

        # Create device contexts
        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        gdi32.SelectObject(hdc_mem, hbitmap)

        # Copy screen — BitBlt without PrintWindow won't lock the station
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, 0, 0, SRCCOPY)

        # Convert to PIL Image via raw bytes
        bmi = wintypes.BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(bmi.bmiHeader)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # top-down bitmap
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB

        buf_size = width * height * 4
        buf = ctypes.create_string_buffer(buf_size)
        gdi32.GetDIBits(hdc_mem, hbitmap, 0, height, buf, bmi, 0)

        # Cleanup
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        img = Image.frombytes("RGB", (width, height), buf, "raw", "BGRX", 0, 1)
        return img


# ── JX4 → Poco hierarchy converter ─────────────────────────────────

# Fields carried over from JX4 AltElement into Poco payload.
_PAYLOAD_KEYS = frozenset({
    "x", "y", "z", "width", "height", "text", "worldX", "worldY", "worldZ",
    "id", "parentId", "cameraId", "tag", "layer", "component", "enabled",
    "activeInHierarchy", "rectTransformPoints",
})


def _convert_jx4_node(raw: dict) -> dict:
    """Recursively convert one JX4 hierarchy node (and children) to Poco format.

    Handles both the ``{"objs": {…}}`` wrapper and bare nodes.
    """
    # Unwrap {"objs": {…}} if present.
    if "objs" in raw and isinstance(raw["objs"], dict) and "name" not in raw:
        raw = raw["objs"]

    name = str(raw.get("name", ""))
    node_id = str(raw.get("id", ""))
    ntype = str(raw.get("type", raw.get("component", "GameObject")))

    payload: dict[str, Any] = {}
    for k in _PAYLOAD_KEYS:
        if k in raw:
            payload[k] = raw[k]

    children = [_convert_jx4_node(c) for c in raw.get("children", [])]

    return {
        "name": name,
        "type": ntype,
        "payload": payload,
        "node_id": node_id,
        "children": children,
    }


def _path_to_node(path: str) -> dict:
    """Convert a JX4 path string (e.g. ``"A/B/C"``) into a minimal Poco node dict."""
    parts = [p for p in path.split("/") if p]
    name = parts[-1] if parts else ""
    return {
        "name": name,
        "type": "GameObject",
        "payload": {"text": "", "path": path},
        "node_id": path,
        "children": [],
    }
