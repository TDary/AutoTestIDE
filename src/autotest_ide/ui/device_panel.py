from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QToolButton

from autotest_ide.core.code_gen import OpMode


class OverlayWidget(QWidget):
    """Semi-transparent overlay for drawing highlight rectangles, swipe lines, and failure text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rects: list = []
        self._swipe_start: QPoint = QPoint()
        self._swipe_end: QPoint = QPoint()
        self._show_swipe: bool = False
        self._fail_text: bool = False

    def set_rects(self, rects: list):
        self._rects = rects
        self.update()

    def set_swipe_line(self, start: QPoint, end: QPoint):
        self._swipe_start = start
        self._swipe_end = end
        self._show_swipe = True
        self.update()

    def clear_swipe_line(self):
        self._show_swipe = False
        self.update()

    def set_fail_text(self, active: bool):
        self._fail_text = active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # Highlight rectangles
        pen = QPen(QColor("#f38ba8"), 2, Qt.DashLine)
        painter.setPen(pen)
        for r in self._rects:
            painter.drawRect(r)
        # Swipe trajectory line
        if self._show_swipe and not self._swipe_start.isNull() and not self._swipe_end.isNull():
            line_pen = QPen(QColor("#f38ba8"), 3, Qt.SolidLine)
            painter.setPen(line_pen)
            painter.drawLine(self._swipe_start, self._swipe_end)
            # Draw circles at start and end
            painter.setBrush(QColor("#f38ba8"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self._swipe_start, 5, 5)
            painter.drawEllipse(self._swipe_end, 5, 5)
        # Screenshot failure overlay
        if self._fail_text:
            painter.fillRect(self.rect(), QColor(30, 30, 46, 200))
            font = painter.font()
            font.setPixelSize(24)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#f38ba8"))
            painter.drawText(self.rect(), Qt.AlignCenter, "截图失败")
        painter.end()


class DevicePanel(QWidget):
    """Device screenshot panel with operation mode toolbar."""

    inspect_requested = pyqtSignal(int, int)
    long_press_requested = pyqtSignal(int, int)
    swipe_requested = pyqtSignal(int, int, int, int)
    input_text_requested = pyqtSignal(int, int)
    coords_hovered = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        self.setMouseTracking(True)

        self._op_mode: OpMode = OpMode.CLICK

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Operation mode toolbar ---
        toolbar = QWidget()
        toolbar.setObjectName("op_mode_bar")
        toolbar.setFixedHeight(32)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(4, 2, 4, 2)
        tb_layout.setSpacing(2)

        self._btn_click = self._make_mode_btn("🖱️ 点击", OpMode.CLICK, True)
        self._btn_long_press = self._make_mode_btn("✋ 长按", OpMode.LONG_PRESS)
        self._btn_swipe = self._make_mode_btn("↔️ 滑动", OpMode.SWIPE)
        self._btn_input = self._make_mode_btn("⌨️ 输入", OpMode.INPUT)

        tb_layout.addWidget(self._btn_click)
        tb_layout.addWidget(self._btn_long_press)
        tb_layout.addWidget(self._btn_swipe)
        tb_layout.addWidget(self._btn_input)
        tb_layout.addStretch()
        layout.addWidget(toolbar)

        # --- Screenshot label ---
        self._screenshot_label = QLabel()
        self._screenshot_label.setAlignment(Qt.AlignCenter)
        self._screenshot_label.setStyleSheet(
            "background-color: #11111b; border: 2px solid transparent;"
        )
        layout.addWidget(self._screenshot_label)

        # --- Overlay ---
        self._overlay = OverlayWidget(self._screenshot_label)
        self._overlay.setGeometry(self._screenshot_label.geometry())

        # Screenshot geometry
        self._current_pixmap: QPixmap = QPixmap()
        self._scale_ratio: float = 1.0
        self._scaled_w: int = 0
        self._scaled_h: int = 0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0

        # Swipe state
        self._swipe_start_dev: tuple = (0, 0)
        self._swiping: bool = False

        # Screenshot failure overlay state
        self._fail_overlay_active: bool = False
        self._fail_clear_timer = QTimer(self)
        self._fail_clear_timer.setSingleShot(True)
        self._fail_clear_timer.timeout.connect(self._clear_fail_overlay)

    @property
    def op_mode(self) -> OpMode:
        return self._op_mode

    def _make_mode_btn(self, text: str, mode: OpMode, selected: bool = False) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setFixedHeight(26)
        btn.clicked.connect(lambda: self._set_op_mode(mode))
        self._update_btn_style(btn, mode == self._op_mode)
        return btn

    def _set_op_mode(self, mode: OpMode):
        self._op_mode = mode
        for btn, m in [
            (self._btn_click, OpMode.CLICK),
            (self._btn_long_press, OpMode.LONG_PRESS),
            (self._btn_swipe, OpMode.SWIPE),
            (self._btn_input, OpMode.INPUT),
        ]:
            self._update_btn_style(btn, m == mode)

    def _update_btn_style(self, btn: QToolButton, selected: bool):
        if selected:
            btn.setStyleSheet(
                "QToolButton { background: #f38ba8; color: #1e1e2e; "
                "border: none; border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: bold; }"
            )
        else:
            btn.setStyleSheet(
                "QToolButton { background: #313244; color: #cdd6f4; "
                "border: none; border-radius: 4px; padding: 2px 8px; font-size: 12px; }"
            )

    def update_screenshot(self, data):
        if isinstance(data, bytes):
            pm = QPixmap()
            pm.loadFromData(data)
            if pm.isNull():
                return
            self._current_pixmap = pm
        else:
            self._current_pixmap = data
        # Clear screenshot failure overlay on success
        if self._fail_overlay_active:
            self._fail_overlay_active = False
            self._fail_clear_timer.stop()
            self._overlay.set_fail_text(False)
        label_size = self._screenshot_label.size()
        scaled = self._current_pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.FastTransformation)
        self._screenshot_label.setPixmap(scaled)
        if not self._current_pixmap.isNull() and label_size.width() > 0:
            self._scale_ratio = scaled.width() / self._current_pixmap.width()
            self._scaled_w = scaled.width()
            self._scaled_h = scaled.height()
            self._offset_x = (label_size.width() - scaled.width()) / 2
            self._offset_y = (label_size.height() - scaled.height()) / 2
        else:
            self._scale_ratio = 1.0

    # --- Screenshot failure overlay ---

    def show_screenshot_failed(self):
        """Show a '截图失败' overlay on the screenshot area."""
        self._fail_overlay_active = True
        self._overlay.set_fail_text(True)
        self._fail_clear_timer.start(3000)

    def _clear_fail_overlay(self):
        self._fail_overlay_active = False
        self._overlay.set_fail_text(False)

    # --- IDE state border indicator ---

    def set_state_border(self, mode: str):
        """Set screenshot border color to indicate IDE state.

        mode: 'idle' -> transparent, 'recording' -> #a6e3a1, 'running' -> #f38ba8
        """
        colors = {"idle": "transparent", "recording": "#a6e3a1", "running": "#f38ba8"}
        color = colors.get(mode, "transparent")
        self._screenshot_label.setStyleSheet(
            f"background-color: #11111b; border: 2px solid {color};"
        )

    def highlight_region(self, bounds: dict):
        if self._current_pixmap.isNull() or not bounds:
            self._overlay.set_rects([])
            return
        r = self._scale_ratio
        x = int(bounds.get("x", 0) * r)
        y = int(bounds.get("y", 0) * r)
        w = int(bounds.get("width", 0) * r)
        h = int(bounds.get("height", 0) * r)
        self._overlay.set_rects([QRect(x, y, w, h)])
        self._overlay.raise_()

    def clear_highlight(self):
        self._overlay.set_rects([])

    def _widget_to_device(self, pos) -> tuple:
        """Convert widget position to device pixel coordinates."""
        lx = pos.x() - self._screenshot_label.pos().x() - self._offset_x
        ly = pos.y() - self._screenshot_label.pos().y() - self._offset_y
        if lx < 0 or ly < 0 or lx >= self._scaled_w or ly >= self._scaled_h:
            return None, None
        x = int(lx / self._scale_ratio)
        y = int(ly / self._scale_ratio)
        return x, y

    def _widget_to_overlay(self, pos) -> QPoint:
        """Convert widget position to overlay-local coordinates."""
        return QPoint(
            int(pos.x() - self._screenshot_label.pos().x() - self._offset_x),
            int(pos.y() - self._screenshot_label.pos().y() - self._offset_y),
        )

    def mousePressEvent(self, event):
        if self._current_pixmap.isNull() or self._scale_ratio == 0:
            return
        if event.button() != Qt.LeftButton:
            return
        x, y = self._widget_to_device(event.pos())
        if x is None:
            return

        if self._op_mode == OpMode.CLICK:
            self.inspect_requested.emit(x, y)
        elif self._op_mode == OpMode.LONG_PRESS:
            self.long_press_requested.emit(x, y)
        elif self._op_mode == OpMode.SWIPE:
            self._swipe_start_dev = (x, y)
            self._swiping = True
        elif self._op_mode == OpMode.INPUT:
            self.input_text_requested.emit(x, y)

    def mouseMoveEvent(self, event):
        # Always update coordinates on hover for the status bar
        x, y = self._widget_to_device(event.pos())
        if x >= 0 and y >= 0:
            self.coords_hovered.emit(x, y)
        if self._swiping:
            # Compute overlay coordinates for the swipe trajectory line
            start_overlay = self._widget_to_overlay(
                self._screenshot_label.mapFromParent(
                    QPoint(
                        int(self._swipe_start_dev[0] * self._scale_ratio + self._offset_x + self._screenshot_label.pos().x()),
                        int(self._swipe_start_dev[1] * self._scale_ratio + self._offset_y + self._screenshot_label.pos().y()),
                    )
                )
            )
            end_overlay = self._widget_to_overlay(event.pos())
            self._overlay.set_swipe_line(start_overlay, end_overlay)

    def mouseReleaseEvent(self, event):
        if not self._swiping:
            return
        self._swiping = False
        self._overlay.clear_swipe_line()

        x2, y2 = self._widget_to_device(event.pos())
        if x2 is None:
            return
        x1, y1 = self._swipe_start_dev
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx < 10 and dy < 10:
            return  # Too short, ignore
        self.swipe_requested.emit(x1, y1, x2, y2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self._screenshot_label.geometry())
