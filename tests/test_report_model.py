import pytest
from autotest_ide.core.report_model import ReportStep, ReportSummary


def test_report_step_creation():
    step = ReportStep(index=1, name="click(540, 960)", status="pass",
                      screenshot="step_1.png", error="", timestamp=1.0)
    assert step.index == 1
    assert step.status == "pass"
    assert step.screenshot == "step_1.png"


def test_report_step_to_dict():
    step = ReportStep(index=1, name="click", status="pass",
                      screenshot="step_1.png", error="", timestamp=1.0)
    d = step.to_dict()
    assert d["index"] == 1
    assert d["status"] == "pass"
    assert "screenshot" in d


def test_report_summary_creation():
    s = ReportSummary(script="test.air/script.py", device_type="android",
                      device_serial="emulator-5554", start_time=0.0,
                      end_time=10.0, total_steps=3, passed=2, failed=1,
                      status="fail")
    assert s.total_steps == 3
    assert s.status == "fail"


def test_report_summary_to_dict():
    s = ReportSummary(script="t.py", device_type="android",
                      device_serial="x", start_time=0, end_time=1,
                      total_steps=1, passed=1, failed=0, status="pass")
    d = s.to_dict()
    assert d["total_steps"] == 1
    assert d["status"] == "pass"
