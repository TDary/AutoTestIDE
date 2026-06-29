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
