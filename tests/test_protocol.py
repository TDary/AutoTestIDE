import json
import struct
import socket

import pytest

from autotest_ide.core.protocol import (
    encode_json_frame,
    MAX_FRAME_SIZE,
    read_exactly,
    read_frame,
    read_json_frame,
    read_binary_frame,
)
from autotest_ide.core.errors import PocoConnectionError, PocoProtocolError


def test_encode_json_frame_includes_4_byte_length_prefix():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "hello", "params": {}}
    frame = encode_json_frame(payload)
    assert len(frame) > 4
    (length,) = struct.unpack(">I", frame[:4])
    body = frame[4:]
    assert length == len(body)
    assert json.loads(body.decode("utf-8")) == payload


def test_encode_json_frame_uses_big_endian():
    payload = {"method": "ping"}
    frame = encode_json_frame(payload)
    (length,) = struct.unpack(">I", frame[:4])
    assert length == len(frame) - 4


def test_encode_json_frame_utf8_non_ascii():
    payload = {"method": "click", "params": {"name": "开始按钮"}}
    frame = encode_json_frame(payload)
    (length,) = struct.unpack(">I", frame[:4])
    body = frame[4:]
    assert json.loads(body.decode("utf-8"))["params"]["name"] == "开始按钮"


def _make_socketpair_with_data(data: bytes):
    """Return a connected socket whose recv yields exactly `data` then EOF."""
    server, client = socket.socketpair()
    server.sendall(data)
    server.close()
    return client


def test_read_exactly_reads_all_bytes():
    sock = _make_socketpair_with_data(b"\x00\x00\x00\x05hello")
    assert read_exactly(sock, 4) == b"\x00\x00\x00\x05"
    assert read_exactly(sock, 5) == b"hello"


def test_read_exactly_returns_empty_on_eof():
    sock = _make_socketpair_with_data(b"")
    assert read_exactly(sock, 4) == b""


def test_read_frame_reads_length_prefixed_body():
    from autotest_ide.core.protocol import encode_json_frame
    frame = encode_json_frame({"method": "ping"})
    sock = _make_socketpair_with_data(frame)
    body = read_frame(sock)
    assert json.loads(body.decode("utf-8")) == {"method": "ping"}


def test_read_frame_empty_on_eof():
    sock = _make_socketpair_with_data(b"")
    assert read_frame(sock) == b""


def test_read_frame_rejects_oversized_frame():
    sock = _make_socketpair_with_data(struct.pack(">I", MAX_FRAME_SIZE + 1))
    with pytest.raises(PocoProtocolError, match="frame too large"):
        read_frame(sock)


def test_read_json_frame_returns_parsed_dict():
    from autotest_ide.core.protocol import encode_json_frame
    sock = _make_socketpair_with_data(encode_json_frame({"id": 1, "result": "ok"}))
    assert read_json_frame(sock) == {"id": 1, "result": "ok"}


def test_read_json_frame_raises_connection_error_on_eof():
    sock = _make_socketpair_with_data(b"")
    with pytest.raises(PocoConnectionError):
        read_json_frame(sock)


def test_read_json_frame_raises_protocol_error_on_bad_json():
    sock = _make_socketpair_with_data(struct.pack(">I", 3) + b"abc")
    with pytest.raises(PocoProtocolError):
        read_json_frame(sock)
