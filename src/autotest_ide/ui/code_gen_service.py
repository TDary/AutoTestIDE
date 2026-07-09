"""Unified code generation service for both recording and non-recording modes.

Supersedes RecordController by handling code generation regardless of whether
recording is active.  In recording mode an assert_exists line is prepended
before each operation; in non-recording mode only the operation line is
emitted.
"""

from PyQt5.QtCore import QObject, pyqtSignal

from autotest_ide.core.code_gen import (
    OpMode, gen_click, gen_assert_exists,
    gen_long_click, gen_input, gen_swipe,
)
from autotest_ide.core.log import getLogger

logger = getLogger(__name__)


class CodeGenService(QObject):
    """Unified code generation service for both recording and non-recording modes."""
    code_insert_requested = pyqtSignal(str)  # emitted for each code line to insert

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self):
        self._recording = True
        logger.info("Recording started")

    def stop_recording(self):
        self._recording = False
        logger.info("Recording stopped")

    def on_inspect_result(self, node: dict, flat_nodes: list,
                          x: int, y: int, op_mode: OpMode = OpMode.CLICK,
                          text: str = ""):
        """Handle inspect success -- generate code based on op_mode.

        In recording mode, an assert_exists line is emitted before the
        operation code.  In non-recording mode only the operation is emitted.
        """
        if op_mode == OpMode.CLICK:
            code = gen_click(node, flat_nodes, x, y)
        elif op_mode == OpMode.LONG_PRESS:
            code = gen_long_click(node, flat_nodes, x, y)
        elif op_mode == OpMode.INPUT:
            code = gen_input(node, flat_nodes, x, y, text)
        else:
            code = gen_click(node, flat_nodes, x, y)

        if code:
            # Recording mode: insert assert before operation
            if self._recording:
                assertion = gen_assert_exists(node, flat_nodes)
                if assertion:
                    self.code_insert_requested.emit(assertion)
            self.code_insert_requested.emit(code)

    def on_inspect_failed(self, x: int, y: int,
                          op_mode: OpMode = OpMode.CLICK,
                          text: str = ""):
        """Handle inspect failure -- generate fallback coordinate code."""
        if op_mode == OpMode.CLICK:
            self.code_insert_requested.emit(f"auto.click({x}, {y})\n")
        elif op_mode == OpMode.LONG_PRESS:
            self.code_insert_requested.emit(f"auto.long_click({x}, {y})\n")
        elif op_mode == OpMode.INPUT:
            self.code_insert_requested.emit(f"auto.click({x}, {y})  # set_text fallback\n")
        else:
            self.code_insert_requested.emit(f"auto.click({x}, {y})\n")

    def on_swipe_done(self, x1: int, y1: int, x2: int, y2: int):
        """Handle swipe completion -- generate swipe code."""
        code = gen_swipe(x1, y1, x2, y2)
        if code:
            self.code_insert_requested.emit(code)
