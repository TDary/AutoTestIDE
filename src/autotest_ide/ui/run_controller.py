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
    run_finished = pyqtSignal(int, str)
    run_started = pyqtSignal()
    run_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._air_dir: str = ""
        self._stopping = False
        self._inproc_future = None

    def start(self, air_dir: str, device_type: str, device_serial: str,
              poco_port: int, timeout: int = 600, sdk: str = "poco"):
        self._air_dir = air_dir
        self._stopping = False
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
        if self._stopping:
            return
        self._stopping = True
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
            # In-process run — cancel the future if we have one
            if self._inproc_future is not None and not self._inproc_future.done():
                self._inproc_future.cancel()
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

    def _run_inproc(self, air_dir: str, poco_port: int, timeout: int, sdk: str):
        """Execute the user's script inside the current process (frozen mode)."""
        import io
        import contextlib
        from concurrent.futures import Future, ThreadPoolExecutor
        from autotest_ide.core.poco_client import PocoClient
        from autotest_ide.sdks import PROTOCOL_REGISTRY
        from autotest_ide.runner.reporter import Reporter
        from autotest_ide.runner.recorder import RecordingPocoClient
        from autotest_ide.runner.runtime import build_namespace

        # Load protocol
        spec = PROTOCOL_REGISTRY.get(sdk, "")
        if ":" in spec:
            mod_path, cls_name = spec.rsplit(":", 1)
        else:
            mod_path = f"autotest_ide.sdks.{sdk}.protocol"
            cls_name = sdk.upper() + "Protocol"
        import importlib
        mod = importlib.import_module(mod_path)
        proto_cls = getattr(mod, cls_name)
        protocol = proto_cls()

        poco = PocoClient(host="127.0.0.1", port=poco_port, protocol=protocol)
        try:
            poco.connect()
        except Exception as e:
            self.output_received.emit(f"ERROR: connect failed: {e}\n", True)
            self.run_finished.emit(1, "")
            return

        reporter = Reporter(Path(air_dir), "local", "")
        recorder = RecordingPocoClient(poco, reporter)
        namespace = build_namespace(recorder, reporter)

        script_path = Path(air_dir) / "script.py"
        script_src = script_path.read_text(encoding="utf-8")

        # Capture stdout/stderr from exec so we can emit it to the console
        buf = io.StringIO()
        status = "pass"
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(compile(script_src, str(script_path), "exec"), namespace)
        except Exception as e:
            buf.write(f"\nERROR: {e}\n")
            import traceback
            traceback.print_exc(file=buf)
            status = "fail"
        finally:
            poco.close()

        # Emit all captured output
        output = buf.getvalue()
        if output:
            for line in output.splitlines(keepends=True):
                is_err = "ERROR" in line or "Traceback" in line
                self.output_received.emit(line, is_err)

        reporter.finish(status, script=str(script_path))
        report_path = str(Path(air_dir) / "report.json")
        if self._stopping:
            self.run_stopped.emit()
        else:
            self.run_finished.emit(0 if status == "pass" else 1, report_path)
