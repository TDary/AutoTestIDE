import json
import tempfile
from pathlib import Path

import pytest

from autotest_ide.runner.reporter import Reporter


_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_reporter_step_pass():
    with tempfile.TemporaryDirectory() as tmp:
        reporter = Reporter(Path(tmp), "android", "serial1")
        reporter.step_start("click(540, 960)")
        reporter.step_pass(screenshot=_FAKE_PNG)
        assert len(reporter.steps) == 1
        assert reporter.steps[0].status == "pass"
        assert reporter.steps[0].screenshot == "step_1.png"
        assert (Path(tmp) / "step_1.png").exists()


def test_reporter_step_fail():
    with tempfile.TemporaryDirectory() as tmp:
        reporter = Reporter(Path(tmp), "android", "serial1")
        reporter.step_start("click(540, 960)")
        reporter.step_fail(error="timeout", screenshot=_FAKE_PNG)
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


def test_reporter_rejects_invalid_png():
    with tempfile.TemporaryDirectory() as tmp:
        reporter = Reporter(Path(tmp), "android", "serial1")
        reporter.step_start("bad screenshot")
        reporter.step_pass(screenshot=b"not-a-png-at-all")
        assert reporter.steps[0].screenshot == ""
        assert not (Path(tmp) / "step_1.png").exists()
