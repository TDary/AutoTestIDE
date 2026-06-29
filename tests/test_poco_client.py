import pytest

from autotest_ide.core.errors import (
    PocoConnectionError,
    PocoProtocolError,
    PocoRemoteError,
    PocoTimeoutError,
)
from autotest_ide.core.poco_client import PocoClient
from tests.fake_poco_server import TINY_PNG


def test_connect_and_handshake(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        assert client.server_version == "fake-1.0"
        assert client.protocol_version == "v1"
    finally:
        client.close()


def test_connect_refused_raises_connection_error():
    # port 1 is reserved, should refuse
    client = PocoClient(host="127.0.0.1", port=1)
    with pytest.raises(PocoConnectionError):
        client.connect()


def test_get_screen_size(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        assert client.get_screen_size() == {"w": 1080, "h": 1920}
    finally:
        client.close()


def test_handshake_protocol_mismatch_raises(fake_server, monkeypatch):
    # Force the client to advertise an unsupported protocol version
    monkeypatch.setattr("autotest_ide.core.poco_client.PROTOCOL_VERSION", "v99")
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    with pytest.raises(PocoProtocolError, match="protocol mismatch"):
        client.connect()


def test_get_root_returns_full_tree(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        root = client.get_root()
        assert root["name"] == "Canvas"
        assert root["children"][0]["name"] == "Button_Play"
    finally:
        client.close()


def test_dump_hierarchy_with_depth(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        shallow = client.dump_hierarchy(depth=1)
        assert shallow["children"] == []
        full = client.dump_hierarchy()
        assert len(full["children"]) == 1
    finally:
        client.close()


def test_get_attributes(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        attrs = client.get_attributes("btn_play")
        assert attrs["text"] == "Play"
        assert attrs["visibleBounds"]["width"] == 200
    finally:
        client.close()


def test_request_timeout_raises_poco_timeout_error(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    # Set delay AFTER connect so the handshake completes normally; the delay
    # then applies to the next request (get_screen_size).
    fake_server.delay = 6.0  # server responds after 6s; client timeout is 5s
    try:
        with pytest.raises(PocoTimeoutError, match="get_screen_size"):
            client.get_screen_size()
    finally:
        client.close()


def test_timeout_closes_connection(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    fake_server.delay = 6.0
    try:
        with pytest.raises(PocoTimeoutError):
            client.get_screen_size()
    except PocoTimeoutError:
        pass
    # After timeout the client is closed; further calls raise connection error
    with pytest.raises(PocoConnectionError):
        client.get_screen_size()


def test_server_drop_mid_request_raises_connection_error(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    # Tell the server to drop on the next request
    fake_server.drop_on_next = True
    with pytest.raises(PocoConnectionError):
        client.get_root()
    client.close()


def test_server_drop_then_client_closed(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    fake_server.drop_on_next = True
    with pytest.raises(PocoConnectionError):
        client.get_root()
    # Connection is now dead; subsequent calls fail
    with pytest.raises(PocoConnectionError):
        client.get_root()


def test_inspect_by_point_hits_button(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.inspect_by_point(540, 960)  # center of btn_play
        assert result["node_id"] == "btn_play"
        assert result["path"] == ["root", "btn_play"]
    finally:
        client.close()


def test_inspect_by_point_misses_returns_root(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.inspect_by_point(10, 10)  # top-left corner
        assert result["node_id"] == "root"
    finally:
        client.close()


def test_inspect_by_point_remote_error_raises_poco_remote_error(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        with pytest.raises(PocoRemoteError) as exc_info:
            client.inspect_by_point(-1, -1)
        assert exc_info.value.code == -32001
        assert "no node at point" in exc_info.value.message
    finally:
        client.close()


def test_get_attributes_node_not_found_raises_remote_error(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        with pytest.raises(PocoRemoteError) as exc_info:
            client.get_attributes("does_not_exist")
        assert exc_info.value.code == -32000
    finally:
        client.close()


def test_screenshot_returns_png_bytes(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        data = client.screenshot()
        assert isinstance(data, bytes)
        assert data == TINY_PNG
    finally:
        client.close()


def test_screenshot_two_round_trips(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        first = client.screenshot()
        second = client.screenshot()
        assert first == second == TINY_PNG
    finally:
        client.close()


def test_heartbeat_returns_true_when_healthy(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        assert client.heartbeat() is True
    finally:
        client.close()


def test_heartbeat_returns_false_after_server_drop(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    assert client.heartbeat() is True
    fake_server.drop_on_next = True
    # The next request will fail; heartbeat should return False, not raise.
    assert client.heartbeat() is False
    client.close()


def test_heartbeat_returns_false_on_closed_client(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    client.close()
    assert client.heartbeat() is False
