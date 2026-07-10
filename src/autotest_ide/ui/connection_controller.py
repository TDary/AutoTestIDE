"""Connection controller -- manages device connect/disconnect lifecycle and worker orchestration.

Owns PocoWorker, ScreenshotWorker, and DeviceBridge instances.  Emits signals
that MainWindow receives so the UI can update without knowing about worker
creation details.

Connect and disconnect operations both run in background threads to avoid
blocking the UI.  After the handshake succeeds, a signal tells the main
thread to set up workers and load data.
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

    # -- Signals to MainWindow (all emitted on main thread via Qt queued connection) --
    device_connected = pyqtSignal(object)   # Device
    device_disconnected = pyqtSignal()
    status_changed = pyqtSignal(str)        # forwarded from DeviceBridge
    inspect_result = pyqtSignal(dict, bytes)
    inspect_failed = pyqtSignal(str, int, int)
    swipe_done = pyqtSignal(bytes)
    screenshot_ready = pyqtSignal(bytes)
    tree_loaded = pyqtSignal(list)          # flat node list
    connection_failed = pyqtSignal(str)     # error message
    handshake_done = pyqtSignal(object)     # Device -- tells main thread to do post-connect setup

    def __init__(self, device_mgr: DeviceManager, parent=None):
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._poco_worker: PocoWorker | None = None
        self._screenshot_worker: ScreenshotWorker | None = None
        self._device_bridge: DeviceBridge | None = None
        self._cached_flat: list = []
        self._cached_root: dict | None = None

        # When handshake completes in background thread, do setup on main thread
        self.handshake_done.connect(self._on_device_connected)

    # -- Public API (all non-blocking) ----------------------------------------

    def connect_android(self, serial: str, sdk_name: str, remote_port: int = 13000):
        """Connect an Android device asynchronously (non-blocking)."""
        protocol = self._load_protocol(sdk_name)
        threading.Thread(
            target=self._do_handshake_android,
            args=(serial, remote_port, protocol),
            daemon=True,
        ).start()

    def connect_local(self, port: int, sdk_name: str):
        """Connect to a local port asynchronously (non-blocking)."""
        protocol = self._load_protocol(sdk_name)
        threading.Thread(
            target=self._do_handshake_local,
            args=(port, protocol),
            daemon=True,
        ).start()

    def connect_ip(self, host: str, port: int, sdk_name: str):
        """Connect to an IP device asynchronously (non-blocking)."""
        protocol = self._load_protocol(sdk_name)
        threading.Thread(
            target=self._do_handshake_ip,
            args=(host, port, protocol),
            daemon=True,
        ).start()

    def disconnect(self):
        """Disconnect device -- non-blocking, cleanup runs in background thread."""
        # Snapshot references on main thread (safe, no blocking)
        sw = self._screenshot_worker
        pw = self._poco_worker
        self._screenshot_worker = None
        self._poco_worker = None
        self._device_bridge = None
        self._cached_flat = []
        self._cached_root = None
        # Notify UI immediately
        self.device_disconnected.emit()
        # Cleanup in background thread (join/wait calls are safe there)
        threading.Thread(
            target=self._do_disconnect_cleanup,
            args=(sw, pw),
            daemon=True,
        ).start()

    def load_tree(self):
        """Refresh tree data from active device -- non-blocking."""
        device = self._device_mgr.active
        if device and device.poco:
            threading.Thread(
                target=self._do_load_tree,
                args=(device,),
                daemon=True,
            ).start()

    def stop_workers_for_offline(self):
        """Stop screenshot and poco workers when device goes offline -- non-blocking."""
        sw = self._screenshot_worker
        pw = self._poco_worker
        self._screenshot_worker = None
        self._poco_worker = None
        threading.Thread(
            target=self._do_stop_workers,
            args=(sw, pw),
            daemon=True,
        ).start()

    def restart_screenshot(self, device: Device):
        """Restart screenshot worker when device comes back online."""
        self._start_screenshot_worker(device)

    # -- Properties -----------------------------------------------------------

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

    # -- Background thread methods -------------------------------------------

    def _do_handshake_android(self, serial: str, remote_port: int, protocol):
        try:
            device = self._device_mgr.connect_android(
                serial, remote_port=remote_port, protocol=protocol,
            )
            if device.status != DeviceState.ONLINE:
                self.connection_failed.emit(f"Device offline: {device._last_error or 'unknown'}")
                return
            self.handshake_done.emit(device)
        except Exception as e:
            logger.warning("Android connect failed: %s", e)
            self.connection_failed.emit(str(e))

    def _do_handshake_local(self, port: int, protocol):
        try:
            device = self._device_mgr.connect_local(port, protocol=protocol)
            if device.status != DeviceState.ONLINE:
                self.connection_failed.emit(f"Device offline: {device._last_error or 'unknown'}")
                return
            self.handshake_done.emit(device)
        except Exception as e:
            logger.warning("Local connect failed: %s", e)
            self.connection_failed.emit(str(e))

    def _do_handshake_ip(self, host: str, port: int, protocol):
        try:
            device = self._device_mgr.connect_ip(host=host, port=port, protocol=protocol)
            if device.status != DeviceState.ONLINE:
                self.connection_failed.emit(f"Device offline: {device._last_error or 'unknown'}")
                return
            self.handshake_done.emit(device)
        except Exception as e:
            logger.warning("IP connect failed: %s", e)
            self.connection_failed.emit(str(e))

    def _do_disconnect_cleanup(self, sw, pw):
        """Background: stop workers and disconnect device (blocking joins are safe here)."""
        if sw:
            try:
                sw.stop()
            except Exception:
                logger.debug("Screenshot worker stop failed", exc_info=True)
        if pw:
            try:
                pw.quit()
                pw.wait(2000)
            except Exception:
                logger.debug("Poco worker stop failed", exc_info=True)
        self._device_mgr.disconnect_active()

    def _do_stop_workers(self, sw, pw):
        """Background: stop workers without disconnecting device."""
        if sw:
            try:
                sw.stop()
            except Exception:
                logger.debug("Screenshot worker stop failed", exc_info=True)
        if pw:
            try:
                pw.quit()
                pw.wait(2000)
            except Exception:
                logger.debug("Poco worker stop failed", exc_info=True)

    def _do_load_tree(self, device: Device):
        """Background thread: load tree data (blocking TCP call)."""
        if device.poco:
            try:
                import time; t0 = time.time()
                root = device.poco.get_root()
                self._cached_root = root
                self._cached_flat = device.poco._flatten_tree(root)
                logger.info("UI tree loaded: %d nodes in %.3fs",
                            len(self._cached_flat), time.time() - t0)
                self.tree_loaded.emit(self._cached_flat)
            except Exception as e:
                logger.warning("Tree load failed: %s", e)

    # -- Main-thread setup (after handshake succeeds) ------------------------

    def _on_device_connected(self, device: Device):
        """Post-connect setup on MAIN THREAD: create bridge, workers, load tree."""
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

        # Notify MainWindow first (so UI shows "connected")
        self.device_connected.emit(device)

        # Load tree in background thread (get_root is blocking TCP)
        threading.Thread(
            target=self._do_load_tree,
            args=(device,),
            daemon=True,
        ).start()

    # -- Internal -------------------------------------------------------------

    def _start_screenshot_worker(self, device: Device):
        self._stop_screenshot_worker_fast()
        self._screenshot_worker = ScreenshotWorker(device, fps=1, parent=self)
        self._screenshot_worker.screenshot_ready.connect(self.screenshot_ready.emit)
        # Delayed start: wait 2s after connect before first screenshot
        # to avoid BitBlt locking the Window Station during handshake
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(2000, self._screenshot_worker.start)

    def _stop_screenshot_worker_fast(self):
        """Stop screenshot worker WITHOUT blocking the main thread.

        Requests the thread to stop and detaches immediately.  The QThread
        will finish on its own (daemon=True).  This avoids the 2-second
        ``wait()`` that was blocking the UI.
        """
        sw = self._screenshot_worker
        if sw:
            sw.requestInterruption()
            sw._stop_event.set()
            self._screenshot_worker = None

    @staticmethod
    def _load_protocol(sdk_name: str):
        from autotest_ide.sdks import load_protocol
        try:
            return load_protocol(sdk_name)
        except ValueError:
            return load_protocol("jx4")
