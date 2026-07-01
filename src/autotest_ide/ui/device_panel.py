from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout


class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rects: list = []

    def set_rects(self, rects: list):
        self._rects = rects
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(QColor(255, 0, 0), 2, Qt.DashLine)
        painter.setPen(pen)
        for r in self._rects:
            painter.drawRect(r)
        painter.end()


class DevicePanel(QWidget):
    inspect_requested = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(250)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._screenshot_label = QLabel()
        self._screenshot_label.setAlignment(Qt.AlignCenter)
        self._screenshot_label.setStyleSheet("background-color: #1a1a2e;")
        layout.addWidget(self._screenshot_label)

        self._overlay = OverlayWidget(self._screenshot_label)
        self._overlay.setGeometry(self._screenshot_label.geometry())

        self._current_pixmap: QPixmap = QPixmap()
        self._scale_ratio: float = 1.0
        self._scaled_w: int = 0
        self._scaled_h: int = 0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0

    def update_screenshot(self, data):
        if isinstance(data, bytes):
            pm = QPixmap()
            pm.loadFromData(data)
            if pm.isNull():
                return
            self._current_pixmap = pm
        else:
            self._current_pixmap = data
        label_size = self._screenshot_label.size()
        scaled = self._current_pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._screenshot_label.setPixmap(scaled)
        if not self._current_pixmap.isNull() and label_size.width() > 0:
            self._scale_ratio = scaled.width() / self._current_pixmap.width()
            self._scaled_w = scaled.width()
            self._scaled_h = scaled.height()
            self._offset_x = (label_size.width() - scaled.width()) / 2
            self._offset_y = (label_size.height() - scaled.height()) / 2
        else:
            self._scale_ratio = 1.0

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

    def mousePressEvent(self, event):
        if self._current_pixmap.isNull() or self._scale_ratio == 0:
            return
        pos = event.pos()
        lx = pos.x() - self._screenshot_label.pos().x() - self._offset_x
        ly = pos.y() - self._screenshot_label.pos().y() - self._offset_y
        if lx < 0 or ly < 0 or lx >= self._scaled_w or ly >= self._scaled_h:
            return
        x = int(lx / self._scale_ratio)
        y = int(ly / self._scale_ratio)
        self.inspect_requested.emit(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self._screenshot_label.geometry())
