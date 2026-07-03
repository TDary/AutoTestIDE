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
        # PyInstaller bundles the interpreter as python3X.dll + bootloader.
        # There's no standalone python.exe to invoke, so we can't spawn a
        # subprocess. Instead we'll exec the script in-process (see _run_inproc).
        return None
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
    step_screenshot = pyqtSignal(bytes)
    run_finished = pyqtSignal(int, str)
    run_started = pyqtSignal()
    run_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._air_dir: str = ""
        self._stop_event = threading.Event()
        self._device = None  # set by start()

    def start(self, air_dir: str, device_type: str, device_serial: str,
              poco_port: int, timeout: int = 600, sdk: str = "poco",
              device=None):
        self._air_dir = air_dir
        self._stop_event.clear()
        self._device = device
        cmd = _build_runtest_cmd(
            air_dir, device_type, device_serial, poco_port, timeout, sdk,
        )
        if cmd is not None:
            # Dev mode — spawn a subprocess
            logger.info("Spawning subprocess: %s", " ".join(cmd))
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            self._reader_thread = threading.Thread(
                target=self._read_output, daemon=True,
            )
            self._reader_thread.start()
        else:
            # Frozen mode — exec in a background thread
            self._process = None
            self._reader_thread = threading.Thread(
                target=self._run_inproc,
                args=(air_dir, poco_port, timeout, sdk),
                daemon=True,
            )
            self._reader_thread.start()
        self.run_started.emit()

    def stop(self):
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        if self._process is not None:
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
        else:
            # In-process run — signal stop event
            pass
        if self._reader_thread:
            self._reader_thread.join(timeout=3)

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
            if self._stop_event.is_set():
                self.run_stopped.emit()
            else:
                self.run_finished.emit(exit_code, report_path)

    def _run_inproc(self, air_dir: str, poco_port: int, timeout: int, sdk: str):
        """Execute the user's script inside the current process (frozen mode).

        Reuses the existing PocoClient from the connected device instead of
        creating a new TCP connection — JX4 only accepts one client at a time.
        """
        import io
        import contextlib
        from autotest_ide.runner.reporter import Reporter
        from autotest_ide.runner.recorder import RecordingPocoClient
        from autotest_ide.runner.runtime import build_namespace

        device = self._get_device()
        if device is None or device.poco is None:
            self.output_received.emit("ERROR: no connected device\n", True)
            self.run_finished.emit(1, "")
            return

        poco = device.poco
        reporter = Reporter(
            Path(air_dir), "local", "",
            on_screenshot=lambda data: self.step_screenshot.emit(data),
        )
        recorder = RecordingPocoClient(poco, reporter)
        namespace = build_namespace(recorder, reporter)

        script_path = Path(air_dir) / "script.py"
        script_src = script_path.read_text(encoding="utf-8")

        # Stream stdout/stderr to console in real-time
        class _StreamToSignal(io.StringIO):
            def __init__(self, signal, is_err=False):
                super().__init__()
                self._signal = signal
                self._is_err = is_err

            def write(self, s):
                if s:
                    self._signal.emit(s, self._is_err)
                return len(s)

            def flush(self):
                pass

        out_stream = _StreamToSignal(self.output_received, False)
        err_stream = _StreamToSignal(self.output_received, True)
        status = "pass"
        try:
            with contextlib.redirect_stdout(out_stream), contextlib.redirect_stderr(err_stream):
                exec(compile(script_src, str(script_path), "exec"), namespace)
        except Exception as e:
            self.output_received.emit(f"ERROR: {e}\n", True)
            import traceback
            traceback.print_exc(file=err_stream)
            status = "fail"
        # Don't close poco — we're reusing the IDE's existing connection

        reporter.finish(status, script=str(script_path))
        report_path = str(Path(air_dir) / "report.json")
        if self._stop_event.is_set():
            self.run_stopped.emit()
        else:
            self.run_finished.emit(0 if status == "pass" else 1, report_path)

    def _get_device(self):
        return self._device
