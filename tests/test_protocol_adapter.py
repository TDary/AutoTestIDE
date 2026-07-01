import pytest

from autotest_ide.core.protocol_base import PocoProtocol
from autotest_ide.core.protocol_poco import PocoTextProtocol
from autotest_ide.core.poco_client import PocoClient


def test_text_protocol_method_map():
    p = PocoTextProtocol()
    assert p.resolve_method("dump_hierarchy") == "Dump"
    assert p.resolve_method("click") == "Click"
    assert p.resolve_method("set_text") == "SetText"
    assert p.resolve_method("screenshot") == "GetScreen"
    assert p.resolve_method("inspect_by_point") == "Inspect"
    assert p.resolve_method("get_attributes") == "GetNodeAttr"
    # Unknown method falls through
    assert p.resolve_method("unknown_method") == "unknown_method"


def test_client_default_protocol_is_text():
    client = PocoClient(host="127.0.0.1", port=0)
    assert isinstance(client.protocol, PocoTextProtocol)


def test_client_accepts_custom_protocol():
    class DummyProtocol(PocoProtocol):
        METHOD_MAP = {"dump_hierarchy": "customDump"}
        called = False

        def send_request(self, sock, method, args, kwargs):
            self.called = True

        def read_response(self, sock, expect_binary):
            return {"result": "ok"}

        def handshake(self, client):
            return "dummy-1.0"

    proto = DummyProtocol()
    client = PocoClient(host="127.0.0.1", port=0, protocol=proto)
    assert client.protocol is proto
    assert client.protocol.resolve_method("dump_hierarchy") == "customDump"
