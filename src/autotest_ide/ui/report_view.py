import webbrowser
from pathlib import Path

from PyQt5.QtWidgets import QVBoxLayout, QWidget, QLabel

from autotest_ide.core.log import getLogger

logger = getLogger(__name__)


class ReportView(QWidget):
    """Displays HTML test report in the system browser."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("运行脚本后将在此处显示报告链接")
        self._label.setAlignment(4)  # Qt.AlignHCenter
        self._layout.addWidget(self._label)

    def show_report(self, html_path: str):
        path = Path(html_path)
        self._label.setText(f'报告已生成: <a href="{html_path}">{html_path}</a>')
        self._label.setOpenExternalLinks(True)
        webbrowser.open(str(path.resolve()))
