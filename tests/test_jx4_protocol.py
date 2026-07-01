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
    _convert_jx4_node,
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
    assert p.resolve_method("dump_hierarchy") == "getHierarchy"
    assert p.resolve_method("click") == "tap"
    assert p.resolve_method("get_screen_size") == "getScreen"
    assert p.resolve_method("get_server_version") == "getServerVersion"
    # Unknown passes through
    assert p.resolve_method("customThing") == "customThing"


def test_read_response_string():
    server, client = socket.socketpair()
    # JX4 wraps payloads in altstart::...::altend
    server.sendall(b"altstart::1.0.0::altLog::::altend")
    server.close()
    result = _read_response(client)
    assert result == "1.0.0"


def test_read_response_json():
    server, client = socket.socketpair()
    payload = 'altstart::{"node_id":"root"}::altLog::::altend'
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
    # Simulate a base64 PNG response wrapped in JX4 envelope
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    b64 = base64.b64encode(fake_png).decode("ascii")
    envelope = f"altstart::{b64}::altLog::::altend".encode("ascii")

    server, client = socket.socketpair()
    server.sendall(envelope)
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


# ── hierarchy converter tests ──────────────────────────────────────

def test_convert_jx4_node_bare():
    raw = {
        "id": -21912,
        "name": "Denglu_NanNv_New(Clone)",
        "x": 0, "y": 0,
        "children": [
            {"id": 100, "name": "BtnStart", "x": 100, "y": 200, "children": []},
        ],
    }
    result = _convert_jx4_node(raw)
    assert result["name"] == "Denglu_NanNv_New(Clone)"
    assert result["node_id"] == "-21912"
    assert result["type"] == "GameObject"
    assert result["payload"]["x"] == 0
    assert result["payload"]["y"] == 0
    assert len(result["children"]) == 1
    child = result["children"][0]
    assert child["name"] == "BtnStart"
    assert child["node_id"] == "100"
    assert child["children"] == []


def test_convert_jx4_node_objs_wrapper():
    raw = {
        "objs": {
            "id": 1,
            "name": "Root",
            "children": [],
        }
    }
    result = _convert_jx4_node(raw)
    assert result["name"] == "Root"
    assert result["node_id"] == "1"
    assert result["children"] == []


def test_convert_jx4_node_with_component():
    raw = {
        "id": 55,
        "name": "Panel",
        "component": "UnityEngine.UI.Image",
        "children": [],
    }
    result = _convert_jx4_node(raw)
    assert result["type"] == "UnityEngine.UI.Image"
    assert result["payload"]["component"] == "UnityEngine.UI.Image"


def test_transform_result_dump_hierarchy():
    p = JX4Protocol()
    raw = {"id": 1, "name": "A", "children": []}
    result = p.transform_result("dump_hierarchy", raw)
    assert result["name"] == "A"
    assert "node_id" in result
    assert "payload" in result


def test_transform_result_passthrough():
    p = JX4Protocol()
    assert p.transform_result("click", {"ok": True}) == {"ok": True}
    assert p.transform_result("dump_hierarchy", "not a dict") == "not a dict"


def test_convert_jx4_node_text_in_payload():
    raw = {
        "id": 10,
        "name": "Label",
        "text": "Hello",
        "children": [],
    }
    result = _convert_jx4_node(raw)
    assert result["payload"]["text"] == "Hello"


def test_capture_screenshot_returns_png():
    p = JX4Protocol()
    data = p.capture_screenshot()
    assert data is not None
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 100
