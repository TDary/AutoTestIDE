"""Subprocess entry point: python -m autotest_ide.runner.runtest <air_dir> [options]

Loads and executes the user's .air/script.py with an injected namespace
containing poco, snapshot, assert_exists, log.
"""
import argparse
import signal
import sys
import time
from pathlib import Path

from autotest_ide.core.log import getLogger, setup_logging
from autotest_ide.core.poco_client import PocoClient
from autotest_ide.runner.recorder import RecordingPocoClient
from autotest_ide.runner.reporter import Reporter
from autotest_ide.runner.runtime import build_namespace

logger = getLogger(__name__)


def main():
    setup_logging(filename="runner.log")
    parser = argparse.ArgumentParser(description="Run an .air script")
    parser.add_argument("air_dir", type=str, help="Path to the .air directory")
    parser.add_argument("--device-type", default="android", help="Device type")
    parser.add_argument("--device-serial", default="", help="Device serial")
    parser.add_argument("--poco-port", type=int, default=13000, help="Poco service port")
    parser.add_argument("--timeout", type=int, default=600, help="Overall timeout in seconds")
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

    # Setup timeout alarm (POSIX only; Windows relies on parent process kill)
    if hasattr(signal, "SIGALRM"):
        signal.alarm(args.timeout)

    poco = PocoClient(host="127.0.0.1", port=args.poco_port)
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
