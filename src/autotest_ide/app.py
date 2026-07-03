import os
import sys
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox

from autotest_ide.core.log import getLogger, setup_logging
from autotest_ide.ui.main_window import MainWindow
from autotest_ide.ui.style import DARK_STYLE

logger = getLogger(__name__)


def main():
    # 切走 CWD，避免锁住 exe 所在目录导致删除失败
    os.chdir(os.path.expanduser("~"))

    setup_logging()
    logger.info("AutoTest IDE starting")
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("AutoTest IDE")
        app.setOrganizationName("AutoTest")
        app.setStyleSheet(DARK_STYLE)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception:
        logger.critical("Unhandled exception during startup", exc_info=True)
        if QApplication.instance():
            QMessageBox.critical(None, "Startup Error", traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
