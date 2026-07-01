import base64
import struct
import socket

import pytest

from autotest_ide.core.errors import PocoConnectionError
from autotest_ide.sdks.jx4.protocol import (
    JX4Protocol,
    _encode_request,
    _read_response,
    _parse_json_response,
)


def test_encode_request_no_args():
    data = _encode_request("getServerVersion", (), {})
    assert data == b"getServerVersion;&"


def test_encode_request_positional_args():
    data = _encode_request("tap", (540, 960), {})
    assert data == b"tap;540;960;&"


def test_encode_request_kwargs():
    data = _encode_request("screenshot", (1,), {})
    assert data == b"screenshot;1;&"


def test_encode_request_bool_true():
    data = _encode_request("enableLogging", ("true",), {})
    assert data == b"enableLogging;true;&"


def test_method_map():
    p = JX4Protocol()
    assert p.resolve_method("dump_hierarchy") == "getUiautatorTree"
    assert p.resolve_method("click") == "tap"
    assert p.resolve_method("screenshot") == "screenshot"
    assert p.resolve_method("get_server_version") == "getServerVersion"
    # Unknown passes through
    assert p.resolve_method("customThing") == "customThing"


def test_read_response_string():
    server, client = socket.socketpair()
    server.sendall(b"1.0.0&")
    server.close()
    result = _read_response(client)
    assert result == "1.0.0"


def test_read_response_json():
    server, client = socket.socketpair()
    payload = '{"node_id":"root"}&'
    server.sendall(payload.encode("utf-8"))
    server.close()
    result = _read_response(client)
    assert result == '{"node_id":"root"}'


def test_read_response_eof():
    server, client = socket.socketpair()
    server.close()
    with pytest.raises(PocoConnectionError, match="connection closed"):
        _read_response(client)


def test_parse_json_response_valid():
    assert _parse_json_response('{"width":1080}') == {"width": 1080}


def test_parse_json_response_plain_string():
    assert _parse_json_response("1.0.0") == "1.0.0"


def test_parse_json_response_empty():
    assert _parse_json_response("") == ""


def test_screenshot_decodes_base64():
    p = JX4Protocol()
    # Simulate a base64 PNG response
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    b64 = base64.b64encode(fake_png).decode("ascii")

    server, client = socket.socketpair()
    server.sendall(b64.encode("ascii") + b"&")
    server.close()

    result = p.read_response(client, expect_binary=True)
    assert result == fake_png


def test_encode_bool_styles():
    assert JX4Protocol.encode_bool(True, "true_false") == "true"
    assert JX4Protocol.encode_bool(False, "true_false") == "false"
    assert JX4Protocol.encode_bool(True, "1_0") == "1"
    assert JX4Protocol.encode_bool(False, "1_0") == "0"
    assert JX4Protocol.encode_bool(True, "True_False") == "True"
    assert JX4Protocol.encode_bool(False, "True_False") == "False"


def test_parse_bool():
    assert JX4Protocol.parse_bool("true") is True
    assert JX4Protocol.parse_bool("True") is True
    assert JX4Protocol.parse_bool("1") is True
    assert JX4Protocol.parse_bool("false") is False
    assert JX4Protocol.parse_bool("False") is False
    assert JX4Protocol.parse_bool("0") is False
    assert JX4Protocol.parse_bool("maybe") is None
