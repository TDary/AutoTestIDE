# Plan 3: PyQt UI Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PyQt UI layer — main window 4-panel layout, device screen streaming (5 FPS screenshot polling), pick-point flow (click screen → inspect_by_point → hit node → property panel + UI tree highlight + editor insert code).

**Architecture:** MainWindow holds DevicePanel (left, screenshot display + click handler), Editor (center, QPlainTextEdit), RightSidebar (QTabWidget with PropertyPanel, TreePanel, Console). All PocoClient calls go through QThread workers in ui/threads.py. DeviceBridge subscribes to Device.on_status_change and emits Qt signals. core/locator.py generates poco(...) locator strings (pure Python, no Qt).

**Tech Stack:** Python 3.8+ stdlib + PyQt5 + pytest. No QScintilla (Phase 1 fallback to QPlainTextEdit). core/ stays PyQt-free.

**Spec reference:** `docs/specs/2026-06-29-autotest-ide-plan3-ui-layer-design.md` (Plan 3 design); parent spec `docs/specs/2026-06-29-autotest-ide-clone-design.md` §5-§6.

**Project root:** `E:/AutoTestIDE/`. All paths relative to it.

**Deviations from spec:**
1. QPlainTextEdit instead of QScintilla (spec §11 risk register, Phase 1 fallback).
2. PyQt5 first (spec §9.2 allows PyQt5 or PyQt6).
3. ScreenshotWorker separate from PocoWorker (5 FPS polling is independent high-frequency task).

---

## File Structure

```
E:/AutoTestIDE/
├── src/autotest_ide/
│   ├── app.py                        # Task 1: QApplication startup
│   ├── __main__.py                   # Task 1: python -m entry
│   ├── core/
│   │   └── locator.py               # Task 2: locator generation (pure Python)
│   └── ui/
│       ├── __init__.py               # Task 3: package init
│       ├── threads.py                # Task 4: QThread workers
│       ├── main_window.py            # Task 5: main window layout
│       ├── device_panel.py           # Task 6: screenshot display + click
│       ├── editor.py                 # Task 7: code editor
│       ├── tree_panel.py            # Task 8: UI tree view
│       ├── property_panel.py        # Task 9: property table
│       └── console.py               # Task 10: console output
└── tests/
    ├── test_locator.py               # Task 2
    ├── test_threads.py               # Task 4
    └── (Plan 1-2 files unchanged)
```

---

## Task 1: App Entry Point (app.py + __main__.py)

**Files:**
- Create: `src/autotest_ide/app.py`
- Create: `src/autotest_ide/__main__.py`

- [ ] **Step 1: Write `src/autotest_ide/__main__.py`**

```python
from autotest_ide.app import main

main()
```

- [ ] **Step 2: Write `src/autotest_ide/app.py`**

```python
import sys

from PyQt5.QtWidgets import QApplication

from autotest_ide.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AutoTest IDE")
    app.setOrganizationName("AutoTest")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
```

- [ ] **Step 3: Verify the app can import (won't fully run until MainWindow exists)**

Run: `python -c "from autotest_ide.app import main; print('OK')"`
Expected: FAIL (MainWindow doesn't exist yet — will work after Task 5)

---

## Task 2: Locator Generation (core/locator.py) — Pure Python, No Qt

**Files:**
- Create: `src/autotest_ide/core/locator.py`
- Create: `tests/test_locator.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_locator.py`:

```python
import pytest

from autotest_ide.core.locator import generate_locator


def test_name_unique():
    node = {"name": "Button_Play", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node, all_nodes=[node]) == 'poco("Button_Play")'


def test_name_not_unique_uses_type():
    node = {"name": "Btn", "type": "Button", "payload": {"text": ""}}
    other = {"name": "Btn", "type": "Label", "payload": {"text": ""}}
    assert generate_locator(node, all_nodes=[node, other]) == 'poco(name="Btn", type="Button")'


def test_name_empty_uses_text_and_type():
    node = {"name": "", "type": "Button", "payload": {"text": "Play"}}
    assert generate_locator(node) == 'poco(text="Play", type="Button")'


def test_name_and_text_empty_uses_type():
    node = {"name": "", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node) == 'poco(type="Button")'


def test_all_empty_uses_node_id():
    node = {"node_id": "btn_play", "name": "", "type": "", "payload": {"text": ""}}
    assert generate_locator(node) == 'poco(node_id="btn_play")'


def test_name_unique_without_all_nodes():
    node = {"name": "Button_Play", "type": "Button", "payload": {"text": ""}}
    assert generate_locator(node) == 'poco("Button_Play")'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_locator.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/autotest_ide/core/locator.py`**

```python
from typing import Optional


def generate_locator(node: dict, all_nodes: Optional[list] = None) -> str:
    name = node.get("name", "")
    ntype = node.get("type", "")
    text = node.get("payload", {}).get("text", "")
    node_id = node.get("node_id", "")

    if name:
        if all_nodes is None or sum(1 for n in all_nodes if n.get("name") == name) <= 1:
            return f'poco("{name}")'
        return f'poco(name="{name}", type="{ntype}")'

    if text:
        return f'poco(text="{text}", type="{ntype}")'

    if ntype:
        return f'poco(type="{ntype}")'

    return f'poco(node_id="{node_id}")'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_locator.py -v`
Expected: 6 passed

- [ ] **Step 5: Verify core/ still has no PyQt**

Run: `python -c "import importlib, sys; m=importlib.import_module('autotest_ide.core.locator'); assert 'PyQt' not in sys.modules"`

---

## Task 3: UI Package Init

**Files:**
- Create: `src/autotest_ide/ui/__init__.py`

- [ ] **Step 1: Write empty init**

```python
```

(empty file — package marker)

---

## Task 4: QThread Workers (ui/threads.py)

**Files:**
- Create: `src/autotest_ide/ui/threads.py`
- Create: `tests/test_threads.py`

- [ ] **Step 1: Write `src/autotest_ide/ui/threads.py`**

```python
import threading

from PyQt5.QtCore import QThread, QObject, pyqtSignal, QPixmap

from autotest_ide.core.device import Device


class ScreenshotWorker(QThread):
    screenshot_ready = pyqtSignal(QPixmap)

    def __init__(self, device: Device, fps: int = 5, parent=None):
        super().__init__(parent)
        self._device = device
        self._interval = 1.0 / fps
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.wait(timeout=self._interval):
            if self._device.status != "online":
                continue
            try:
                png_bytes = self._device.poco.screenshot()
                pixmap = QPixmap()
                pixmap.loadFromData(png_bytes)
                if not pixmap.isNull():
                    self.screenshot_ready.emit(pixmap)
            except Exception:
                pass

    def stop(self):
        self._stop_event.set()
        self.wait(2000)


class PocoWorker(QThread):
    inspect_result = pyqtSignal(dict, QPixmap)
    inspect_failed = pyqtSignal(str)

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self._device = device
        self._task = None

    def inspect(self, x: int, y: int):
        self._task = ("inspect", x, y)
        self.start()

    def run(self):
        if not self._task:
            return
        kind = self._task[0]
        if kind == "inspect":
            x, y = self._task[1], self._task[2]
            try:
                result = self._device.poco.inspect_by_point(x, y)
                shot = self._device.poco.screenshot()
                pixmap = QPixmap()
                pixmap.loadFromData(shot)
                self.inspect_result.emit(result, pixmap)
            except Exception as e:
                self.inspect_failed.emit(str(e))


class DeviceBridge(QObject):
    status_changed = pyqtSignal(str)

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self._device = device
        device.on_status_change(self._on_status)

    def _on_status(self, status: str):
        self.status_changed.emit(status)
```

- [ ] **Step 2: Write `tests/test_threads.py`** (basic import smoke test — Qt widgets need QApplication)

```python
import pytest

from PyQt5.QtWidgets import QApplication

# Ensure a QApplication exists for Qt imports
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_screenshot_worker_importable(qapp):
    from autotest_ide.ui.threads import ScreenshotWorker
    assert ScreenshotWorker is not None


def test_poco_worker_importable(qapp):
    from autotest_ide.ui.threads import PocoWorker
    assert PocoWorker is not None


def test_device_bridge_importable(qapp):
    from autotest_ide.ui.threads import DeviceBridge
    assert DeviceBridge is not None
```

- [ ] **Step 3: Run test**

Run: `pytest tests/test_threads.py -v`
Expected: 3 passed

---

## Task 5: Main Window Layout (ui/main_window.py)

**Files:**
- Create: `src/autotest_ide/ui/main_window.py`

- [ ] **Step 1: Write `src/autotest_ide/ui/main_window.py`**

```python
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QTabWidget, QLabel, QComboBox,
    QStatusBar, QToolBar, QAction,
)

from autotest_ide.ui.device_panel import DevicePanel
from autotest_ide.ui.editor import Editor
from autotest_ide.ui.tree_panel import TreePanel
from autotest_ide.ui.property_panel import PropertyPanel
from autotest_ide.ui.console import Console


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AutoTest IDE")
        self.resize(1280, 720)

        self._init_menubar()
        self._init_toolbar()
        self._init_central()
        self._init_statusbar()

    def _init_menubar(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("文件")
        file_menu.addAction("新建")
        file_menu.addAction("打开")
        file_menu.addSeparator()
        file_menu.addAction("退出")

        run_menu = menu.addMenu("运行")
        run_menu.addAction("运行脚本")
        run_menu.addAction("停止")

        help_menu = menu.addMenu("帮助")
        help_menu.addAction("关于")

    def _init_toolbar(self):
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        toolbar.addWidget(self.device_combo)

        toolbar.addSeparator()

        self.run_action = QAction("运行", self)
        toolbar.addAction(self.run_action)

        self.stop_action = QAction("停止", self)
        self.stop_action.setEnabled(False)
        toolbar.addAction(self.stop_action)

    def _init_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        self.device_panel = DevicePanel()
        self.editor = Editor()

        right_tabs = QTabWidget()
        self.property_panel = PropertyPanel()
        self.tree_panel = TreePanel()
        self.console = Console()
        right_tabs.addTab(self.property_panel, "属性")
        right_tabs.addTab(self.tree_panel, "UI 树")
        right_tabs.addTab(self.console, "控制台")

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.device_panel)
        splitter.addWidget(self.editor)
        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 3)

        layout.addWidget(splitter)

    def _init_statusbar(self):
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_device = QLabel("设备: 未连接")
        self.status_protocol = QLabel("协议: -")
        self.status_coords = QLabel("坐标: -")
        status.addPermanentWidget(self.status_device)
        status.addPermanentWidget(self.status_protocol)
        status.addPermanentWidget(self.status_coords)
```

---

## Task 6: Device Panel (ui/device_panel.py)

**Files:**
- Create: `src/autotest_ide/ui/device_panel.py`

- [ ] **Step 1: Write `src/autotest_ide/ui/device_panel.py`**

```python
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout


class OverlayWidget(QWidget):
    """Transparent overlay for drawing hit-region rectangles on the screenshot."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rects: list[QRect] = []

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

    def update_screenshot(self, pixmap: QPixmap):
        self._current_pixmap = pixmap
        label_size = self._screenshot_label.size()
        scaled = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._screenshot_label.setPixmap(scaled)
        if not pixmap.isNull() and label_size.width() > 0:
            self._scale_ratio = scaled.width() / pixmap.width()
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
        label_size = self._screenshot_label.size()
        scaled = self._current_pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # The scaled pixmap is centered in the label; compute offset
        offset_x = (label_size.width() - scaled.width()) / 2
        offset_y = (label_size.height() - scaled.height()) / 2
        # Position relative to this widget
        pos = event.pos()
        lx = pos.x() - self._screenshot_label.pos().x() - offset_x
        ly = pos.y() - self._screenshot_label.pos().y() - offset_y
        if lx < 0 or ly < 0 or lx >= scaled.width() or ly >= scaled.height():
            return
        # Reverse scale to get logical pixel coordinates
        x = int(lx / self._scale_ratio)
        y = int(ly / self._scale_ratio)
        self.inspect_requested.emit(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self._screenshot_label.geometry())
```

---

## Task 7: Code Editor (ui/editor.py)

**Files:**
- Create: `src/autotest_ide/ui/editor.py`

- [ ] **Step 1: Write `src/autotest_ide/ui/editor.py`**

```python
import re

from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter, QFont
from PyQt5.QtWidgets import QPlainTextEdit


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#ff79c6"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "import", "from", "class", "def", "if", "elif", "else",
            "for", "while", "return", "try", "except", "finally",
            "with", "as", "and", "or", "not", "in", "is", "True", "False", "None",
        ]
        for kw in keywords:
            self._rules.append((QRegExp(r"\b" + kw + r"\b"), keyword_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#f1fa8c"))
        self._rules.append((QRegExp(r'".*"'), string_format))
        self._rules.append((QRegExp(r"'.*'"), string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6272a4"))
        self._rules.append((QRegExp(r"#[^\n]*"), comment_format))

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
```

---

## Task 8: UI Tree Panel (ui/tree_panel.py)

**Files:**
- Create: `src/autotest_ide/ui/tree_panel.py`

- [ ] **Step 1: Write `src/autotest_ide/ui/tree_panel.py`**

```python
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QTreeView


class TreePanel(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStandardItemModel(self)
        self._model.setHorizontalHeaderLabels(["名称", "类型", "文本"])
        self.setModel(self._model)
        self.setAlternatingRowColors(True)
        self._node_map: dict[str, QStandardItem] = {}

    def load_tree(self, root_node: dict):
        self._model.clear()
        self._model.setHorizontalHeaderLabels(["名称", "类型", "文本"])
        self._node_map.clear()
        self._add_node(root_node, self._model.invisibleRootItem())

    def _add_node(self, node: dict, parent_item):
        name = node.get("name", "")
        ntype = node.get("type", "")
        text = node.get("payload", {}).get("text", "")
        node_id = node.get("node_id", "")

        name_item = QStandardItem(name)
        type_item = QStandardItem(ntype)
        text_item = QStandardItem(text)

        name_item.setData(node_id, Qt.UserRole)
        name_item.setEditable(False)
        type_item.setEditable(False)
        text_item.setEditable(False)

        parent_item.appendRow([name_item, type_item, text_item])

        if node_id:
            self._node_map[node_id] = name_item

        for child in node.get("children", []):
            self._add_node(child, name_item)

    def highlight_node(self, node_id: str):
        if node_id in self._node_map:
            item = self._node_map[node_id]
            self.setCurrentIndex(item.index())
            self.scrollTo(item.index())
            self.expand(item.index())

    def get_selected_node_data(self) -> dict:
        indexes = self.selectedIndexes()
        if not indexes:
            return {}
        item = self._model.itemFromIndex(indexes[0])
        node_id = item.data(Qt.UserRole)
        return {"node_id": node_id, "name": item.text()}
```

---

## Task 9: Property Panel (ui/property_panel.py)

**Files:**
- Create: `src/autotest_ide/ui/property_panel.py`

- [ ] **Step 1: Write `src/autotest_ide/ui/property_panel.py`**

```python
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView


class PropertyPanel(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["属性", "值"])
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.setSelectionBehavior(QTableWidget.SelectItems)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

    def show_properties(self, payload: dict):
        self.setRowCount(0)
        if not payload:
            return
        for key, value in payload.items():
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QTableWidgetItem(str(key)))
            val_item = QTableWidgetItem(str(value))
            val_item.setFlags(val_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 1, val_item)
```

---

## Task 10: Console Panel (ui/console.py)

**Files:**
- Create: `src/autotest_ide/ui/console.py`

- [ ] **Step 1: Write `src/autotest_ide/ui/console.py`**

```python
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
            cursor.insertHtml(f'<span style="color:red">{text}</span><br>')
        else:
            cursor.insertText(text + "\n")
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def clear_output(self):
        self.clear()
```

---

## Task 11: Wire Everything Together + Final Verification

- [ ] **Step 1: Wire MainWindow to DeviceManager, threads, and panels**

Add to `main_window.py` the logic to:
- Set up `DeviceManager` and `DeviceBridge`
- Populate device dropdown from `list_android_devices()` / `list_local_devices()`
- On device combo selection → `connect_android` / `connect_local`
- Start `ScreenshotWorker` when device goes online
- On `inspect_requested` → dispatch `PocoWorker`
- On `inspect_result` → call `generate_locator`, update TreePanel, PropertyPanel, DevicePanel highlight, Editor insert
- On `DeviceBridge.status_changed` → update status bar

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`
Expected: all pass (Plan 1-2 tests + Plan 3 locator + threads tests)

- [ ] **Step 3: Verify core/ has no PyQt dependency**

Run: `python -c "import importlib, sys; [print(f'OK: {m}') for m in ['autotest_ide.core.errors','autotest_ide.core.protocol','autotest_ide.core.poco_client','autotest_ide.core.forwarder','autotest_ide.core.device','autotest_ide.core.device_manager','autotest_ide.core.locator'] if not (importlib.import_module(m) or 'PyQt' in sys.modules)]"`

- [ ] **Step 4: Manual smoke test**

Run: `python -m autotest_ide`
Verify: window appears with 4 panels, device dropdown, toolbar, status bar.

---

## Self-Review

### Spec coverage check

| Spec / design section | Task(s) |
|---|---|
| §6.1 Main window layout | T5 |
| §6.2A Device panel (screenshot + click) | T6 |
| §6.2B Script editor | T7 |
| §6.2C Right sidebar (property, tree, console) | T8, T9, T10 |
| §6.2D Status bar | T5 |
| §6.3 Pick-point flow | T6 + T11 wiring |
| §6.4 Locator strategy | T2 |
| §5.2 Thread model (QThread workers) | T4 |
| Deviation #1 (QPlainTextEdit) | T7 |
| Deviation #3 (ScreenshotWorker separate) | T4 |

**Gaps:** None. Every spec/design section in Plan 3's scope has a task.

---

**文档结束**
