"""可点击按钮面板 —— 展示 UI 树中所有 Button/Toggle 节点"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QApplication,
)

_CLR_ENABLED = QColor("#a6e3a1")
_CLR_DISABLED = QColor("#f9e2af")

# Name keywords that likely indicate a clickable node (pre-filter for JX4)
_CLICKABLE_NAME_KEYWORDS = ("Btn", "Anniu", "Button", "Toggle", "btn")


class ClickablePanel(QWidget):
    node_selected = pyqtSignal(str)
    insert_code_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._table = QTableWidget(0, 4, self)
        self._table.setObjectName("clickable_table")
        self._table.setHorizontalHeaderLabels(["名称", "类型", "文本", "路径"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        self._row_data: list[tuple[str, str]] = []
        self._device = None

        self._table.cellClicked.connect(self._on_row_clicked)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self._table.customContextMenuRequested.connect(self._on_context_menu)

    # ── public ────────────────────────────────────────────────────────

    def set_device(self, device) -> None:
        self._device = device

    def load_clickable_nodes(self, flat_nodes: list) -> None:
        self._table.setRowCount(0)
        self._row_data.clear()
        paths = _build_paths(flat_nodes)

        # Step 1: pre-filter candidates by name keywords (JX4 dump has no components)
        candidates = []
        for node in flat_nodes:
            payload = node.get("payload", {})
            # Standard Poco: components list already present
            components = payload.get("components", [])
            if components:
                comp_types = [c.get("type", "") for c in components if isinstance(c, dict)]
                if any("Button" in ct or "Toggle" in ct for ct in comp_types):
                    candidates.append(node)
                    continue
            # JX4 fallback: name keywords
            name = node.get("name", "")
            if any(kw in name for kw in _CLICKABLE_NAME_KEYWORDS):
                candidates.append(node)

        # Step 2: for JX4 candidates, call get_attributes to confirm via components
        for node in candidates:
            payload = node.get("payload", {})
            node_id = node.get("node_id", "")
            name = node.get("name", "")
            path = paths.get(node_id, name)

            # If payload already has components (standard Poco), use it directly
            components = payload.get("components", [])
            if components:
                self._add_row(node, path, payload)
                continue

            # JX4: try get_attributes for full component list
            attrs = self._get_attrs(node_id)
            if attrs and _attrs_has_button(attrs):
                self._add_row(node, path, attrs)
            elif any(kw in name for kw in _CLICKABLE_NAME_KEYWORDS):
                # get_attributes failed but name matches — show anyway
                self._add_row(node, path, payload)

        self._table.resizeColumnsToContents()

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._row_data.clear()

    # ── private ───────────────────────────────────────────────────────

    def _get_attrs(self, node_id: str) -> dict | None:
        if not self._device or not node_id:
            return None
        try:
            return self._device.poco.get_attributes(node_id)
        except Exception:
            return None

    def _add_row(self, node: dict, path: str, payload: dict) -> None:
        name = node.get("name", "")
        ntype = node.get("type", "")
        text = payload.get("text", "")
        node_id = node.get("node_id", "")
        enabled = payload.get("enabled", True)

        row = self._table.rowCount()
        self._table.insertRow(row)
        self._row_data.append((node_id, path))

        fg = _CLR_ENABLED if enabled is not False else _CLR_DISABLED

        for col, value in enumerate([name, ntype, text, path]):
            item = QTableWidgetItem(value)
            item.setForeground(fg)
            item.setData(Qt.UserRole, (node_id, path))
            self._table.setItem(row, col, item)

    def _on_row_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._row_data):
            self.node_selected.emit(self._row_data[row][0])

    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._row_data):
            self.insert_code_requested.emit(self._row_data[row][1])

    def _on_context_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._row_data):
            return
        node_id, path = self._row_data[row]
        menu = QMenu(self)
        copy_act = QAction(f"复制路径: {path}", self)
        insert_act = QAction(f"插入点击代码: {path}", self)
        menu.addAction(copy_act)
        menu.addAction(insert_act)

        def _copy():
            QApplication.clipboard().setText(path)

        def _insert():
            self.insert_code_requested.emit(path)

        copy_act.triggered.connect(_copy)
        insert_act.triggered.connect(_insert)
        menu.exec_(self._table.viewport().mapToGlobal(pos))


# ── helpers ─────────────────────────────────────────────────────────


def _attrs_has_button(attrs: dict) -> bool:
    components = attrs.get("components", [])
    if not components:
        return False
    comp_types = [c.get("type", "") for c in components if isinstance(c, dict)]
    return any("Button" in ct or "Toggle" in ct for ct in comp_types)


# ── path builder (mirrors locator.py _build_parent_map) ──────────────


def _build_paths(flat_nodes: list) -> dict[str, str]:
    by_id: dict[str, dict] = {}
    parent_of: dict[str, str] = {}
    for node in flat_nodes:
        nid = node.get("node_id", "")
        if nid:
            by_id[nid] = node
    for node in flat_nodes:
        for child in node.get("children", []):
            cid = child.get("node_id", "")
            if cid and cid in by_id:
                parent_of[cid] = node.get("node_id", "")

    result: dict[str, str] = {}
    for nid in by_id:
        parts: list[str] = []
        cur = nid
        visited: set[str] = set()
        while cur and cur not in visited:
            visited.add(cur)
            n = by_id.get(cur)
            if n is None:
                break
            name = n.get("name", "")
            if name and name != "root":
                parts.append(name)
            cur = parent_of.get(cur, "")
        parts.reverse()
        if parts:
            result[nid] = "/".join(parts)
    return result
