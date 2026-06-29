import webbrowser
from pathlib import Path

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QVBoxLayout, QWidget


class ReportView(QWidget):
    """Displays HTML test report. Tries QWebEngineView, falls back to browser."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._web_view = None
        self._use_webengine = False
        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineView
            self._web_view = QWebEngineView()
            self._layout.addWidget(self._web_view)
            self._use_webengine = True
        except ImportError:
            pass

    def show_report(self, html_path: str):
        path = Path(html_path)
        if self._use_webengine and self._web_view:
            url = QUrl.fromLocalFile(str(path.resolve()))
            self._web_view.setUrl(url)
        else:
            webbrowser.open(str(path.resolve()))
