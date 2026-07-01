import json
import time
from pathlib import Path
from typing import Optional

from autotest_ide.core.log import getLogger
from autotest_ide.core.report_model import ReportStep, ReportSummary

logger = getLogger(__name__)


class Reporter:
    def __init__(self, air_dir: Path, device_type: str, device_serial: str):
        self._air_dir = air_dir
        self._device_type = device_type
        self._device_serial = device_serial
        self._steps: list = []
        self._start_time = time.time()
        self._current_step: Optional[ReportStep] = None

    @property
    def steps(self) -> list:
        return self._steps

    def step_start(self, name: str):
        self._current_step = ReportStep(
            index=len(self._steps) + 1,
            name=name,
            status="running",
            screenshot="",
            error="",
            timestamp=time.time(),
        )

    def step_pass(self, screenshot: bytes = b""):
        step = self._current_step
        if step is None:
            return
        step.status = "pass"
        if screenshot:
            step.screenshot = self._save_screenshot(step.index, screenshot)
        self._steps.append(step)
        self._current_step = None

    def step_fail(self, error: str = "", screenshot: bytes = b""):
        step = self._current_step
        if step is None:
            return
        step.status = "fail"
        step.error = error
        if screenshot:
            step.screenshot = self._save_screenshot(step.index, screenshot)
        self._steps.append(step)
        self._current_step = None

    def finish(self, status: str, script: str = ""):
        end_time = time.time()
        passed = sum(1 for s in self._steps if s.status == "pass")
        failed = sum(1 for s in self._steps if s.status == "fail")
        summary = ReportSummary(
            script=script,
            device_type=self._device_type,
            device_serial=self._device_serial,
            start_time=self._start_time,
            end_time=end_time,
            total_steps=len(self._steps),
            passed=passed,
            failed=failed,
            status=status,
        )
        report = {
            "summary": summary.to_dict(),
            "steps": [s.to_dict() for s in self._steps],
        }
        report_path = self._air_dir / "report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Report written: %s", report_path)

    def _save_screenshot(self, step_index: int, data: bytes) -> str:
        filename = f"step_{step_index}.png"
        path = self._air_dir / filename
        path.write_bytes(data)
        logger.debug("Screenshot saved: %s", path)
        return filename
