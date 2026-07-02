from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView


class PropertyPanel(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["属性", "值"])
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.setSelectionBehavior(QTableWidget.SelectItems)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAlternatingRowColors(True)

    def show_properties(self, props: dict):
        self.setRowCount(0)
        if not props:
            return

        # Extract component info
        components = props.get("components", [])
        comp_types = [c.get("type", "") for c in components if isinstance(c, dict)]
        has_button = any("Button" in ct for ct in comp_types)
        has_toggle = any("Toggle" in ct for ct in comp_types)
        clickable = has_button or has_toggle
        enabled = props.get("enabled", None)

        # Add status row at top
        if clickable:
            status = "Button" if has_button else "Toggle"
            if enabled is False:
                status += " (disabled)"
            label = f"  {status}"
            color = QColor("#a6e3a1") if enabled is not False else QColor("#f9e2af")
        else:
            label = "  不可点击"
            color = QColor("#6c7086")

        row = 0
        self.insertRow(row)
        item_key = QTableWidgetItem("可点击")
        item_key.setForeground(QColor("#cdd6f4"))
        item_val = QTableWidgetItem(label)
        item_val.setForeground(color)
        font = item_val.font()
        font.setBold(True)
        item_val.setFont(font)
        self.setItem(row, 0, item_key)
        self.setItem(row, 1, item_val)

        # Add other properties
        for key, value in props.items():
            if key == "components":
                for i, comp in enumerate(components):
                    if isinstance(comp, dict):
                        ctype = comp.get("type", "")
                        row = self.rowCount()
                        self.insertRow(row)
                        self.setItem(row, 0, QTableWidgetItem(f"component[{i}]"))
                        self.setItem(row, 1, QTableWidgetItem(ctype))
                        for prop in comp.get("properties", []):
                            pname = prop.get("name", "")
                            pval = prop.get("value", "")
                            row = self.rowCount()
                            self.insertRow(row)
                            self.setItem(row, 0, QTableWidgetItem(f"  {pname}"))
                            self.setItem(row, 1, QTableWidgetItem(str(pval)))
            else:
                row = self.rowCount()
                self.insertRow(row)
                self.setItem(row, 0, QTableWidgetItem(str(key)))
                self.setItem(row, 1, QTableWidgetItem(str(value)))
