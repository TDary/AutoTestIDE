import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

import psutil
from PyQt5.QtCore import QObject, pyqtSignal


class RunController(QObject):
    output_received = pyqtSignal(str, bool)
    run_finished = pyqtSignal(int, str)
    run_started = pyqtSignal()
    run_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None

    def start(self, air_dir: str, device_type: str, device_serial: str,
              poco_port: int, timeout: int = 600):
        cmd = [
            sys.executable, "-m", "autotest_ide.runner.runtest",
            air_dir,
            "--device-type", device_type,
            "--device-serial", device_serial,
            "--poco-port", str(poco_port),
            "--timeout", str(timeout),
        ]
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
        try:
            proc = psutil.Process(self._process.pid)
            children = proc.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            proc.kill()
        except psutil.NoSuchProcess:
            pass
        self._process = None
        self.run_stopped.emit()

    def _read_output(self):
        if self._process is None:
            return
        try:
            for line in self._process.stdout:
                self.output_received.emit(line, False)
        except ValueError:
            pass
        finally:
            exit_code = self._process.wait() if self._process else -1
            report_path = ""
            self.run_finished.emit(exit_code, report_path)
            self._process = None
