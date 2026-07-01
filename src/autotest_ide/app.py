import sys
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox

from autotest_ide.core.log import getLogger, setup_logging
from autotest_ide.ui.main_window import MainWindow

logger = getLogger(__name__)


def main():
    setup_logging()
    logger.info("AutoTest IDE starting")
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("AutoTest IDE")
        app.setOrganizationName("AutoTest")
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
