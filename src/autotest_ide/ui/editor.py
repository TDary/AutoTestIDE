from PyQt5.QtCore import QRegularExpression
from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QFont
from PyQt5.QtWidgets import QPlainTextEdit


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []

        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("#cba6f7"))
        keyword_fmt.setFontWeight(QFont.Bold)
        keywords = [
            "import", "from", "class", "def", "if", "elif", "else",
            "for", "while", "return", "try", "except", "finally",
            "with", "as", "and", "or", "not", "in", "is", "True", "False", "None",
        ]
        for kw in keywords:
            self._rules.append((QRegularExpression(r"\b" + kw + r"\b"), keyword_fmt))

        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(QColor("#fab387"))
        builtins = ["auto", "print", "range", "len", "int", "str", "float", "list", "dict", "set", "tuple"]
        for b in builtins:
            self._rules.append((QRegularExpression(r"\b" + b + r"\b"), builtin_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#a6e3a0"))
        self._rules.append((QRegularExpression(r'".*?"'), string_fmt))
        self._rules.append((QRegularExpression(r"'.*?'"), string_fmt))

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#fab387"))
        self._rules.append((QRegularExpression(r"\b[0-9]+\.?[0-9]*\b"), number_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6c7086"))
        comment_fmt.setFontItalic(True)
        self._rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class Editor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("# 在此编写自动化脚本\nauto.find_and_tap('Button_Play')")
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self._highlighter = PythonHighlighter(self.document())

    def insert_locator_code(self, code: str):
        cursor = self.textCursor()
        cursor.insertText("\n" + code)
        self.setTextCursor(cursor)
