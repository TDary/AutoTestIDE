import pytest

from autotest_ide.core.errors import (
    PocoConnectionError,
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
    client = PocoClient(host="127.0.0.1", port=1)
    with pytest.raises(PocoConnectionError):
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


def test_dump_hierarchy(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        full = client.dump_hierarchy(only_visible=False)
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
    # then applies to the next request.
    fake_server.delay = 15.0  # server responds after 15s; client timeout is 10s
    try:
        with pytest.raises(PocoTimeoutError, match="Dump"):
            client.dump_hierarchy()
    finally:
        client.close()


def test_timeout_closes_connection(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    fake_server.delay = 15.0
    try:
        with pytest.raises(PocoTimeoutError):
            client.dump_hierarchy()
    except PocoTimeoutError:
        pass
    # After timeout the client is closed; further calls raise connection error
    with pytest.raises(PocoConnectionError):
        client.dump_hierarchy()


def test_server_drop_mid_request_raises_connection_error(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
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
    with pytest.raises(PocoConnectionError):
        client.get_root()


def test_inspect_by_point_hits_button(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.inspect_by_point(540, 960)
        assert result["node_id"] == "btn_play"
        assert result["path"] == ["root", "btn_play"]
    finally:
        client.close()


def test_inspect_by_point_misses_returns_root(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    try:
        result = client.inspect_by_point(10, 10)
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
    assert client.heartbeat() is False
    client.close()


def test_heartbeat_returns_false_on_closed_client(fake_server):
    client = PocoClient(host=fake_server.host, port=fake_server.port)
    client.connect()
    client.close()
    assert client.heartbeat() is False
