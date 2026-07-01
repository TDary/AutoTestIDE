"""Subprocess entry point: python -m autotest_ide.runner.runtest <air_dir> [options]

Loads and executes the user's .air/script.py with an injected namespace
containing poco, snapshot, assert_exists, log.
"""
import argparse
import importlib
import os
import signal
import sys
import threading
import time
from pathlib import Path

from autotest_ide.core.log import getLogger, setup_logging
from autotest_ide.core.poco_client import PocoClient
from autotest_ide.core.protocol_base import PocoProtocol
from autotest_ide.runner.recorder import RecordingPocoClient
from autotest_ide.runner.reporter import Reporter
from autotest_ide.runner.runtime import build_namespace
from autotest_ide.sdks import PROTOCOL_REGISTRY

logger = getLogger(__name__)


def _load_protocol(spec: str) -> PocoProtocol:
    """Load a protocol class from a ``package.module:ClassName`` spec.

    Accepts either a registry short name (e.g. ``"jx4"``) or a fully
    qualified ``package.module:ClassName`` spec.
    """
    if ":" in spec:
        module_path, class_name = spec.rsplit(":", 1)
    elif spec in PROTOCOL_REGISTRY:
        full_spec = PROTOCOL_REGISTRY[spec]
        module_path, class_name = full_spec.rsplit(":", 1)
    else:
        # try sdks package by name
        module_path = f"autotest_ide.sdks.{spec}.protocol"
        class_name = spec.upper() + "Protocol"
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls()


def _watchdog(timeout: int):
    time.sleep(timeout)
    os._exit(2)


def main():
    setup_logging(filename="runner.log")
    parser = argparse.ArgumentParser(description="Run an .air script")
    parser.add_argument("air_dir", type=str, help="Path to the .air directory")
    parser.add_argument("--device-type", default="android", help="Device type")
    parser.add_argument("--device-serial", default="", help="Device serial")
    parser.add_argument("--poco-port", type=int, default=13000, help="Poco service port")
    parser.add_argument("--timeout", type=int, default=600, help="Overall timeout in seconds")
    parser.add_argument("--protocol", default="jx4",
                        help="Protocol adapter name or package.module:Class spec")
    args = parser.parse_args()

    air_dir = Path(args.air_dir).resolve()
    if not air_dir.is_dir():
        logger.error("air_dir is not a directory: %s", air_dir)
        sys.exit(1)
    if not str(air_dir).endswith(".air"):
        logger.error("air_dir must end with .air: %s", air_dir)
        sys.exit(1)
    script_path = air_dir / "script.py"
    if not script_path.exists():
        logger.error("Script not found: %s", script_path)
        sys.exit(1)

    # Load protocol adapter — fall back to jx4 on failure
    try:
        protocol = _load_protocol(args.protocol)
    except Exception as e:
        logger.error("Failed to load protocol %r: %s", args.protocol, e)
        protocol = _load_protocol("jx4")

    # Setup timeout: POSIX uses SIGALRM, Windows uses watchdog thread
    if hasattr(signal, "SIGALRM"):
        signal.alarm(args.timeout)
    else:
        t = threading.Thread(target=_watchdog, args=(args.timeout,), daemon=True)
        t.start()

    poco = PocoClient(host="127.0.0.1", port=args.poco_port, protocol=protocol)
    try:
        poco.connect()
    except Exception as e:
        logger.error("Failed to connect to Poco service: %s", e)
        sys.exit(1)

    reporter = Reporter(air_dir, args.device_type, args.device_serial)
    recorder = RecordingPocoClient(poco, reporter)
    namespace = build_namespace(recorder, reporter)

    logger.info("Executing script: %s", script_path)
    script_src = script_path.read_text(encoding="utf-8")
    status = "pass"
    try:
        exec(compile(script_src, str(script_path), "exec"), namespace)
    except Exception as e:
        logger.error("Script error: %s", e, exc_info=True)
        status = "fail"
    finally:
        poco.close()

    reporter.finish(status, script=str(script_path))
    logger.info("Script finished: status=%s", status)
    sys.exit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
