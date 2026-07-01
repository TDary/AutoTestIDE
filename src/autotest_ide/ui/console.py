import html

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QFont
from PyQt5.QtWidgets import QTextEdit


class Console(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

    def append_text(self, text: str, is_error: bool = False):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        if is_error:
            cursor.insertHtml(f'<span style="color:red">{html.escape(text)}</span><br>')
        else:
            cursor.insertText(text + "\n")
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def clear_output(self):
        self.clear()
