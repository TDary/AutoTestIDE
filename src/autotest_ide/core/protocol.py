import json
import struct
from typing import Any

from autotest_ide.core.errors import PocoProtocolError

HEADER_SIZE = 4
MAX_FRAME_SIZE = 64 * 1024 * 1024  # 64 MB safety cap


def encode_json_frame(payload: dict) -> bytes:
    """Encode a dict as a length-prefixed UTF-8 JSON frame."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body


def read_exactly(sock, n: int) -> bytes:
    """Read exactly n bytes from sock. Returns b'' if the connection closes early."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return b""
        buf.extend(chunk)
    return bytes(buf)


def read_frame(sock) -> bytes:
    """Read one length-prefixed frame body. Returns b'' on clean EOF."""
    header = read_exactly(sock, HEADER_SIZE)
    if not header:
        return b""
    (length,) = struct.unpack(">I", header)
    if length > MAX_FRAME_SIZE:
        raise PocoProtocolError(f"frame too large: {length}")
    if length == 0:
        return b""
    return read_exactly(sock, length)


def read_json_frame(sock) -> dict:
    """Read one frame and parse as JSON. Raises ConnectionError on EOF, PocoProtocolError on bad JSON."""
    body = read_frame(sock)
    if not body:
        raise ConnectionError("connection closed")
    try:
        return json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise PocoProtocolError(f"invalid JSON frame: {e}")


def read_binary_frame(sock) -> bytes:
    """Read one frame as raw bytes. Returns b'' on clean EOF."""
    return read_frame(sock)
