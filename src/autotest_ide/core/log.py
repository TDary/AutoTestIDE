import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _log_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent.parent.parent
    d = base / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_logging(filename: str = "autotest_ide.log", level: int = logging.INFO) -> None:
    log_file = _log_dir() / filename
    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = RotatingFileHandler(
            str(log_file), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        root.addHandler(handler)

    if getattr(sys, "frozen", False):
        def excepthook(exc_type, exc_value, exc_tb):
            logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        sys.excepthook = excepthook


def getLogger(name: str) -> logging.Logger:
    return logging.getLogger(name)
