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
