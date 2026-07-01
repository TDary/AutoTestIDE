import json
import struct
import socket

import pytest

from autotest_ide.core.protocol import (
    encode_command,
    encode_json_frame,
    MAX_FRAME_SIZE,
    read_exactly,
    read_frame,
    read_json_frame,
    read_binary_frame,
)
from autotest_ide.core.errors import PocoConnectionError, PocoProtocolError


def test_encode_command_basic():
    data = encode_command("getServerVersion")
    assert data == b"getServerVersion \n"


def test_encode_command_with_args():
    data = encode_command("Click", 540, 960)
    assert data == b"Click 540 960 \n"


def test_encode_command_with_kwargs():
    data = encode_command("Dump", "onlyVisibleNode=True")
    assert data == b"Dump onlyVisibleNode=True \n"


def test_encode_command_mixed():
    data = encode_command("GetNodeAttr", "btn_play", "text")
    assert data == b"GetNodeAttr btn_play text \n"


def test_encode_json_frame_includes_4_byte_length_prefix():
    payload = {"result": "ok"}
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


def test_read_json_frame_returns_parsed_value():
    sock = _make_socketpair_with_data(encode_json_frame({"result": "ok"}))
    assert read_json_frame(sock) == {"result": "ok"}


def test_read_json_frame_raises_connection_error_on_eof():
    sock = _make_socketpair_with_data(b"")
    with pytest.raises(PocoConnectionError):
        read_json_frame(sock)


def test_read_json_frame_raises_protocol_error_on_bad_json():
    sock = _make_socketpair_with_data(struct.pack(">I", 3) + b"abc")
    with pytest.raises(PocoProtocolError):
        read_json_frame(sock)
