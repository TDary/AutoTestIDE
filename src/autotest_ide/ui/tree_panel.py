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
        self._node_map: dict = {}

    def load_tree(self, root_node: dict):
        self._model.clear()
        self._model.setHorizontalHeaderLabels(["名称", "类型", "文本"])
        self._node_map.clear()
        self._add_node(root_node, self._model.invisibleRootItem())

    def _add_node(self, node: dict, parent_item):
        stack = [(node, parent_item)]
        while stack:
            current, parent = stack.pop()
            name = current.get("name", "")
            ntype = current.get("type", "")
            text = current.get("payload", {}).get("text", "")
            node_id = current.get("node_id", "")

            name_item = QStandardItem(name)
            type_item = QStandardItem(ntype)
            text_item = QStandardItem(text)

            name_item.setData(node_id, Qt.UserRole)
            name_item.setEditable(False)
            type_item.setEditable(False)
            text_item.setEditable(False)

            parent.appendRow([name_item, type_item, text_item])

            if node_id:
                self._node_map[node_id] = name_item

            for child in reversed(current.get("children", [])):
                stack.append((child, name_item))

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
