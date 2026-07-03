import os
from pathlib import Path

from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QSplitter, QTabWidget, QLabel, QComboBox, QPushButton,
    QStatusBar, QToolBar, QAction,
    QFileDialog, QMessageBox, QLineEdit, QDialog, QDialogButtonBox, QFormLayout,
    QInputDialog, QVBoxLayout, QMenu,
)

from autotest_ide.core.log import getLogger
from autotest_ide.core.locator import generate_locator_code
from autotest_ide.ui.device_panel import DevicePanel
from autotest_ide.ui.editor import Editor
from autotest_ide.ui.icons import make_icon
from autotest_ide.ui.title_bar import CustomTitleBar
from autotest_ide.ui.tree_panel import TreePanel
from autotest_ide.ui.property_panel import PropertyPanel
from autotest_ide.ui.console import Console
from autotest_ide.ui.clickable_panel import ClickablePanel
from autotest_ide.ui.threads import ScreenshotWorker, PocoWorker, DeviceBridge, DeviceScanWorker
from autotest_ide.ui.run_controller import RunController
from autotest_ide.ui.record_controller import RecordController
from autotest_ide.ui.report_view import ReportView
from autotest_ide.core.device_manager import DeviceManager
from autotest_ide.report import render_report

logger = getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AutoTest IDE")
        self.resize(1280, 720)
        self.setMinimumSize(960, 540)

        # Frameless window — we draw our own title bar
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        # Allow native resizing on Windows via hit-test
        self.setMouseTracking(True)

        self._device_mgr = DeviceManager()
        self._screenshot_worker = None
        self._poco_worker = None
        self._device_bridge = None
        self._run_controller = RunController(self)
        self._record_controller = RecordController(self)
        self._report_view = None
        self._current_air = None
        self._current_script = None
        self._cached_root = None
        self._cached_flat = []
        self._last_inspect_xy = (0, 0)

        self._init_titlebar()
        self._build_menu()
        self._init_toolbar()
        self._init_central()
        self._init_statusbar()
        self._init_connections()

    def _init_titlebar(self):
        self._title_bar = CustomTitleBar(self)
        self._title_bar.menu_requested.connect(self._show_popup_menu)
        # Use a container widget as the central widget so we can stack
        # title bar above the toolbar + content.
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._title_bar)

    def _build_menu(self):
        # Build QMenus without showing the native menuBar.
        self._menu_file = QMenu("文件", self)
        new_action = QAction("新建", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new)
        self._menu_file.addAction(new_action)

        open_action = QAction("打开...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open)
        self._menu_file.addAction(open_action)

        save_action = QAction("保存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save)
        self._menu_file.addAction(save_action)

        self._menu_file.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        self._menu_file.addAction(exit_action)

        self._menu_run = QMenu("运行", self)
        run_script_action = QAction("运行脚本", self)
        run_script_action.setShortcut("F5")
        run_script_action.triggered.connect(self._on_run_clicked)
        self._menu_run.addAction(run_script_action)

        stop_action = QAction("停止", self)
        stop_action.setShortcut("Shift+F5")
        stop_action.triggered.connect(self._on_stop_clicked)
        self._menu_run.addAction(stop_action)

        self._menu_run.addSeparator()

        record_menu_action = QAction("录制", self)
        record_menu_action.setShortcut("Ctrl+R")
        record_menu_action.triggered.connect(self._on_record_clicked)
        self._menu_run.addAction(record_menu_action)

        stop_record_menu_action = QAction("停止录制", self)
        stop_record_menu_action.setShortcut("Ctrl+Shift+R")
        stop_record_menu_action.triggered.connect(self._on_stop_record_clicked)
        self._menu_run.addAction(stop_record_menu_action)

        self._menu_help = QMenu("帮助", self)
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        self._menu_help.addAction(about_action)

        # Don't show native menu bar — it would push the title bar down.
        self.menuBar().setVisible(False)

    def _show_popup_menu(self):
        # Pop up a top-level menu below the hamburger button.
        btn = self._title_bar._btn_menu
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
        # Build a combined popup so the user sees all three menus.
        popup = QMenu(self)
        popup.addMenu(self._menu_file)
        popup.addMenu(self._menu_run)
        popup.addMenu(self._menu_help)
        popup.exec_(pos)

    def _init_toolbar(self):
        # Device/connection bar — a plain widget, not a QToolBar, so it
        # sits flush below the title bar without native toolbar chrome.
        device_bar = QWidget()
        device_bar.setObjectName("device_bar")
        device_bar.setFixedHeight(44)
        layout = QHBoxLayout(device_bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        section_dev = QLabel("设备")
        section_dev.setObjectName("toolbar_section")
        layout.addWidget(section_dev)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(220)
        layout.addWidget(self.device_combo)

        layout.addWidget(QLabel("SDK"))
        self.sdk_combo = QComboBox()
        self.sdk_combo.setMinimumWidth(200)
        # Populate from the central registry so new SDKs show up automatically.
        from autotest_ide.sdks import PROTOCOL_REGISTRY
        for name in PROTOCOL_REGISTRY:
            self.sdk_combo.addItem(name, name)
        layout.addWidget(self.sdk_combo)

        self._refresh_btn = self._make_btn("refresh", "刷新", "#89b4fa", "btn_refresh")
        self._refresh_btn.clicked.connect(self._refresh_devices)
        self._refresh_btn.setEnabled(True)
        layout.addWidget(self._refresh_btn)

        layout.addSpacing(12)

        section_conn = QLabel("连接")
        section_conn.setObjectName("toolbar_section")
        layout.addWidget(section_conn)

        self._connect_btn = self._make_btn("connect", "连接", "#a6e3a1", "btn_connect")
        self._connect_btn.clicked.connect(self._connect_selected_device)
        layout.addWidget(self._connect_btn)

        self._disconnect_btn = self._make_btn("disconnect", "断开", "#f38ba8", "btn_disconnect")
        self._disconnect_btn.clicked.connect(self._disconnect_device)
        layout.addWidget(self._disconnect_btn)

        self._conn_status = QLabel(" ● 未连接 ")
        self._conn_status.setObjectName("conn_status_disconnected")
        self._conn_status.setFixedHeight(24)
        layout.addWidget(self._conn_status)

        layout.addStretch()

        # Add device bar to the central outer layout (below title bar)
        self.centralWidget().layout().addWidget(device_bar)

        # Compact QToolBar for script run/stop only (right-aligned would
        # require a stretch; we keep it simple as its own row).
        toolbar = QToolBar("脚本")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setObjectName("run_toolbar")
        # We add the toolbar AFTER the device bar by inserting it into
        # the central layout instead of using QMainWindow's toolbar area.
        # That keeps ordering: title bar → device bar → run bar → content.

        run_bar = QWidget()
        run_bar.setObjectName("run_bar")
        run_bar.setFixedHeight(40)
        run_layout = QHBoxLayout(run_bar)
        run_layout.setContentsMargins(8, 0, 8, 4)
        run_layout.setSpacing(8)

        section_run = QLabel("脚本")
        section_run.setObjectName("toolbar_section")
        run_layout.addWidget(section_run)

        # Use QToolButton widgets so the existing QSS for #btn_run / #btn_stop applies.
        from PyQt5.QtWidgets import QToolButton
        self.run_btn = QToolButton()
        self.run_btn.setIcon(make_icon("run", "#a6e3a1"))
        self.run_btn.setText(" 运行")
        self.run_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.run_btn.setObjectName("btn_run")
        self.run_btn.clicked.connect(self._on_run_clicked)
        run_layout.addWidget(self.run_btn)

        self.stop_btn = QToolButton()
        self.stop_btn.setIcon(make_icon("stop", "#f38ba8"))
        self.stop_btn.setText(" 停止")
        self.stop_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.stop_btn.setObjectName("btn_stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        run_layout.addWidget(self.stop_btn)

        self.record_btn = QToolButton()
        self.record_btn.setIcon(make_icon("record", "#f9e2af"))
        self.record_btn.setText(" 录制")
        self.record_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.record_btn.setObjectName("btn_record")
        self.record_btn.clicked.connect(self._on_record_clicked)
        run_layout.addWidget(self.record_btn)

        self.stop_record_btn = QToolButton()
        self.stop_record_btn.setIcon(make_icon("stop_record", "#6c7086"))
        self.stop_record_btn.setText(" 停录")
        self.stop_record_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.stop_record_btn.setObjectName("btn_stop_record")
        self.stop_record_btn.setEnabled(False)
        self.stop_record_btn.clicked.connect(self._on_stop_record_clicked)
        run_layout.addWidget(self.stop_record_btn)

        run_layout.addStretch()

        self.centralWidget().layout().addWidget(run_bar)

        # Keep QAction references for menu / shortcut bindings
        self.run_action = QAction("运行脚本", self)
        self.run_action.setShortcut("F5")
        self.run_action.triggered.connect(self._on_run_clicked)
        self.addAction(self.run_action)

        self.stop_action = QAction("停止", self)
        self.stop_action.setShortcut("Shift+F5")
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(self._on_stop_clicked)
        self.addAction(self.stop_action)

        self.record_action = QAction("录制", self)
        self.record_action.setShortcut("Ctrl+R")
        self.record_action.triggered.connect(self._on_record_clicked)
        self.addAction(self.record_action)

        self.stop_record_action = QAction("停止录制", self)
        self.stop_record_action.setShortcut("Ctrl+Shift+R")
        self.stop_record_action.setEnabled(False)
        self.stop_record_action.triggered.connect(self._on_stop_record_clicked)
        self.addAction(self.stop_record_action)

    @staticmethod
    def _make_btn(icon_name: str, text: str, color: str, obj_name: str):
        from PyQt5.QtWidgets import QToolButton
        btn = QToolButton()
        btn.setIcon(make_icon(icon_name, color))
        btn.setText(" " + text)
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setObjectName(obj_name)
        return btn

    def _init_central(self):
        # Reuse the central widget's outer layout from _init_titlebar
        outer = self.centralWidget().layout()

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(0)

        self.device_panel = DevicePanel()
        self.editor = Editor()

        right_tabs = QTabWidget()
        self.property_panel = PropertyPanel()
        self.tree_panel = TreePanel()
        self.console = Console()
        right_tabs.addTab(self.property_panel, "属性")
        right_tabs.addTab(self.tree_panel, "UI 树")
        right_tabs.addTab(self.console, "控制台")
        self.clickable_panel = ClickablePanel()
        right_tabs.addTab(self.clickable_panel, "可点击")

        # Refresh button for UI tree (top-right of tab)
        self._tree_refresh_btn = QPushButton("刷新")
        self._tree_refresh_btn.setObjectName("btn_tree_refresh")
        self._tree_refresh_btn.setFixedHeight(24)
        self._tree_refresh_btn.clicked.connect(self._on_refresh_tree)
        right_tabs.setCornerWidget(self._tree_refresh_btn, Qt.TopRightCorner)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.device_panel)
        splitter.addWidget(self.editor)
        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([256, 640, 384])

        content_layout.addWidget(splitter)
        outer.addWidget(content, 1)

    def _init_statusbar(self):
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_device = QLabel("  设备: 未连接  ")
        self.status_protocol = QLabel("  协议: -  ")
        self.status_coords = QLabel("  坐标: -  ")
        status.addPermanentWidget(self.status_device)
        status.addPermanentWidget(self.status_protocol)
        status.addPermanentWidget(self.status_coords)

    def _init_connections(self):
        self.device_panel.inspect_requested.connect(self._on_inspect_requested)
        self.tree_panel.selectionModel().selectionChanged.connect(self._on_tree_selection_changed)
        self.tree_panel.insert_code_requested.connect(self._on_insert_code_from_tree)
        self.clickable_panel.node_selected.connect(self._on_clickable_node_selected)
        self.clickable_panel.insert_code_requested.connect(self._on_insert_code_from_tree)
        self._run_controller.output_received.connect(self.console.append_text)
        self._run_controller.step_screenshot.connect(self.device_panel.update_screenshot)
        self._run_controller.run_started.connect(self._on_run_started)
        self._run_controller.run_finished.connect(self._on_run_finished)
        self._run_controller.run_stopped.connect(self._on_run_stopped)
        self._record_controller.code_generated.connect(self.editor.insert_locator_code)

    def _refresh_devices(self):
        self._refresh_btn.setEnabled(False)
        self.device_combo.clear()
        self.device_combo.addItem("扫描设备中...", None)
        self._scan_worker = DeviceScanWorker(self._device_mgr, self)
        self._scan_worker.devices_found.connect(self._on_devices_found)
        self._scan_worker.start()

    def _on_devices_found(self, android: list, local: list):
        self.device_combo.clear()
        for d in android:
            state = d.get("state", "device")
            label = f"{d['serial']} ({d.get('model', 'unknown')})"
            if state != "device":
                label += f" [{state}"
                if state == "unauthorized":
                    label += " - 请在手机上允许USB调试"
                label += "]"
            self.device_combo.addItem(label, ("android", d["serial"], state))
        for d in local:
            label = f"localhost:{d['port']}"
            self.device_combo.addItem(label, ("local", d["port"], "device"))
        self.device_combo.insertSeparator(self.device_combo.count())
        self.device_combo.addItem("IP直连 (如 192.168.1.100:13000)", ("ip", None, "device"))
        self._refresh_btn.setEnabled(True)

    def _connect_selected_device(self):
        data = self.device_combo.currentData()
        if not data:
            return
        kind, identifier, state = data
        if kind == "ip":
            self._connect_ip_device()
            return
        if state != "device":
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "无法连接", f"设备状态为 {state}，请先在手机上允许USB调试授权。")
            return
        self._disconnect_device()
        sdk_name = self.sdk_combo.currentData() or "jx4"
        protocol = self._load_protocol(sdk_name)
        logger.info("Connecting device kind=%s identifier=%s sdk=%s", kind, identifier, sdk_name)
        try:
            if kind == "android":
                device = self._device_mgr.connect_android(serial=identifier, protocol=protocol)
            else:
                device = self._device_mgr.connect_local(port=identifier, protocol=protocol)
        except Exception as e:
            QMessageBox.warning(self, "连接失败", f"无法连接设备\n{e}")
            return

        if device.status != "online":
            err = device.last_error or "未知错误"
            QMessageBox.warning(
                self, "连接失败",
                f"设备状态: {device.status}\n\n错误: {err}",
            )
            self._disconnect_device()
            return

        self._device_bridge = DeviceBridge(device)
        self._device_bridge.status_changed.connect(self._on_device_status_changed)

        self._poco_worker = PocoWorker(device, self)
        self._poco_worker.inspect_result.connect(self._on_inspect_result)
        self._poco_worker.inspect_failed.connect(self._on_inspect_failed)

        self._start_screenshot_worker(device)
        self._cached_root = device.poco.get_root()
        self._cached_flat = device.poco._flatten_tree(self._cached_root)
        self.tree_panel.load_tree(self._cached_root)
        self.clickable_panel.set_device(device)
        self.clickable_panel.load_clickable_nodes(self._cached_flat)
        self.status_device.setText(f"  设备: {device.name}  ")
        sdk = self.sdk_combo.currentData() or "jx4"
        self.status_protocol.setText(f"  协议: {device.poco.protocol_version or '-'} ({sdk})  ")
        self._conn_status.setText(" ● 已连接 ")
        self._conn_status.setStyleSheet(
            "color: #a6e3a1; font-size: 13px; font-weight: bold; padding: 2px 8px;"
        )

    def _disconnect_device(self):
        logger.info("Disconnecting device")
        self._stop_screenshot_worker()
        if self._poco_worker:
            self._poco_worker.quit()
            self._poco_worker.wait(2000)
            self._poco_worker = None
        self._device_mgr.disconnect_active()
        self._cached_root = None
        self._cached_flat = []
        self.status_device.setText("  设备: 未连接  ")
        self.status_protocol.setText("  协议: -  ")
        self._conn_status.setText(" ● 未连接 ")
        self._conn_status.setStyleSheet(
            "color: #f38ba8; font-size: 13px; font-weight: bold; padding: 2px 8px;"
        )
        self.device_panel.clear_highlight()
        self.property_panel.show_properties({})
        self.tree_panel.load_tree({"name": "", "type": "", "payload": {}, "children": []})
        self.clickable_panel.set_device(None)
        self.clickable_panel.clear()

    def _connect_ip_device(self):
        text, ok = QInputDialog.getText(
            self, "IP 直连", "请输入设备 IP:端口\n(如 192.168.1.100:13000)",
            text="192.168.1.100:13000",
        )
        if not ok or not text.strip():
            return
        text = text.strip()
        try:
            host, port_str = text.rsplit(":", 1)
            port = int(port_str)
        except ValueError:
            QMessageBox.warning(self, "格式错误", "请输入 IP:端口 格式，如 192.168.1.100:13000")
            return

        # Quick TCP probe so we can give the user an immediate, specific error
        # before going through the full Poco handshake.
        tcp_err = self._probe_tcp(host, port)
        if tcp_err:
            QMessageBox.warning(
                self, "网络不通",
                f"无法建立 TCP 连接到 {host}:{port}\n\n{tcp_err}\n\n"
                "请检查:\n"
                "1. 设备和电脑是否在同一局域网\n"
                "2. 设备上 Poco service 是否已启动 (端口 13000)\n"
                "3. 防火墙是否放行该端口",
            )
            return

        self._disconnect_device()
        sdk_name = self.sdk_combo.currentData() or "jx4"
        protocol = self._load_protocol(sdk_name)
        logger.info("Connecting IP device host=%s port=%d sdk=%s", host, port, sdk_name)
        try:
            device = self._device_mgr.connect_ip(host=host, port=port, protocol=protocol)
        except Exception as e:
            logger.warning("IP connection failed: %s", e, exc_info=True)
            QMessageBox.warning(self, "连接失败", f"无法连接 {host}:{port}\n{e}")
            return

        if device.status != "online":
            err = device.last_error or "未知错误"
            hint = self._diagnose_handshake_failure(err, sdk_name)
            QMessageBox.warning(
                self, "Poco 握手失败",
                f"TCP 已连通 {host}:{port}，但 Poco 协议握手失败。\n\n"
                f"错误: {err}\n\n"
                f"{hint}",
            )
            self._disconnect_device()
            return

        self._device_bridge = DeviceBridge(device)
        self._device_bridge.status_changed.connect(self._on_device_status_changed)

        self._poco_worker = PocoWorker(device, self)
        self._poco_worker.inspect_result.connect(self._on_inspect_result)
        self._poco_worker.inspect_failed.connect(self._on_inspect_failed)

        self._start_screenshot_worker(device)
        self._cached_root = device.poco.get_root()
        self._cached_flat = device.poco._flatten_tree(self._cached_root)
        self.tree_panel.load_tree(self._cached_root)
        self.clickable_panel.set_device(device)
        self.clickable_panel.load_clickable_nodes(self._cached_flat)
        self.status_device.setText(f"  设备: {device.name}  ")
        sdk = self.sdk_combo.currentData() or "jx4"
        self.status_protocol.setText(f"  协议: {device.poco.protocol_version or '-'} ({sdk})  ")
        self._conn_status.setText(" ● 已连接 ")
        self._conn_status.setStyleSheet(
            "color: #a6e3a1; font-size: 13px; font-weight: bold; padding: 2px 8px;"
        )

    @staticmethod
    def _probe_tcp(host: str, port: int, timeout: float = 2.0) -> str:
        """Quick TCP connect test. Returns empty string on success, error msg on failure."""
        import socket as _socket
        try:
            s = _socket.create_connection((host, port), timeout=timeout)
            s.close()
            return ""
        except _socket.timeout:
            return f"连接超时 ({timeout}s) — 目标无响应"
        except ConnectionRefusedError:
            return "连接被拒绝 — 目标端口未监听"
        except OSError as e:
            return f"网络错误: {e}"

    @staticmethod
    def _diagnose_handshake_failure(err: str, sdk_name: str) -> str:
        """Suggest likely causes based on the handshake error message."""
        err_lower = err.lower()
        if "handshake failed" in err_lower or "did not respond" in err_lower:
            return (
                "提示: TCP 通但握手超时，常见原因:\n"
                f"  - 当前 SDK 选的是「{sdk_name}」，但设备运行的可能是另一种\n"
                "    尝试切换 SDK (Poco ↔ JX4) 后重连\n"
                "  - 设备上 Poco service 端口不是 13000\n"
                "  - service 已启动但未完成初始化"
            )
        if "connect failed" in err_lower:
            return "提示: TCP 层连接失败，请检查网络/防火墙"
        return ""

    @staticmethod
    def _load_protocol(sdk_name: str):
        from autotest_ide.sdks import PROTOCOL_REGISTRY
        import importlib
        if sdk_name in PROTOCOL_REGISTRY:
            spec = PROTOCOL_REGISTRY[sdk_name]
            module_path, class_name = spec.rsplit(":", 1)
            mod = importlib.import_module(module_path)
            return getattr(mod, class_name)()
        # fallback: try sdks package by name
        try:
            mod = importlib.import_module(f"autotest_ide.sdks.{sdk_name}.protocol")
            cls = getattr(mod, f"{sdk_name.upper()}Protocol", None)
            if cls:
                return cls()
        except (ImportError, AttributeError):
            pass
        # final fallback: jx4
        from autotest_ide.sdks.jx4.protocol import JX4Protocol
        return JX4Protocol()

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
        self.status_device.setText(f"  设备: {status}  ")
        device = self._device_mgr.active
        if device and status == "online":
            if not self._screenshot_worker:
                self._start_screenshot_worker(device)
            if device.poco:
                sdk = self.sdk_combo.currentData() or "jx4"
                self.status_protocol.setText(f"  协议: {device.poco.protocol_version or '-'} ({sdk})  ")
            self._conn_status.setText(" ● 已连接 ")
            self._conn_status.setStyleSheet(
                "color: #a6e3a1; font-size: 13px; font-weight: bold; padding: 2px 8px;"
            )
        elif status in ("offline", "disconnected"):
            self._stop_screenshot_worker()
            if self._poco_worker:
                self._poco_worker.quit()
                self._poco_worker.wait(2000)
                self._poco_worker = None
            self._conn_status.setText(" ● 未连接 ")
            self._conn_status.setStyleSheet(
                "color: #f38ba8; font-size: 13px; font-weight: bold; padding: 2px 8px;"
            )

    def _on_inspect_requested(self, x: int, y: int):
        device = self._device_mgr.active
        if not device or device.status != "online":
            return
        self.status_coords.setText(f"  坐标: ({x}, {y})  ")
        self._last_inspect_xy = (x, y)
        if self._poco_worker and not self._poco_worker.isRunning():
            self._poco_worker.inspect(x, y)
        else:
            self._on_inspect_failed("inspect worker busy or unavailable", x, y)

    def _on_inspect_result(self, node: dict, screenshot: bytes):
        self.device_panel.update_screenshot(screenshot)
        bounds = node.get("payload", {}).get("pos", {})
        if bounds:
            self.device_panel.highlight_region(bounds)
        node_id = node.get("node_id", "")
        if node_id:
            self.tree_panel.highlight_node(node_id)
        self.property_panel.show_properties(node.get("payload", {}))
        x, y = getattr(self, "_last_inspect_xy", (0, 0))
        if self._record_controller.is_recording:
            self._record_controller.on_inspect_result(node, x, y)
        else:
            code = generate_locator_code(node, self._cached_flat)
            if code:
                self.editor.insert_locator_code(code)

    def _on_inspect_failed(self, error: str, x: int, y: int):
        self.console.append_warn(f"检查节点失败: {error}")
        if self._record_controller.is_recording:
            self._record_controller.on_inspect_failed(x, y)
        else:
            self.editor.insert_locator_code(f"auto.click({x}, {y})\n")

    def _on_insert_code_from_tree(self, path: str):
        self.editor.insert_locator_code(f"auto.find_and_tap('{path}')\n")

    def _on_refresh_tree(self):
        device = self._device_mgr.active
        if not device or device.status != "online":
            return
        try:
            self._cached_root = device.poco.get_root()
            self._cached_flat = device.poco._flatten_tree(self._cached_root)
            self.tree_panel.load_tree(self._cached_root)
            self.clickable_panel.set_device(device)
            self.clickable_panel.load_clickable_nodes(self._cached_flat)
            logger.info("UI tree refreshed")
        except Exception as e:
            logger.warning("Failed to refresh tree: %s", e)
            self.console.append_text(f"刷新 UI 树失败: {e}", is_error=True)

    def _on_tree_selection_changed(self):
        node_data = self.tree_panel.get_selected_node_data()
        if node_data:
            node_id = node_data.get("node_id", "")
            if node_id and node_id != "root":
                device = self._device_mgr.active
                if device and device.status == "online":
                    try:
                        attrs = device.poco.get_attributes(node_id)
                        self.property_panel.show_properties(attrs)
                    except Exception:
                        self.property_panel.show_properties(node_data)
            else:
                self.property_panel.show_properties(node_data)
        else:
            self.property_panel.show_properties({})

    def _on_clickable_node_selected(self, node_id: str):
        if node_id:
            self.tree_panel.highlight_node(node_id)
        device = self._device_mgr.active
        if node_id and node_id != "root" and device and device.status == "online":
            try:
                attrs = device.poco.get_attributes(node_id)
                self.property_panel.show_properties(attrs)
            except Exception:
                node = next((n for n in self._cached_flat if n.get("node_id") == node_id), None)
                if node:
                    self.property_panel.show_properties(node.get("payload", {}))
                else:
                    self.property_panel.show_properties({})
        else:
            self.property_panel.show_properties({})

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
        air_dir = QFileDialog.getExistingDirectory(self, "新建 .air 工程", "",)
        if not air_dir:
            return
        if not air_dir.endswith(".air"):
            air_dir += ".air"
        air_path = Path(air_dir)
        air_path.mkdir(exist_ok=True)
        script = air_path / "script.py"
        if not script.exists():
            script.write_text("# 在此编写自动化脚本\nimport time\ntime.sleep(2)\n", encoding="utf-8")
        self._current_air = str(air_path)
        self._current_script = None
        self.editor.setPlainText(script.read_text(encoding="utf-8"))
        self.editor.document().setModified(False)
        logger.info("New .air project: %s", air_path)

    def _on_open(self):
        if not self._check_unsaved():
            return
        # 直接打开单个 .py 脚本文件
        py_file, _ = QFileDialog.getOpenFileName(
            self, "打开脚本文件", "", "Python 文件 (*.py);;所有文件 (*)"
        )
        if not py_file:
            return
        try:
            content = Path(py_file).read_text(encoding="utf-8")
            self.editor.setPlainText(content)
            self._current_air = None
            self._current_script = py_file
            self.editor.document().setModified(False)
            logger.info("Opened script: %s", py_file)
        except Exception as e:
            QMessageBox.warning(self, "打开失败", str(e))

    def _on_save(self):
        script_path = getattr(self, "_current_script", None)
        if script_path:
            try:
                Path(script_path).write_text(self.editor.toPlainText(), encoding="utf-8")
                self.editor.document().setModified(False)
                logger.info("Saved script: %s", script_path)
            except Exception as e:
                QMessageBox.warning(self, "保存失败", str(e))
            return
        air_dir = getattr(self, "_current_air", None)
        if not air_dir:
            air_dir = QFileDialog.getExistingDirectory(self, "保存到 .air 工程", "",)
            if not air_dir:
                return
            if not air_dir.endswith(".air"):
                air_dir += ".air"
            Path(air_dir).mkdir(exist_ok=True)
            self._current_air = air_dir
        script = Path(air_dir) / "script.py"
        try:
            script.write_text(self.editor.toPlainText(), encoding="utf-8")
            self.editor.document().setModified(False)
            logger.info("Saved script: %s", script)
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _on_about(self):
        QMessageBox.about(self, "关于 AutoTest IDE",
                          "AutoTest IDE v1.0\n\n"
                          "基于 Poco 协议的 UI 自动化测试 IDE\n"
                          "使用 PyQt5 构建")

    def _on_run_clicked(self):
        device = self._device_mgr.active
        logger.info("_on_run_clicked: device=%s status=%s", device, getattr(device, 'status', None))
        if not device or device.status != "online":
            self.console.append_text("错误: 没有在线设备", is_error=True)
            return
        script_path = getattr(self, "_current_script", None)
        logger.info("_on_run_clicked: _current_script=%s _current_air=%s", script_path, getattr(self, "_current_air", None))
        if script_path:
            Path(script_path).write_text(self.editor.toPlainText(), encoding="utf-8")
            air_dir = str(Path(script_path).parent)
        else:
            air_dir = getattr(self, "_current_air", None) or "test.air"
            Path(air_dir).mkdir(exist_ok=True)
            script = Path(air_dir) / "script.py"
            script.write_text(self.editor.toPlainText(), encoding="utf-8")
        logger.info("Running: air_dir=%s script_path=%s sdk=%s", air_dir, script_path, self.sdk_combo.currentData())
        sdk = self.sdk_combo.currentData() or "jx4"
        self._run_controller.start(
            str(air_dir), device.device_type, device.name,
            device.poco.port, sdk=sdk, device=device,
            script_path=script_path or "",
        )

    def _on_stop_clicked(self):
        logger.info("Stopping script")
        self._run_controller.stop()

    def _on_run_started(self):
        self.run_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(False)
        self.device_panel.setEnabled(False)

    def _on_run_finished(self, exit_code: int, report_path: str):
        self.run_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.record_btn.setEnabled(True)
        self.device_panel.setEnabled(True)
        logger.info("Script finished exit_code=%d report_path=%s", exit_code, report_path)
        self.console.append_text(f"脚本结束 (exit code: {exit_code})")
        if report_path and Path(report_path).exists():
            try:
                render_report(Path(report_path), Path(report_path).parent / "report.html")
            except Exception as e:
                logger.warning("Report rendering failed: %s", e, exc_info=True)

    def _on_run_stopped(self):
        self.run_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.record_btn.setEnabled(True)
        self.device_panel.setEnabled(True)

    def _on_record_clicked(self):
        if not self._cached_flat:
            device = self._device_mgr.active
            if device and device.status == "online":
                try:
                    self._cached_root = device.poco.get_root()
                    self._cached_flat = device.poco._flatten_tree(self._cached_root)
                except Exception as e:
                    self.console.append_warn(f"刷新 UI 树失败: {e}")
                    return
            else:
                self.console.append_warn("请先连接设备")
                return
        self._record_controller.start(self._cached_flat)
        self.record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        self.run_btn.setEnabled(False)
        self.record_action.setEnabled(False)
        self.stop_record_action.setEnabled(True)
        self.console.append_text("录制开始 — 点击设备截图将自动生成代码")

    def _on_stop_record_clicked(self):
        self._record_controller.stop()
        self.record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self.run_btn.setEnabled(True)
        self.record_action.setEnabled(True)
        self.stop_record_action.setEnabled(False)
        self.console.append_text("录制停止")

    def closeEvent(self, event):
        if not self._check_unsaved():
            event.ignore()
            return
        # 停止运行中的脚本线程
        if self._run_controller:
            self._run_controller.stop()
        # 停止设备扫描线程
        scan_worker = getattr(self, "_scan_worker", None)
        if scan_worker and scan_worker.isRunning():
            scan_worker.quit()
            scan_worker.wait(2000)
            self._scan_worker = None
        # 断开设备：关 socket、停所有 Worker、停心跳
        self._disconnect_device()
        self._device_mgr.shutdown()
        super().closeEvent(event)
        os._exit(0)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.WindowStateChange and hasattr(self, "_title_bar"):
            self._title_bar.update_max_button()

    # ── Edge resize for frameless window ──────────────────────────
    _RESIZE_MARGIN = 6

    def _edge_at(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self._RESIZE_MARGIN
        on_left = x < m
        on_right = x >= w - m
        on_top = y < m
        on_bottom = y >= h - m
        if on_top and on_left:     return Qt.TopLeftCorner
        if on_top and on_right:    return Qt.TopRightCorner
        if on_bottom and on_left:  return Qt.BottomLeftCorner
        if on_bottom and on_right: return Qt.BottomRightCorner
        if on_left:   return Qt.LeftEdge
        if on_right:  return Qt.RightEdge
        if on_top:    return Qt.TopEdge
        if on_bottom: return Qt.BottomEdge
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._edge_at(event.pos())
            if edge is not None:
                # Use native Win32 hit-test resize: query the window handle
                import ctypes
                from ctypes import wintypes
                hwnd = int(self.winId())
                resize_map = {
                    Qt.TopLeftCorner: 13, Qt.TopEdge: 12, Qt.TopRightCorner: 14,
                    Qt.RightEdge: 11, Qt.BottomRightCorner: 17,
                    Qt.BottomEdge: 15, Qt.BottomLeftCorner: 16, Qt.LeftEdge: 10,
                }
                code = resize_map.get(edge)
                if code:
                    ctypes.windll.user32.ReleaseCapture()
                    ctypes.windll.user32.SendMessageW(
                        hwnd, 0xA1, code, 0,
                    )
                    event.accept()
                    return
        super().mousePressEvent(event)
