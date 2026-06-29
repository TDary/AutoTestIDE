from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QFont
from PyQt5.QtWidgets import QPlainTextEdit


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []

        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("#ff79c6"))
        keyword_fmt.setFontWeight(QFont.Bold)
        keywords = [
            "import", "from", "class", "def", "if", "elif", "else",
            "for", "while", "return", "try", "except", "finally",
            "with", "as", "and", "or", "not", "in", "is", "True", "False", "None",
        ]
        for kw in keywords:
            self._rules.append((QRegExp(r"\b" + kw + r"\b"), keyword_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#f1fa8c"))
        self._rules.append((QRegExp(r'".*"'), string_fmt))
        self._rules.append((QRegExp(r"'.*'"), string_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6272a4"))
        self._rules.append((QRegExp(r"#[^\n]*"), comment_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)


class Editor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("# 在此编写自动化脚本\npoco('Button_Play').click()")
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self._highlighter = PythonHighlighter(self.document())

    def insert_locator_code(self, code: str):
        cursor = self.textCursor()
        cursor.insertText("\n" + code)
        self.setTextCursor(cursor)
