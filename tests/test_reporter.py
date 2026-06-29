import json
import tempfile
from pathlib import Path

import pytest

from autotest_ide.runner.reporter import Reporter


def test_reporter_step_pass():
    with tempfile.TemporaryDirectory() as tmp:
        reporter = Reporter(Path(tmp), "android", "serial1")
        reporter.step_start("click(540, 960)")
        reporter.step_pass(screenshot=b"\x89PNG")
        assert len(reporter.steps) == 1
        assert reporter.steps[0].status == "pass"
        assert reporter.steps[0].screenshot == "step_1.png"
        assert (Path(tmp) / "step_1.png").exists()


def test_reporter_step_fail():
    with tempfile.TemporaryDirectory() as tmp:
        reporter = Reporter(Path(tmp), "android", "serial1")
        reporter.step_start("click(540, 960)")
        reporter.step_fail(error="timeout", screenshot=b"\x89PNG")
        assert reporter.steps[0].status == "fail"
        assert reporter.steps[0].error == "timeout"


def test_reporter_finish_writes_json():
    with tempfile.TemporaryDirectory() as tmp:
        reporter = Reporter(Path(tmp), "android", "serial1")
        reporter.step_start("step1")
        reporter.step_pass()
        reporter.finish("pass")
        report_path = Path(tmp) / "report.json"
        assert report_path.exists()
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert "summary" in data
        assert "steps" in data
        assert data["summary"]["status"] == "pass"
        assert len(data["steps"]) == 1
