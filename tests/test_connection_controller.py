"""Tests for ConnectionController — device connect/disconnect lifecycle and worker orchestration."""

import threading
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication

from autotest_ide.core.device import Device, DeviceState
from autotest_ide.ui.connection_controller import ConnectionController


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ── Mock worker classes ──────────────────────────────────────────
# We patch real worker classes with mock QObject-based classes that have
# the same signals but do NOT start real threads.  Real threads would
# loop forever in tests (ScreenshotWorker polls indefinitely).

class MockPocoWorker(QObject):
    inspect_result = pyqtSignal(dict, bytes)
    inspect_failed = pyqtSignal(str, int, int)
    swipe_done = pyqtSignal(bytes)

    def __init__(self, device, parent=None):
        super().__init__(parent)
        self._device = device
        self._running = False

    def isRunning(self):
        return self._running

    def inspect(self, x, y):
        pass

    def long_press(self, x, y, duration=2.0):
        pass

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        pass

    def input_text(self, x, y, text):
        pass

    def quit(self):
        self._running = False

    def wait(self, ms):
        pass


class MockScreenshotWorker(QObject):
    screenshot_ready = pyqtSignal(bytes)
    screenshot_failed = pyqtSignal()

    def __init__(self, device, fps=5, parent=None):
        super().__init__(parent)
        self._device = device
        self._stop_event = threading.Event()

    def start(self):
        pass

    def stop(self):
        pass

    def requestInterruption(self):
        pass


class MockDeviceBridge(QObject):
    status_changed = pyqtSignal(str)

    def __init__(self, device, parent=None):
        super().__init__(parent)
        self._device = device


@pytest.fixture
def mock_workers():
    """Patch real worker classes with mock implementations that don't start threads."""
    with patch("autotest_ide.ui.connection_controller.PocoWorker", MockPocoWorker), \
         patch("autotest_ide.ui.connection_controller.ScreenshotWorker", MockScreenshotWorker), \
         patch("autotest_ide.ui.connection_controller.DeviceBridge", MockDeviceBridge):
        yield


def _make_device(status=DeviceState.ONLINE):
    device = MagicMock(spec=Device)
    device.status = status
    device.name = "test_device"
    device.last_error = None
    device.device_type = "android"
    # poco client mock
    device.poco = MagicMock()
    device.poco.protocol_version = "1.0"
    device.poco.port = 13000
    device.poco.get_root.return_value = {
        "name": "root", "type": "Node", "payload": {}, "children": []
    }
    device.poco._flatten_tree.return_value = [
        {"name": "root", "node_id": "root", "payload": {}}
    ]
    return device


def _make_device_mgr():
    mgr = MagicMock()
    mgr.active = None
    mgr.connect_android = MagicMock()
    mgr.connect_local = MagicMock()
    mgr.connect_ip = MagicMock()
    mgr.disconnect_active = MagicMock()
    return mgr


# ── Helpers for synchronous connect in tests ──────────────────────
# The public connect_android/connect_local/connect_ip methods spawn a
# background thread and return immediately.  In tests we call the
# synchronous _do_handshake_* methods directly (they call device_mgr
# and emit handshake_done).  For tests that just need a "connected"
# state (workers, signal forwarding), calling _on_device_connected
# directly is simpler and avoids needing a Qt event loop.

_DUMMY_PROTOCOL = None


def _sync_connect_android(cc, serial="test", remote_port=13000):
    cc._do_handshake_android(serial, remote_port, _DUMMY_PROTOCOL)


def _sync_connect_local(cc, port=13000):
    cc._do_handshake_local(port, _DUMMY_PROTOCOL)


def _sync_connect_ip(cc, host="127.0.0.1", port=13000):
    cc._do_handshake_ip(host, port, _DUMMY_PROTOCOL)


def _direct_connect(cc, device):
    """Call _on_device_connected directly — simplest way to get a connected state in tests."""
    cc._on_device_connected(device)


# ── Initial state ───────────────────────────────────────────────

def test_initial_state(qtbot, mock_workers):
    mgr = _make_device_mgr()
    cc = ConnectionController(mgr)
    assert cc.poco_worker is None
    assert cc.has_screenshot_worker is False
    assert cc.active_device is None
    assert cc.cached_flat == []
    assert cc.cached_root == {}


# ── connect_android ──────────────────────────────────────────────

def test_connect_android_calls_device_mgr(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    connected = []
    cc.device_connected.connect(lambda d: connected.append(d))

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_android(cc, serial="emulator-5554")

    mgr.connect_android.assert_called_once()
    assert len(connected) == 1
    assert connected[0] is device


def test_connect_android_emits_connection_failed_on_exception(qtbot, mock_workers):
    mgr = _make_device_mgr()
    mgr.connect_android.side_effect = RuntimeError("adb failed")
    cc = ConnectionController(mgr)

    failed = []
    cc.connection_failed.connect(lambda e: failed.append(e))

    with qtbot.waitSignal(cc.connection_failed, timeout=3000):
        _sync_connect_android(cc, serial="dead")

    assert len(failed) == 1
    assert "adb failed" in failed[0]


def test_connect_android_emits_connection_failed_when_device_not_online(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device(status=DeviceState.OFFLINE)
    device._last_error = "port forward failed"
    mgr.connect_android.return_value = device
    cc = ConnectionController(mgr)

    failed = []
    cc.connection_failed.connect(lambda e: failed.append(e))

    with qtbot.waitSignal(cc.connection_failed, timeout=3000):
        _sync_connect_android(cc, serial="emulator-5554")

    assert len(failed) == 1
    assert "offline" in failed[0].lower()


# ── connect_local ────────────────────────────────────────────────

def test_connect_local_calls_device_mgr(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_local.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    connected = []
    cc.device_connected.connect(lambda d: connected.append(d))

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_local(cc, port=13000)

    mgr.connect_local.assert_called_once()
    assert len(connected) == 1


def test_connect_local_emits_connection_failed_on_exception(qtbot, mock_workers):
    mgr = _make_device_mgr()
    mgr.connect_local.side_effect = RuntimeError("port not open")
    cc = ConnectionController(mgr)

    failed = []
    cc.connection_failed.connect(lambda e: failed.append(e))

    with qtbot.waitSignal(cc.connection_failed, timeout=3000):
        _sync_connect_local(cc, port=1)

    assert len(failed) == 1


# ── connect_ip ────────────────────────────────────────────────────

def test_connect_ip_calls_device_mgr(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_ip.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    connected = []
    cc.device_connected.connect(lambda d: connected.append(d))

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_ip(cc, host="192.168.1.100", port=13000)

    mgr.connect_ip.assert_called_once()
    assert len(connected) == 1


def test_connect_ip_emits_connection_failed_on_exception(qtbot, mock_workers):
    mgr = _make_device_mgr()
    mgr.connect_ip.side_effect = RuntimeError("timeout")
    cc = ConnectionController(mgr)

    failed = []
    cc.connection_failed.connect(lambda e: failed.append(e))

    with qtbot.waitSignal(cc.connection_failed, timeout=3000):
        _sync_connect_ip(cc, host="bad.host", port=13000)

    assert len(failed) == 1


# ── disconnect ────────────────────────────────────────────────────

def test_disconnect_stops_workers_and_clears_state(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    # Connect first
    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_android(cc, serial="test")

    assert cc.poco_worker is not None
    assert cc.has_screenshot_worker is True
    assert cc.cached_flat != []

    # Now disconnect
    disconnected = []
    cc.device_disconnected.connect(lambda: disconnected.append(True))

    with qtbot.waitSignal(cc.device_disconnected, timeout=3000):
        cc.disconnect()

    mgr.disconnect_active.assert_called_once()
    assert cc.poco_worker is None
    assert cc.has_screenshot_worker is False
    assert cc.cached_flat == []
    assert cc.cached_root == {}
    assert len(disconnected) == 1


# ── Signal forwarding ─────────────────────────────────────────────

def test_inspect_result_forwarded_from_poco_worker(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_android(cc, serial="test")

    pw = cc.poco_worker
    assert pw is not None

    # Emit from mock PocoWorker — should forward through CC
    node = {"name": "Btn", "payload": {"pos": [100, 200]}, "node_id": "1"}
    screenshot_bytes = b"\x89PNG fake"

    with qtbot.waitSignal(cc.inspect_result, timeout=3000):
        pw.inspect_result.emit(node, screenshot_bytes)

    # Verify by checking the last signal emission
    # The signal should have been received


def test_inspect_failed_forwarded_from_poco_worker(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_android(cc, serial="test")

    pw = cc.poco_worker

    with qtbot.waitSignal(cc.inspect_failed, timeout=3000):
        pw.inspect_failed.emit("timeout", 100, 200)


def test_swipe_done_forwarded_from_poco_worker(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_android(cc, serial="test")

    pw = cc.poco_worker

    with qtbot.waitSignal(cc.swipe_done, timeout=3000):
        pw.swipe_done.emit(b"\x89PNG swipe")


def test_status_changed_forwarded_from_device_bridge(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_android(cc, serial="test")

    bridge = cc._device_bridge
    assert bridge is not None

    with qtbot.waitSignal(cc.status_changed, timeout=3000):
        bridge.status_changed.emit("online")


# ── Tree loading ──────────────────────────────────────────────────

def test_tree_loaded_emitted_on_connect(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    trees = []
    cc.tree_loaded.connect(lambda flat: trees.append(flat))

    with qtbot.waitSignal(cc.tree_loaded, timeout=3000):
        _sync_connect_android(cc, serial="test")

    assert len(trees) == 1
    assert cc.cached_flat == trees[0]
    assert cc.cached_root is not None


def test_load_tree_refreshes_from_active_device(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.active = device
    cc = ConnectionController(mgr)

    trees = []
    cc.tree_loaded.connect(lambda flat: trees.append(flat))

    cc.load_tree()  # now async — verify that get_root is called in background

    # The background thread should call get_root (give it a moment)
    import time
    time.sleep(0.5)

    device.poco.get_root.assert_called_once()


def test_load_tree_skips_when_no_device(qtbot, mock_workers):
    mgr = _make_device_mgr()
    mgr.active = None
    cc = ConnectionController(mgr)

    trees = []
    cc.tree_loaded.connect(lambda flat: trees.append(flat))

    cc.load_tree()

    assert len(trees) == 0


# ── stop_workers_for_offline / restart_screenshot ─────────────────

def test_stop_workers_for_offline(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_android(cc, serial="test")

    assert cc.poco_worker is not None
    assert cc.has_screenshot_worker is True

    cc.stop_workers_for_offline()

    assert cc.poco_worker is None
    assert cc.has_screenshot_worker is False


def test_has_screenshot_worker_property(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    assert cc.has_screenshot_worker is False

    with qtbot.waitSignal(cc.device_connected, timeout=3000):
        _sync_connect_android(cc, serial="test")

    assert cc.has_screenshot_worker is True

    cc.stop_workers_for_offline()
    assert cc.has_screenshot_worker is False


def test_restart_screenshot_creates_new_worker(qtbot, mock_workers):
    mgr = _make_device_mgr()
    device = _make_device()
    mgr.connect_android.return_value = device
    mgr.active = device
    cc = ConnectionController(mgr)

    # Start without connecting first — no screenshot worker yet
    assert cc.has_screenshot_worker is False

    # restart_screenshot should create a worker
    cc.restart_screenshot(device)
    assert cc.has_screenshot_worker is True

    # Calling again should replace the old one
    cc.restart_screenshot(device)
    assert cc.has_screenshot_worker is True
