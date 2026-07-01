"""
Modern dark theme stylesheet for AutoTest IDE.

Color palette inspired by One Dark Pro / Dracula.
Applied once in app.py via ``app.setStyleSheet(DARK_STYLE)``.
"""

DARK_STYLE = """
/* ── Global ────────────────────────────────────────────────────── */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1e1e2e;
}

/* ── Menu Bar ─────────────────────────────────────────────────── */
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
    padding: 2px;
}
QMenuBar::item {
    padding: 4px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #313244;
}
QMenu {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 28px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #45475a;
}
QMenu::separator {
    height: 1px;
    background-color: #313244;
    margin: 4px 8px;
}

/* ── Toolbar ──────────────────────────────────────────────────── */
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    spacing: 6px;
    padding: 4px 8px;
}
QToolBar::separator {
    width: 1px;
    height: 20px;
    background-color: #45475a;
    margin: 0 4px;
}
QToolBar QToolButton {
    background-color: transparent;
    color: #cdd6f4;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
}
QToolBar QToolButton:hover {
    background-color: #313244;
    border: 1px solid #45475a;
}
QToolBar QToolButton:pressed {
    background-color: #45475a;
}
QToolBar QToolButton:disabled {
    color: #585b70;
}

/* ── ComboBox ─────────────────────────────────────────────────── */
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
}
QComboBox:hover {
    border: 1px solid #89b4fa;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #cdd6f4;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    outline: none;
}

/* ── Labels in toolbar ────────────────────────────────────────── */
QToolBar QLabel {
    background-color: transparent;
    color: #a6adc8;
    font-size: 12px;
    padding: 0 4px;
}

/* ── Splitter ─────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #313244;
    width: 2px;
}
QSplitter::handle:hover {
    background-color: #89b4fa;
}

/* ── Tab Widget ───────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 4px;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    border: 1px solid #313244;
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border-bottom: 2px solid #89b4fa;
}
QTabBar::tab:hover:!selected {
    background-color: #313244;
}

/* ── Tree View ────────────────────────────────────────────────── */
QTreeView {
    background-color: #181825;
    color: #cdd6f4;
    border: none;
    alternate-background-color: #1e1e2e;
    outline: none;
}
QTreeView::item {
    padding: 3px 0;
    border: none;
}
QTreeView::item:selected {
    background-color: #45475a;
    color: #f5e0dc;
}
QTreeView::item:hover:!selected {
    background-color: #313244;
}
QHeaderView::section {
    background-color: #181825;
    color: #a6adc8;
    border: none;
    border-bottom: 1px solid #313244;
    padding: 4px 8px;
    font-weight: bold;
}

/* ── Table (Property Panel) ────────────────────────────────────── */
QTableWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: none;
    outline: none;
}
QTableWidget::item {
    padding: 4px 8px;
}
QTableWidget::item:selected {
    background-color: #45475a;
    color: #f5e0dc;
}
QTableWidget::item:hover:!selected {
    background-color: #313244;
}
QHeaderView::section {
    background-color: #181825;
    color: #a6adc8;
    border: none;
    border-bottom: 1px solid #313244;
    padding: 4px 8px;
    font-weight: bold;
}

/* ── Editor (QPlainTextEdit) ──────────────────────────────────── */
QPlainTextEdit {
    background-color: #181825;
    color: #cdd6f4;
    border: none;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
    padding: 8px;
}

/* ── Console ──────────────────────────────────────────────────── */
QTextEdit {
    background-color: #11111b;
    color: #cdd6f4;
    border: none;
    selection-background-color: #45475a;
    padding: 8px;
}

/* ── Status Bar ───────────────────────────────────────────────── */
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
    font-size: 12px;
}
QStatusBar::item {
    border: none;
    padding: 0 8px;
}
QStatusBar QLabel {
    color: #a6adc8;
    padding: 0 8px;
    border-right: 1px solid #313244;
}

/* ── Scroll Bar ───────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #181825;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background-color: #181825;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
}

/* ── Message Box ──────────────────────────────────────────────── */
QMessageBox {
    background-color: #1e1e2e;
}
QMessageBox QLabel {
    color: #cdd6f4;
}
QMessageBox QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px 20px;
    min-width: 64px;
}
QMessageBox QPushButton:hover {
    background-color: #45475a;
    border: 1px solid #89b4fa;
}

/* ── Input Dialog ─────────────────────────────────────────────── */
QInputDialog {
    background-color: #1e1e2e;
}
QInputDialog QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: #45475a;
}
QInputDialog QLineEdit:focus {
    border: 1px solid #89b4fa;
}
QInputDialog QLabel {
    color: #cdd6f4;
}
QInputDialog QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px 20px;
    min-width: 64px;
}
QInputDialog QPushButton:hover {
    background-color: #45475a;
    border: 1px solid #89b4fa;
}

/* ── File Dialog ──────────────────────────────────────────────── */
QFileDialog {
    background-color: #1e1e2e;
}

/* ── ToolTip ──────────────────────────────────────────────────── */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
"""
