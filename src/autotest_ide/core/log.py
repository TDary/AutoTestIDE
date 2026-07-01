import logging
import os
import re
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


def _sanitize(msg: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(msg))


class _SanitizingFormatter(logging.Formatter):
    def format(self, record):
        orig_msg, orig_args = record.msg, record.args
        record.msg = _sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _sanitize(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_sanitize(a) for a in record.args)
        try:
            return super().format(record)
        finally:
            record.msg = orig_msg
            record.args = orig_args


def setup_logging(filename: str = "autotest_ide.log", level: int = logging.INFO) -> None:
    log_file = _log_dir() / filename
    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = RotatingFileHandler(
            str(log_file), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fmt = _SanitizingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(fmt)
        root.addHandler(handler)

    if getattr(sys, "frozen", False):
        def excepthook(exc_type, exc_value, exc_tb):
            logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        sys.excepthook = excepthook


def getLogger(name: str) -> logging.Logger:
    return logging.getLogger(name)
