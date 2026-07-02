import threading

from PyQt5.QtCore import QThread, QObject, pyqtSignal
from PyQt5.QtGui import QPixmap

from autotest_ide.core.device import Device
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
            if self._device.status != "online":
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
    inspect_failed = pyqtSignal(str)

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self._device = device
        self._task = None

    def inspect(self, x: int, y: int):
        self._task = ("inspect", x, y)
        self.start()

    def run(self):
        if not self._task:
            return
        kind = self._task[0]
        if kind == "inspect":
            x, y = self._task[1], self._task[2]
            try:
                result = self._device.poco.inspect_by_point(x, y)
                shot = self._device.poco.screenshot()
                self.inspect_result.emit(result, shot)
            except Exception as e:
                logger.warning("PocoWorker inspect failed at (%d, %d): %s", x, y, e)
                self.inspect_failed.emit(str(e))


class DeviceBridge(QObject):
    status_changed = pyqtSignal(str)

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self._device = device
        device.on_status_change(self._on_status)

    def _on_status(self, status: str):
        self.status_changed.emit(status)
