import html

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QFont, QTextCharFormat, QColor
from PyQt5.QtWidgets import QTextEdit


class Console(QTextEdit):
    _FMT_ERROR = QColor("#f38ba8")
    _FMT_WARN = QColor("#f9e2af")
    _FMT_INFO = QColor("#cdd6f4")
    _FMT_DEBUG = QColor("#6c7086")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self._error_fmt = QTextCharFormat()
        self._error_fmt.setForeground(self._FMT_ERROR)
        self._warn_fmt = QTextCharFormat()
        self._warn_fmt.setForeground(self._FMT_WARN)
        self._debug_fmt = QTextCharFormat()
        self._debug_fmt.setForeground(self._FMT_DEBUG)

    def append_text(self, text: str, is_error: bool = False):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = self._error_fmt if is_error else None
        if fmt:
            cursor.insertText(text, fmt)
        else:
            cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_error(self, text: str):
        self.append_text(text, is_error=True)

    def append_warn(self, text: str):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + "\n", self._warn_fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_debug(self, text: str):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + "\n", self._debug_fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def clear_output(self):
        self.clear()
