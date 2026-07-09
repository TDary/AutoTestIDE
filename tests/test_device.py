import time

import pytest

from autotest_ide.core.device import Device, DeviceState
from autotest_ide.core.errors import DeviceError
from autotest_ide.core.forwarder import LocalForwarder


def make_local_device(local_port):
    fwd = LocalForwarder(local_port)
    return Device(name="test", device_type="windows", forwarder=fwd)


def test_device_initial_state_is_disconnected():
    device = make_local_device(5001)
    assert device.status == DeviceState.DISCONNECTED
    assert device.name == "test"
    assert device.device_type == "windows"


def test_device_poco_raises_when_not_online():
    device = make_local_device(5001)
    with pytest.raises(DeviceError, match="not online"):
        _ = device.poco


def test_device_connect_transitions_to_online(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        assert device.status == DeviceState.ONLINE
        assert device.poco is not None
    finally:
        device.disconnect()


def test_device_connect_failure_transitions_to_offline():
    device = make_local_device(1)
    device.connect()
    assert device.status == DeviceState.OFFLINE


def test_device_connect_failure_records_last_error():
    device = make_local_device(1)
    device.connect()
    assert device.status == DeviceState.OFFLINE
    assert device.last_error is not None
    assert "connect failed" in device.last_error.lower() or "connection refused" in device.last_error.lower()


def test_device_connect_success_clears_last_error(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        assert device.status == DeviceState.ONLINE
        assert device.last_error is None
    finally:
        device.disconnect()


def test_device_connect_when_not_disconnected_raises(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        with pytest.raises(DeviceError, match="already"):
            device.connect()
    finally:
        device.disconnect()


def test_device_disconnect_returns_to_disconnected(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    assert device.status == DeviceState.ONLINE
    device.disconnect()
    assert device.status == DeviceState.DISCONNECTED


def test_device_disconnect_is_idempotent(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    device.disconnect()
    device.disconnect()


def test_device_on_status_change_callback_fires(fake_server):
    statuses = []
    device = make_local_device(fake_server.port)
    device.on_status_change(lambda s: statuses.append(s))
    device.connect()
    device.disconnect()
    assert DeviceState.CONNECTING in statuses
    assert DeviceState.ONLINE in statuses
    assert DeviceState.DISCONNECTED in statuses


# --- Heartbeat tests ---


def test_heartbeat_keeps_device_online(fake_server):
    device = make_local_device(fake_server.port)
    device._heartbeat_interval = 0.1
    device.connect()
    try:
        time.sleep(0.3)
        assert device.status == DeviceState.ONLINE
    finally:
        device.disconnect()


def test_heartbeat_3_failures_flip_to_offline(fake_server):
    device = make_local_device(fake_server.port)
    device._heartbeat_interval = 0.1
    device.connect()
    assert device.status == DeviceState.ONLINE
    fake_server.drop_on_next = True
    time.sleep(1.0)
    assert device.status == DeviceState.OFFLINE
    device.disconnect()


def test_heartbeat_resets_failure_count_on_success(fake_server):
    device = make_local_device(fake_server.port)
    device._heartbeat_interval = 0.1
    device.connect()
    # Single request failure then recovery: fail_next_request returns error but keeps connection open
    fake_server.fail_next_request = True
    time.sleep(0.5)
    # Only 1 failure happened, device should still be online
    assert device.status == DeviceState.ONLINE
    device.disconnect()


def test_health_check_returns_true_when_online(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        assert device.health_check() is True
    finally:
        device.disconnect()


def test_health_check_returns_false_and_flips_offline_after_drop(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    fake_server.drop_on_next = True
    assert device.health_check() is False
    assert device.status == DeviceState.OFFLINE
    device.disconnect()


def test_health_check_returns_false_when_disconnected():
    device = make_local_device(5001)
    assert device.health_check() is False


# --- Reconnect tests ---


def test_reconnect_from_offline(fake_server):
    device = make_local_device(fake_server.port)
    device._heartbeat_interval = 0.1
    device.connect()
    fake_server.drop_on_next = True
    time.sleep(1.0)
    assert device.status == DeviceState.OFFLINE
    device.reconnect()
    assert device.status == DeviceState.ONLINE
    device.disconnect()


def test_reconnect_from_disconnected_raises(fake_server):
    device = make_local_device(fake_server.port)
    with pytest.raises(DeviceError, match="offline"):
        device.reconnect()


def test_reconnect_from_online_raises(fake_server):
    device = make_local_device(fake_server.port)
    device.connect()
    try:
        with pytest.raises(DeviceError, match="offline"):
            device.reconnect()
    finally:
        device.disconnect()
