import os
import sys

import pytest

from autotest_ide.core.device import DeviceState
from autotest_ide.core.device_manager import DeviceManager
from autotest_ide.core.errors import DeviceDiscoveryError

FAKE_ADB = [sys.executable, os.path.join(os.path.dirname(__file__), "fake_adb.py")]


def test_list_android_devices_parses_device_rows():
    mgr = DeviceManager(adb_path=FAKE_ADB)
    devices = mgr.list_android_devices()
    assert len(devices) == 3
    d = devices[0]
    assert d["serial"] == "emulator-5554"
    assert d["state"] == "device"
    assert d["model"] == "Pixel_6"
    assert d["transport_id"] == "1"
    assert devices[1]["serial"] == "deadbeef"
    assert devices[1]["state"] == "offline"
    assert devices[2]["serial"] == "cafebabe"
    assert devices[2]["state"] == "unauthorized"


def test_list_android_devices_returns_empty_when_no_devices(monkeypatch):
    empty_adb = [sys.executable, "-c", "print('List of devices attached')"]
    mgr = DeviceManager(adb_path=empty_adb)
    assert mgr.list_android_devices() == []


def test_list_android_devices_adb_failure_raises():
    bogus = [sys.executable, "-c", "import sys; sys.exit(1)"]
    mgr = DeviceManager(adb_path=bogus)
    with pytest.raises(DeviceDiscoveryError):
        mgr.list_android_devices()


def test_list_local_devices_finds_open_port(fake_server):
    mgr = DeviceManager()
    found = mgr.list_local_devices(ports=[fake_server.port])
    assert len(found) == 1
    assert found[0]["host"] == "127.0.0.1"
    assert found[0]["port"] == fake_server.port


def test_list_local_devices_returns_empty_when_nothing_listening():
    mgr = DeviceManager()
    found = mgr.list_local_devices(ports=[1])
    assert found == []


def test_list_local_devices_default_ports():
    mgr = DeviceManager()
    found = mgr.list_local_devices()
    assert isinstance(found, list)


def test_connect_local_sets_active_and_returns_device(fake_server):
    mgr = DeviceManager()
    device = mgr.connect_local(port=fake_server.port)
    try:
        assert mgr.active is device
        assert device.status == DeviceState.ONLINE
        assert device.name == f"localhost:{fake_server.port}"
    finally:
        mgr.disconnect_active()
    assert mgr.active is None


def test_connect_local_default_name():
    mgr = DeviceManager()
    device = mgr.connect_local(port=1)
    assert device.status == DeviceState.OFFLINE
    assert mgr.active is device
    mgr.shutdown()


def test_connect_android_uses_fake_adb(fake_server):
    mgr = DeviceManager(adb_path=FAKE_ADB)
    device = mgr.connect_android(serial="emulator-5554", remote_port=5001)
    assert device.status == DeviceState.OFFLINE
    assert device.name == "emulator-5554"
    mgr.shutdown()


def test_disconnect_active_clears_active(fake_server):
    mgr = DeviceManager()
    mgr.connect_local(port=fake_server.port)
    assert mgr.active is not None
    mgr.disconnect_active()
    assert mgr.active is None


def test_shutdown_disconnects_all_devices(fake_server):
    mgr = DeviceManager()
    d1 = mgr.connect_local(port=fake_server.port)
    mgr.disconnect_active()
    mgr.shutdown()
    assert d1.status == DeviceState.DISCONNECTED


def test_atexit_registered_on_first_connect(fake_server, monkeypatch):
    registered = []
    monkeypatch.setattr("atexit.register", lambda fn: registered.append(fn))
    mgr = DeviceManager()
    assert mgr._atexit_registered is False
    mgr.connect_local(port=fake_server.port)
    assert mgr._atexit_registered is True
    assert len(registered) == 1
    mgr.shutdown()
