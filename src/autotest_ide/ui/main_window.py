from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QSplitter, QTabWidget, QLabel, QComboBox,
    QStatusBar, QToolBar, QAction,
)

from autotest_ide.ui.device_panel import DevicePanel
from autotest_ide.ui.editor import Editor
from autotest_ide.ui.tree_panel import TreePanel
from autotest_ide.ui.property_panel import PropertyPanel
from autotest_ide.ui.console import Console
from autotest_ide.ui.threads import ScreenshotWorker, PocoWorker, DeviceBridge
from autotest_ide.core.device_manager import DeviceManager
from autotest_ide.core.locator import generate_locator


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AutoTest IDE")
        self.resize(1280, 720)

        self._device_mgr = DeviceManager()
        self._screenshot_worker = None
        self._poco_worker = None
        self._device_bridge = None

        self._init_menubar()
        self._init_toolbar()
        self._init_central()
        self._init_statusbar()
        self._init_connections()

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

        self._refresh_action = QAction("刷新设备", self)
        self._refresh_action.triggered.connect(self._refresh_devices)
        toolbar.addAction(self._refresh_action)

        self._connect_action = QAction("连接", self)
        self._connect_action.triggered.connect(self._connect_selected_device)
        toolbar.addAction(self._connect_action)

        self._disconnect_action = QAction("断开", self)
        self._disconnect_action.triggered.connect(self._disconnect_device)
        toolbar.addAction(self._disconnect_action)

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

    def _init_connections(self):
        self.device_panel.inspect_requested.connect(self._on_inspect_requested)

    def _refresh_devices(self):
        self.device_combo.clear()
        try:
            android = self._device_mgr.list_android_devices()
            for d in android:
                label = f"{d['serial']} ({d.get('model', 'unknown')})"
                self.device_combo.addItem(label, ("android", d["serial"]))
        except Exception:
            pass
        try:
            local = self._device_mgr.list_local_devices()
            for d in local:
                label = f"localhost:{d['port']}"
                self.device_combo.addItem(label, ("local", d["port"]))
        except Exception:
            pass

    def _connect_selected_device(self):
        data = self.device_combo.currentData()
        if not data:
            return
        kind, identifier = data
        if kind == "android":
            device = self._device_mgr.connect_android(serial=identifier)
        else:
            device = self._device_mgr.connect_local(port=identifier)

        self._device_bridge = DeviceBridge(device)
        self._device_bridge.status_changed.connect(self._on_device_status_changed)

        if device.status == "online":
            self._start_screenshot_worker(device)
            self.tree_panel.load_tree(device.poco.get_root())

    def _disconnect_device(self):
        self._stop_screenshot_worker()
        self._device_mgr.disconnect_active()
        self.status_device.setText("设备: 未连接")
        self.status_protocol.setText("协议: -")
        self.device_panel.clear_highlight()
        self.property_panel.show_properties({})
        self.tree_panel.load_tree({"name": "", "type": "", "payload": {}, "children": []})

    def _start_screenshot_worker(self, device):
        self._stop_screenshot_worker()
        self._screenshot_worker = ScreenshotWorker(device, fps=5)
        self._screenshot_worker.screenshot_ready.connect(self.device_panel.update_screenshot)
        self._screenshot_worker.start()

    def _stop_screenshot_worker(self):
        if self._screenshot_worker:
            self._screenshot_worker.stop()
            self._screenshot_worker = None

    def _on_device_status_changed(self, status):
        self.status_device.setText(f"设备: {status}")
        device = self._device_mgr.active
        if device and status == "online":
            if not self._screenshot_worker:
                self._start_screenshot_worker(device)
            if device.poco:
                self.status_protocol.setText(f"协议: {device.poco.protocol_version or '-'}")
        elif status == "offline":
            self._stop_screenshot_worker()
        elif status == "disconnected":
            self._stop_screenshot_worker()

    def _on_inspect_requested(self, x: int, y: int):
        device = self._device_mgr.active
        if not device or device.status != "online":
            return
        self.status_coords.setText(f"坐标: ({x}, {y})")
        if self._poco_worker and self._poco_worker.isRunning():
            return
        self._poco_worker = PocoWorker(device)
        self._poco_worker.inspect_result.connect(self._on_inspect_result)
        self._poco_worker.inspect_failed.connect(self._on_inspect_failed)
        self._poco_worker.inspect(x, y)

    def _on_inspect_result(self, result: dict, screenshot: QPixmap):
        device = self._device_mgr.active
        if not device:
            return
        node_id = result.get("node_id", "")
        self.device_panel.update_screenshot(screenshot)
        try:
            root = device.poco.get_root()
            self.tree_panel.load_tree(root)
        except Exception:
            pass
        if node_id:
            self.tree_panel.highlight_node(node_id)
        node = self._find_node_in_tree(device, node_id) if device and node_id else None
        if node:
            bounds = node.get("payload", {}).get("visibleBounds", {})
            self.device_panel.highlight_region(bounds)
            self.property_panel.show_properties(node.get("payload", {}))
            locator = generate_locator(node, all_nodes=self._flatten_tree(root))
            self.editor.insert_locator_code(f"{locator}.click()")
        else:
            self.device_panel.clear_highlight()
            self.property_panel.show_properties({})

    def _on_inspect_failed(self, error: str):
        self.console.append_text(f"检选点失败: {error}", is_error=True)

    def _find_node_in_tree(self, device, node_id: str) -> dict:
        try:
            attrs = device.poco.get_attributes(node_id)
            return {"node_id": node_id, "payload": attrs}
        except Exception:
            return None

    def _flatten_tree(self, root: dict) -> list:
        nodes = [root]
        for child in root.get("children", []):
            nodes.extend(self._flatten_tree(child))
        return nodes

    def closeEvent(self, event):
        self._stop_screenshot_worker()
        self._device_mgr.shutdown()
        super().closeEvent(event)
