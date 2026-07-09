"""Connection controller -- manages device connect/disconnect lifecycle and worker orchestration.

Owns PocoWorker, ScreenshotWorker, and DeviceBridge instances.  Emits signals
that MainWindow receives so the UI can update without knowing about worker
creation details.

All connect operations are run in a background thread to avoid blocking the UI.
"""

import threading

from PyQt5.QtCore import QObject, pyqtSignal

from autotest_ide.core.device import Device, DeviceState
from autotest_ide.core.device_manager import DeviceManager
from autotest_ide.core.log import getLogger
from autotest_ide.ui.threads import PocoWorker, ScreenshotWorker, DeviceBridge

logger = getLogger(__name__)


class ConnectionController(QObject):
    """Manages device connection lifecycle and worker orchestration."""

    device_connected = pyqtSignal(object)   # Device
    device_disconnected = pyqtSignal()
    status_changed = pyqtSignal(str)        # forwarded from DeviceBridge
    inspect_result = pyqtSignal(dict, bytes)
    inspect_failed = pyqtSignal(str, int, int)
    swipe_done = pyqtSignal(bytes)
    screenshot_ready = pyqtSignal(bytes)
    tree_loaded = pyqtSignal(list)          # flat node list
    connection_failed = pyqtSignal(str)     # error message

    def __init__(self, device_mgr: DeviceManager, parent=None):
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._poco_worker: PocoWorker | None = None
        self._screenshot_worker: ScreenshotWorker | None = None
        self._device_bridge: DeviceBridge | None = None
        self._cached_flat: list = []
        self._cached_root: dict | None = None

    # -- Public API -----------------------------------------------------------

    def connect_android(self, serial: str, sdk_name: str, remote_port: int = 13000):
        """Connect an Android device asynchronously (non-blocking)."""
        protocol = self._load_protocol(sdk_name)
        threading.Thread(
            target=self._do_connect_android,
            args=(serial, remote_port, protocol),
            daemon=True,
        ).start()

    def connect_local(self, port: int, sdk_name: str):
        """Connect to a local port asynchronously (non-blocking)."""
        protocol = self._load_protocol(sdk_name)
        threading.Thread(
            target=self._do_connect_local,
            args=(port, protocol),
            daemon=True,
        ).start()

    def connect_ip(self, host: str, port: int, sdk_name: str):
        """Connect to an IP device asynchronously (non-blocking)."""
        protocol = self._load_protocol(sdk_name)
        threading.Thread(
            target=self._do_connect_ip,
            args=(host, port, protocol),
            daemon=True,
        ).start()

    def _do_connect_android(self, serial: str, remote_port: int, protocol):
        """Background thread: connect Android device."""
        try:
            device = self._device_mgr.connect_android(
                serial, remote_port=remote_port, protocol=protocol,
            )
            if device.status != DeviceState.ONLINE:
                msg = f"device offline ({device.status})"
                if device.last_error:
                    msg = f"{device.last_error} — device offline"
                logger.warning("Android device not online: %s", msg)
                self.connection_failed.emit(msg)
                return
            self._on_device_connected(device)
        except Exception as e:
            logger.warning("Android connect failed: %s", e)
            self.connection_failed.emit(str(e))

    def _do_connect_local(self, port: int, protocol):
        """Background thread: connect local port."""
        try:
            device = self._device_mgr.connect_local(port, protocol=protocol)
            if device.status != DeviceState.ONLINE:
                msg = device.last_error or f"device offline ({device.status})"
                logger.warning("Local device not online: %s", msg)
                self.connection_failed.emit(msg)
                return
            self._on_device_connected(device)
        except Exception as e:
            logger.warning("Local connect failed: %s", e)
            self.connection_failed.emit(str(e))

    def _do_connect_ip(self, host: str, port: int, protocol):
        """Background thread: connect IP device."""
        try:
            device = self._device_mgr.connect_ip(host=host, port=port, protocol=protocol)
            if device.status != DeviceState.ONLINE:
                msg = device.last_error or f"device offline ({device.status})"
                logger.warning("IP device not online: %s", msg)
                self.connection_failed.emit(msg)
                return
            self._on_device_connected(device)
        except Exception as e:
            logger.warning("IP connect failed: %s", e)
            self.connection_failed.emit(str(e))

    def disconnect(self):
        """Disconnect device and stop all workers."""
        self._stop_screenshot_worker()
        if self._poco_worker:
            self._poco_worker.quit()
            self._poco_worker.wait(2000)
            self._poco_worker = None
        if self._device_bridge:
            self._device_bridge = None
        self._device_mgr.disconnect_active()
        self._cached_flat = []
        self._cached_root = None
        self.device_disconnected.emit()

    @property
    def cached_flat(self) -> list:
        return self._cached_flat

    @property
    def cached_root(self) -> dict:
        return self._cached_root or {}

    @property
    def active_device(self):
        return self._device_mgr.active

    @property
    def poco_worker(self) -> PocoWorker | None:
        return self._poco_worker

    @property
    def has_screenshot_worker(self) -> bool:
        return self._screenshot_worker is not None

    def load_tree(self):
        """Refresh tree data from active device."""
        device = self._device_mgr.active
        if device and device.poco:
            self._load_tree(device)

    def stop_workers_for_offline(self):
        """Stop screenshot and poco workers when device goes offline."""
        self._stop_screenshot_worker()
        if self._poco_worker:
            self._poco_worker.quit()
            self._poco_worker.wait(2000)
            self._poco_worker = None

    def restart_screenshot(self, device: Device):
        """Restart screenshot worker when device comes back online."""
        self._start_screenshot_worker(device)

    # -- Internal -------------------------------------------------------------

    def _on_device_connected(self, device: Device):
        """Post-connect setup: create bridge, workers, load tree."""
        # DeviceBridge
        self._device_bridge = DeviceBridge(device, self)
        self._device_bridge.status_changed.connect(self.status_changed.emit)

        # PocoWorker
        self._poco_worker = PocoWorker(device, self)
        self._poco_worker.inspect_result.connect(self.inspect_result.emit)
        self._poco_worker.inspect_failed.connect(self.inspect_failed.emit)
        self._poco_worker.swipe_done.connect(self.swipe_done.emit)

        # ScreenshotWorker
        self._start_screenshot_worker(device)

        # Load tree
        self._load_tree(device)

        # Notify MainWindow
        self.device_connected.emit(device)

    def _start_screenshot_worker(self, device: Device):
        self._stop_screenshot_worker()
        self._screenshot_worker = ScreenshotWorker(device, fps=5, parent=self)
        self._screenshot_worker.screenshot_ready.connect(self.screenshot_ready.emit)
        self._screenshot_worker.start()

    def _stop_screenshot_worker(self):
        if self._screenshot_worker:
            self._screenshot_worker.stop()
            self._screenshot_worker = None

    def _load_tree(self, device: Device):
        if device.poco:
            try:
                root = device.poco.get_root()
                self._cached_root = root
                self._cached_flat = device.poco._flatten_tree(root)
                self.tree_loaded.emit(self._cached_flat)
            except Exception as e:
                logger.warning("Tree load failed: %s", e)

    @staticmethod
    def _load_protocol(sdk_name: str):
        from autotest_ide.sdks import load_protocol
        try:
            return load_protocol(sdk_name)
        except ValueError:
            return load_protocol("jx4")
