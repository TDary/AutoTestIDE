from PyQt5.QtCore import QObject, pyqtSignal

from autotest_ide.core.locator import generate_locator_code
from autotest_ide.core.log import getLogger

logger = getLogger(__name__)


class RecordController(QObject):
    code_generated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False
        self._cached_flat: list = []

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, cached_flat: list):
        self._recording = True
        self._cached_flat = cached_flat
        logger.info("Recording started")

    def stop(self):
        self._recording = False
        self._cached_flat = []
        logger.info("Recording stopped")

    def on_inspect_result(self, node: dict, x: int, y: int):
        if not self._recording:
            return
        code = generate_locator_code(node, self._cached_flat)
        if not code:
            code = f"auto.click({x}, {y})\n"
        self.code_generated.emit(code)

    def on_inspect_failed(self, x: int, y: int):
        if not self._recording:
            return
        self.code_generated.emit(f"auto.click({x}, {y})\n")
