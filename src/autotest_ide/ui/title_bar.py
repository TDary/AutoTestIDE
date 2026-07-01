"""Custom frameless title bar for the main window.

Replaces the native Windows title bar with a dark-themed one that
matches the app's Catppuccin Mocha palette. Provides:
- Menu button (hamburger) on the far left
- App title in the center-left
- Minimize / maximize / close buttons on the right
- Drag-to-move and double-click-to-maximize on the title area
"""
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QIcon, QMouseEvent, QPainter, QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QFrame,
)

from autotest_ide.ui.icons import make_icon


class TitleBarButton(QPushButton):
    """Menu / min / max / close button — flat until hover."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind
        self.setFixedSize(40 if kind == "menu" else 46, 32)
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setObjectName(f"title_btn_{kind}")

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()


class CustomTitleBar(QWidget):
    """Top bar — holds menu button, title, and window controls."""

    menu_requested = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent = parent
        self.setFixedHeight(36)
        self.setObjectName("custom_title_bar")
        self.setAutoFillBackground(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Hamburger menu button (far left)
        self._btn_menu = TitleBarButton("menu")
        self._btn_menu.setText("≡")
        self._btn_menu.setToolTip("菜单")
        self._btn_menu.clicked.connect(self.menu_requested.emit)
        layout.addWidget(self._btn_menu)

        # App title
        self._title = QLabel("  AutoTest IDE")
        self._title.setObjectName("title_label")
        layout.addWidget(self._title)
        layout.addStretch()

        # Window control buttons (right)
        self._btn_min = TitleBarButton("min")
        self._btn_min.setText("—")
        self._btn_min.setToolTip("最小化")
        layout.addWidget(self._btn_min)

        self._btn_max = TitleBarButton("max")
        self._btn_max.setText("☐")
        self._btn_max.setToolTip("最大化")
        layout.addWidget(self._btn_max)

        self._btn_close = TitleBarButton("close")
        self._btn_close.setText("✕")
        self._btn_close.setToolTip("关闭")
        layout.addWidget(self._btn_close)

        self._btn_min.clicked.connect(parent.showMinimized)
        self._btn_max.clicked.connect(self._toggle_maximize)
        self._btn_close.clicked.connect(parent.close)

        self._pressed = False
        self._press_pos = QPoint()

    def set_title(self, title: str):
        self._title.setText("  " + title)

    def _toggle_maximize(self):
        if self._parent.isMaximized():
            self._parent.showNormal()
        else:
            self._parent.showMaximized()

    def update_max_button(self):
        """Call after window state changes to refresh the button glyph."""
        if self._parent.isMaximized():
            self._btn_max.setText("❐")
            self._btn_max.setToolTip("还原")
        else:
            self._btn_max.setText("☐")
            self._btn_max.setToolTip("最大化")

    def _is_on_button(self, pos) -> bool:
        child = self.childAt(pos)
        return isinstance(child, QPushButton)

    def mousePressEvent(self, event: QMouseEvent):
        if self._is_on_button(event.pos()):
            super().mousePressEvent(event)
            return
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self._press_pos = event.globalPos() - self._parent.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._pressed and (event.buttons() & Qt.LeftButton):
            if self._parent.isMaximized():
                # Restore from maximized while dragging
                self._parent.showNormal()
                # Re-anchor so the window doesn't jump
                self._press_pos = QPoint(self.width() // 2, 10)
            self._parent.move(event.globalPos() - self._press_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._pressed = False
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        # Only toggle on double-click in the title area, not on buttons
        if self._is_on_button(event.pos()):
            return
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()
            event.accept()
