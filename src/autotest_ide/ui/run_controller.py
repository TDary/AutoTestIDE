import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

import psutil
from PyQt5.QtCore import QObject, pyqtSignal

from autotest_ide.core.log import getLogger

logger = getLogger(__name__)


def _build_runtest_cmd(air_dir: str, device_type: str, device_serial: str,
                       poco_port: int, timeout: int, sdk: str = "poco"):
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent / "_internal" / "scripts"
        cmd = [sys.executable, str(base / "runtest.py")]
    else:
        cmd = [sys.executable, "-m", "autotest_ide.runner.runtest"]

    cmd += [
        air_dir,
        "--device-type", device_type,
        "--device-serial", device_serial,
        "--poco-port", str(poco_port),
        "--timeout", str(timeout),
        "--protocol", sdk,
    ]
    return cmd


class RunController(QObject):
    output_received = pyqtSignal(str, bool)
    run_finished = pyqtSignal(int, str)
    run_started = pyqtSignal()
    run_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._air_dir: str = ""
        self._stopping = False

    def start(self, air_dir: str, device_type: str, device_serial: str,
              poco_port: int, timeout: int = 600, sdk: str = "poco"):
        self._air_dir = air_dir
        self._stopping = False
        cmd = _build_runtest_cmd(
            air_dir, device_type, device_serial, poco_port, timeout, sdk,
        )
        logger.info("Spawning subprocess: %s", " ".join(cmd))
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        self._reader_thread = threading.Thread(
            target=self._read_output, daemon=True,
        )
        self._reader_thread.start()
        self.run_started.emit()

    def stop(self):
        if self._process is None:
            return
        self._stopping = True
        logger.info("Stopping subprocess PID=%d", self._process.pid)
        try:
            proc = psutil.Process(self._process.pid)
            children = proc.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    logger.debug("Child process already dead")
            proc.kill()
        except psutil.NoSuchProcess:
            logger.debug("Process already dead during kill")
        if self._reader_thread:
            self._reader_thread.join(timeout=3000)

    def _read_output(self):
        process = self._process
        if process is None:
            return
        try:
            for line in process.stdout:
                self.output_received.emit(line, False)
        except ValueError:
            logger.debug("Pipe closed during read")
        finally:
            exit_code = process.wait()
            report_path = str(Path(self._air_dir) / "report.json") if self._air_dir else ""
            logger.debug("Subprocess exited code=%d", exit_code)
            self._process = None
            if self._stopping:
                self.run_stopped.emit()
            else:
                self.run_finished.emit(exit_code, report_path)
