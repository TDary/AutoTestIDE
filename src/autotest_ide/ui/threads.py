import threading

from PyQt5.QtCore import QThread, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap

from autotest_ide.core.device import Device, DeviceState
from autotest_ide.core.log import getLogger

logger = getLogger(__name__)


class ScreenshotWorker(QThread):
    screenshot_ready = pyqtSignal(bytes)

    def __init__(self, device: Device, fps: int = 5, parent=None):
        super().__init__(parent)
        self._device = device
        self._interval = 1.0 / fps
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.wait(timeout=self._interval):
            if self._device.status != DeviceState.ONLINE:
                self._stop_event.wait(timeout=1.0)
                continue
            try:
                png_bytes = self._device.poco.screenshot()
                self.screenshot_ready.emit(png_bytes)
            except Exception:
                logger.warning("Screenshot capture failed", exc_info=True)

    def stop(self):
        self._stop_event.set()
        self.wait(2000)


class PocoWorker(QThread):
    inspect_result = pyqtSignal(dict, bytes)
    inspect_failed = pyqtSignal(str, int, int)
    swipe_done = pyqtSignal(bytes)

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self._device = device
        self._task = None

    def inspect(self, x: int, y: int):
        if self.isRunning():
            return
        self._task = ("inspect", x, y)
        self.start()

    def long_press(self, x: int, y: int, duration: float = 2.0):
        if self.isRunning():
            return
        self._task = ("long_press", x, y, duration)
        self.start()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        if self.isRunning():
            return
        self._task = ("swipe", x1, y1, x2, y2, duration)
        self.start()

    def input_text(self, x: int, y: int, text: str):
        if self.isRunning():
            return
        self._task = ("input_text", x, y, text)
        self.start()

    def run(self):
        if not self._task:
            return
        kind = self._task[0]
        try:
            if kind == "inspect":
                x, y = self._task[1], self._task[2]
                result = self._device.poco.inspect_by_point(x, y)
                shot = self._device.poco.screenshot()
                self.inspect_result.emit(result, shot)
            elif kind == "long_press":
                x, y, duration = self._task[1], self._task[2], self._task[3]
                self._device.poco.long_click(x, y, duration=duration)
                result = self._device.poco.inspect_by_point(x, y)
                shot = self._device.poco.screenshot()
                self.inspect_result.emit(result, shot)
            elif kind == "swipe":
                x1, y1, x2, y2, duration = (
                    self._task[1], self._task[2],
                    self._task[3], self._task[4], self._task[5],
                )
                self._device.poco.swipe(x1, y1, x2, y2, duration=duration)
                shot = self._device.poco.screenshot()
                self.swipe_done.emit(shot)
            elif kind == "input_text":
                x, y, text = self._task[1], self._task[2], self._task[3]
                result = self._device.poco.inspect_by_point(x, y)
                node_id = result.get("node_id", "")
                if node_id:
                    self._device.poco.set_text(node_id, text)
                shot = self._device.poco.screenshot()
                self.inspect_result.emit(result, shot)
        except Exception as e:
            if kind in ("inspect", "long_press", "input_text"):
                x = self._task[1]
                y = self._task[2]
                logger.warning("PocoWorker %s failed at (%d, %d): %s", kind, x, y, e)
                self.inspect_failed.emit(str(e), x, y)
            elif kind == "swipe":
                logger.warning("PocoWorker swipe failed: %s", e)
                self.inspect_failed.emit(str(e), 0, 0)


class DeviceScanWorker(QThread):
    devices_found = pyqtSignal(list, list)  # android_list, local_list

    def __init__(self, device_mgr, parent=None):
        super().__init__(parent)
        self._device_mgr = device_mgr

    def run(self):
        android = []
        local = []
        try:
            android = self._device_mgr.list_android_devices()
        except Exception:
            logger.warning("Android device scan failed", exc_info=True)
        try:
            local = self._device_mgr.list_local_devices()
        except Exception:
            logger.warning("Local device scan failed", exc_info=True)
        self.devices_found.emit(android, local)


class DeviceBridge(QObject):
    status_changed = pyqtSignal(str)

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self._device = device
        device.on_status_change(self._on_status)

    def _on_status(self, status):
        self.status_changed.emit(status.value)
