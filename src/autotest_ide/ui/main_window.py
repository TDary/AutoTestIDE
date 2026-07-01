from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QSplitter, QTabWidget, QLabel, QComboBox,
    QStatusBar, QToolBar, QAction,
    QFileDialog, QMessageBox,
)

from autotest_ide.core.log import getLogger
from autotest_ide.ui.device_panel import DevicePanel
from autotest_ide.ui.editor import Editor
from autotest_ide.ui.tree_panel import TreePanel
from autotest_ide.ui.property_panel import PropertyPanel
from autotest_ide.ui.console import Console
from autotest_ide.ui.threads import ScreenshotWorker, PocoWorker, DeviceBridge
from autotest_ide.ui.run_controller import RunController
from autotest_ide.ui.report_view import ReportView
from autotest_ide.core.device_manager import DeviceManager
from autotest_ide.core.locator import generate_locator
from autotest_ide.report import render_report

logger = getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AutoTest IDE")
        self.resize(1280, 720)

        self._device_mgr = DeviceManager()
        self._screenshot_worker = None
        self._poco_worker = None
        self._device_bridge = None
        self._run_controller = RunController(self)
        self._report_view = None
        self._current_file = None
        self._cached_root = None
        self._cached_flat = []

        self._init_menubar()
        self._init_toolbar()
        self._init_central()
        self._init_statusbar()
        self._init_connections()

    def _init_menubar(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("文件")
        new_action = QAction("新建", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new)
        file_menu.addAction(new_action)

        open_action = QAction("打开...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open)
        file_menu.addAction(open_action)

        save_action = QAction("保存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        run_menu = menu.addMenu("运行")
        run_script_action = QAction("运行脚本", self)
        run_script_action.setShortcut("F5")
        run_script_action.triggered.connect(self._on_run_clicked)
        run_menu.addAction(run_script_action)

        stop_action = QAction("停止", self)
        stop_action.setShortcut("Shift+F5")
        stop_action.triggered.connect(self._on_stop_clicked)
        run_menu.addAction(stop_action)

        help_menu = menu.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _init_toolbar(self):
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        toolbar.addWidget(self.device_combo)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("SDK:"))

        self.sdk_combo = QComboBox()
        self.sdk_combo.addItem("Poco (标准)", "poco")
        self.sdk_combo.addItem("JX4 (AltrunUnityDriver)", "jx4")
        self.sdk_combo.setMinimumWidth(200)
        toolbar.addWidget(self.sdk_combo)

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
        self._run_controller.output_received.connect(
            lambda text, is_err: self.console.append_text(text, is_err)
        )
        self._run_controller.run_started.connect(self._on_run_started)
        self._run_controller.run_finished.connect(self._on_run_finished)
        self._run_controller.run_stopped.connect(self._on_run_stopped)
        self.run_action.triggered.connect(self._on_run_clicked)
        self.stop_action.triggered.connect(self._on_stop_clicked)

    def _refresh_devices(self):
        self.device_combo.clear()
        adb_ok = False
        try:
            android = self._device_mgr.list_android_devices()
            adb_ok = True
            for d in android:
                state = d.get("state", "device")
                label = f"{d['serial']} ({d.get('model', 'unknown')})"
                if state != "device":
                    label += f" [{state}"
                    if state == "unauthorized":
                        label += " - 请在手机上允许USB调试"
                    label += "]"
                self.device_combo.addItem(label, ("android", d["serial"], state))
        except Exception as e:
            logger.warning("Failed to refresh android devices", exc_info=True)
            self.device_combo.addItem("安卓设备: ADB连接失败，请检查USB和adb", None)
        try:
            local = self._device_mgr.list_local_devices()
            for d in local:
                label = f"localhost:{d['port']}"
                self.device_combo.addItem(label, ("local", d["port"], "device"))
        except Exception as e:
            logger.warning("Failed to refresh local devices", exc_info=True)
            self.console.append_text(f"刷新本地设备失败: {e}", is_error=True)

    def _connect_selected_device(self):
        data = self.device_combo.currentData()
        if not data:
            return
        kind, identifier, state = data
        if state != "device":
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "无法连接", f"设备状态为 {state}，请先在手机上允许USB调试授权。")
            return
        self._disconnect_device()
        sdk_name = self.sdk_combo.currentData() or "poco"
        protocol = self._load_protocol(sdk_name)
        logger.info("Connecting device kind=%s identifier=%s sdk=%s", kind, identifier, sdk_name)
        if kind == "android":
            device = self._device_mgr.connect_android(serial=identifier, protocol=protocol)
        else:
            device = self._device_mgr.connect_local(port=identifier, protocol=protocol)

        self._device_bridge = DeviceBridge(device)
        self._device_bridge.status_changed.connect(self._on_device_status_changed)

        if device.status == "online":
            self._start_screenshot_worker(device)
            self._cached_root = device.poco.get_root()
            self._cached_flat = device.poco._flatten_tree(self._cached_root)
            self.tree_panel.load_tree(self._cached_root)

    def _disconnect_device(self):
        logger.info("Disconnecting device")
        self._stop_screenshot_worker()
        self._device_mgr.disconnect_active()
        self._cached_root = None
        self._cached_flat = []
        self.status_device.setText("设备: 未连接")
        self.status_protocol.setText("协议: -")
        self.device_panel.clear_highlight()
        self.property_panel.show_properties({})
        self.tree_panel.load_tree({"name": "", "type": "", "payload": {}, "children": []})

    @staticmethod
    def _load_protocol(sdk_name: str):
        from autotest_ide.runner.runtest import PROTOCOL_REGISTRY
        import importlib
        if sdk_name in PROTOCOL_REGISTRY:
            spec = PROTOCOL_REGISTRY[sdk_name]
            module_path, class_name = spec.rsplit(":", 1)
            mod = importlib.import_module(module_path)
            return getattr(mod, class_name)()
        # fallback: try sdks package
        try:
            mod = importlib.import_module(f"autotest_ide.sdks.{sdk_name}")
            cls = getattr(mod, f"{sdk_name.upper()}Protocol", None)
            if cls:
                return cls()
        except (ImportError, AttributeError):
            pass
        from autotest_ide.core.protocol_poco import PocoTextProtocol
        return PocoTextProtocol()

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
                sdk = self.sdk_combo.currentData() or "poco"
                self.status_protocol.setText(f"协议: {device.poco.protocol_version or '-'} ({sdk})")
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
        logger.debug("Inspect requested at (%d, %d)", x, y)
        self._poco_worker = PocoWorker(device)
        self._poco_worker.inspect_result.connect(self._on_inspect_result)
        self._poco_worker.inspect_failed.connect(self._on_inspect_failed)
        self._poco_worker.inspect(x, y)

    def _on_inspect_result(self, result: dict, screenshot_bytes: bytes):
        device = self._device_mgr.active
        if not device:
            return
        node_id = result.get("node_id", "")
        self.device_panel.update_screenshot(screenshot_bytes)
        root = self._cached_root
        flat = self._cached_flat
        if node_id:
            self.tree_panel.highlight_node(node_id)
        node = self._find_node_in_tree(device, node_id) if device and node_id else None
        if node:
            bounds = node.get("payload", {}).get("visibleBounds", {})
            self.device_panel.highlight_region(bounds)
            self.property_panel.show_properties(node.get("payload", {}))
            locator = generate_locator(node, all_nodes=flat)
            self.editor.insert_locator_code(f"{locator}.click()")
        else:
            self.device_panel.clear_highlight()
            self.property_panel.show_properties({})

    def _on_inspect_failed(self, error: str):
        logger.warning("Inspect failed: %s", error)
        self.console.append_text(f"检选点失败: {error}", is_error=True)

    def _find_node_in_tree(self, device, node_id: str) -> dict:
        try:
            attrs = device.poco.get_attributes(node_id)
            return {"node_id": node_id, "payload": attrs}
        except Exception:
            logger.debug("Failed to find node %s in tree", node_id, exc_info=True)
            return None

    def _check_unsaved(self) -> bool:
        if self.editor.document().isModified():
            ret = QMessageBox.question(
                self, "未保存", "当前内容未保存，是否保存？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if ret == QMessageBox.Save:
                self._on_save()
                if self.editor.document().isModified():
                    return False
            elif ret == QMessageBox.Cancel:
                return False
        return True

    def _on_new(self):
        if not self._check_unsaved():
            return
        self.editor.clear()
        self.editor.setPlaceholderText("# 在此编写自动化脚本\npoco('Button_Play').click()")
        self._current_file = None
        self.editor.document().setModified(False)

    def _on_open(self):
        if not self._check_unsaved():
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开脚本", "", "Python 文件 (*.py);;所有文件 (*)")
        if path:
            try:
                content = Path(path).read_text(encoding="utf-8")
                self.editor.setPlainText(content)
                self._current_file = path
                self.editor.document().setModified(False)
                logger.info("Opened file: %s", path)
            except Exception as e:
                QMessageBox.warning(self, "打开失败", str(e))

    def _on_save(self):
        path = getattr(self, "_current_file", None)
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "保存脚本", "", "Python 文件 (*.py);;所有文件 (*)")
        if path:
            try:
                Path(path).write_text(self.editor.toPlainText(), encoding="utf-8")
                self._current_file = path
                self.editor.document().setModified(False)
                logger.info("Saved file: %s", path)
            except Exception as e:
                QMessageBox.warning(self, "保存失败", str(e))

    def _on_about(self):
        QMessageBox.about(self, "关于 AutoTest IDE",
                          "AutoTest IDE v1.0\n\n"
                          "基于 Poco 协议的 UI 自动化测试 IDE\n"
                          "使用 PyQt5 构建")

    def _on_run_clicked(self):
        device = self._device_mgr.active
        if not device or device.status != "online":
            self.console.append_text("错误: 没有在线设备", is_error=True)
            return
        ret = QMessageBox.warning(
            self, "运行脚本",
            "脚本将以当前用户权限执行，请仅运行可信来源的 .air 脚本。\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        air_dir = "test.air"
        sdk = self.sdk_combo.currentData() or "poco"
        logger.info("Running script air_dir=%s device=%s:%s poco_port=%d sdk=%s",
                     air_dir, device.device_type, device.name, device.poco.port, sdk)
        self._run_controller.start(
            air_dir, device.device_type, device.name,
            device.poco.port, sdk=sdk,
        )

    def _on_stop_clicked(self):
        logger.info("Stopping script")
        self._run_controller.stop()

    def _on_run_started(self):
        self.run_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.device_panel.setEnabled(False)

    def _on_run_finished(self, exit_code: int, report_path: str):
        self.run_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.device_panel.setEnabled(True)
        logger.info("Script finished exit_code=%d report_path=%s", exit_code, report_path)
        self.console.append_text(f"脚本结束 (exit code: {exit_code})")
        if report_path and Path(report_path).exists():
            html_path = str(Path(report_path).parent / "report.html")
            try:
                render_report(Path(report_path), Path(html_path))
                if self._report_view is None:
                    self._report_view = ReportView()
                self._report_view.show_report(html_path)
                self._report_view.show()
            except Exception as e:
                logger.warning("Report rendering failed: %s", e, exc_info=True)
                self.console.append_text(f"报告渲染失败: {e}", is_error=True)

    def _on_run_stopped(self):
        self.run_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.device_panel.setEnabled(True)

    def closeEvent(self, event):
        if not self._check_unsaved():
            event.ignore()
            return
        self._stop_screenshot_worker()
        self._device_mgr.shutdown()
        super().closeEvent(event)
