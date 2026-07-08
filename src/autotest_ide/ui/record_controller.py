from PyQt5.QtCore import QObject, pyqtSignal

from autotest_ide.core.code_gen import OpMode, gen_click, gen_assert_exists, gen_long_click, gen_swipe, gen_input
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

    def on_inspect_result(self, node: dict, x: int, y: int, op_mode: OpMode = OpMode.CLICK, text: str = ""):
        if not self._recording:
            return

        if op_mode == OpMode.CLICK:
            code = gen_click(node, self._cached_flat, x, y)
            if code:
                assertion = gen_assert_exists(node, self._cached_flat)
                if assertion:
                    self.code_generated.emit(assertion)
                self.code_generated.emit(code)
            return

        if op_mode == OpMode.LONG_PRESS:
            code = gen_long_click(node, self._cached_flat, x, y)
            if code:
                assertion = gen_assert_exists(node, self._cached_flat)
                if assertion:
                    self.code_generated.emit(assertion)
                self.code_generated.emit(code)
            return

        if op_mode == OpMode.INPUT:
            code = gen_input(node, self._cached_flat, x, y, text)
            if code:
                assertion = gen_assert_exists(node, self._cached_flat)
                if assertion:
                    self.code_generated.emit(assertion)
                self.code_generated.emit(code)
            return

    def on_inspect_failed(self, x: int, y: int, op_mode: OpMode = OpMode.CLICK, text: str = ""):
        if not self._recording:
            return

        if op_mode == OpMode.CLICK:
            self.code_generated.emit(f"auto.click({x}, {y})\n")
        elif op_mode == OpMode.LONG_PRESS:
            self.code_generated.emit(f"auto.long_click({x}, {y})\n")
        elif op_mode == OpMode.INPUT:
            self.code_generated.emit(f"auto.click({x}, {y})  # set_text fallback\n")
        else:
            self.code_generated.emit(f"auto.click({x}, {y})\n")

    def on_swipe_done(self, x1: int, y1: int, x2: int, y2: int):
        if not self._recording:
            return
        self.code_generated.emit(gen_swipe(x1, y1, x2, y2))
