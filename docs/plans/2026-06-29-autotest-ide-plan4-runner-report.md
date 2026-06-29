# Plan 4: Script Runner + HTML Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the script runner subsystem — spawn `runtest.py` subprocess to execute user `.air` scripts, record every Poco operation as a report step (screenshot + status), generate `report.json`, render HTML report with Jinja2 template, display in IDE or browser.

**Architecture:** IDE spawns `python -m autotest_ide.runner.runtest <air_dir> --device-type <t> --device-serial <s> --poco-port <p>`. The subprocess loads script, injects namespace with `poco` (RecordingPocoClient), `snapshot`, `assert_exists`, `log`. Each operation auto-records step with screenshot. On finish, writes `report.json`. IDE reads it, renders HTML, displays in QWebEngineView.

**Tech Stack:** Python 3.8+ stdlib + Jinja2 + psutil + PyQt5 + pytest. `core/` stays PyQt-free.

**Spec reference:** `docs/specs/2026-06-29-autotest-ide-plan4-runner-report-design.md`; parent spec §7, §6.5.

**Project root:** `E:/AutoTestIDE/`. All paths relative to it.

**Deviations from spec:**
1. QWebEngineView for report display (fallback: webbrowser.open).
2. Accumulate steps in memory, write report.json at finish (not per-step IO).
3. RecordingPocoClient only records operation methods, not query methods.

---

## File Structure

```
E:/AutoTestIDE/
├── src/autotest_ide/
│   ├── core/
│   │   └── report_model.py          # Task 1: ReportStep + ReportSummary dataclasses
│   ├── runner/
│   │   ├── __init__.py              # Task 2: package init
│   │   ├── reporter.py             # Task 3: Reporter class
│   │   ├── recorder.py             # Task 4: RecordingPocoClient
│   │   ├── runtime.py              # Task 5: build_namespace()
│   │   └── runtest.py              # Task 6: subprocess entry point
│   ├── report/
│   │   ├── template.html            # Task 7: Jinja2 HTML template
│   │   ├── report.css               # Task 7
│   │   └── report.js                # Task 7
│   └── ui/
│       ├── run_controller.py        # Task 8: RunController (subprocess management)
│       └── report_view.py           # Task 9: ReportView (HTML display)
└── tests/
    ├── test_report_model.py         # Task 1
    ├── test_reporter.py             # Task 3
    ├── test_recorder.py             # Task 4
    ├── test_runtime.py              # Task 5
    ├── test_runtest.py              # Task 6: integration test
    └── test_run_controller.py       # Task 8
```

---

## Task 1: Report Data Model (core/report_model.py)

**Files:**
- Create: `src/autotest_ide/core/report_model.py`
- Create: `tests/test_report_model.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests** → FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement `src/autotest_ide/core/report_model.py`**

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class ReportStep:
    index: int
    name: str
    status: str
    screenshot: str
    error: str
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "status": self.status,
            "screenshot": self.screenshot,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ReportSummary:
    script: str
    device_type: str
    device_serial: str
    start_time: float
    end_time: float
    total_steps: int
    passed: int
    failed: int
    status: str

    def to_dict(self) -> dict:
        return {
            "script": self.script,
            "device_type": self.device_type,
            "device_serial": self.device_serial,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_steps": self.total_steps,
            "passed": self.passed,
            "failed": self.failed,
            "status": self.status,
        }
```

- [ ] **Step 4: Run tests** → 4 passed

- [ ] **Step 5: Verify no PyQt** → OK

---

## Task 2: Runner Package Init

- [ ] **Step 1: Write `src/autotest_ide/runner/__init__.py`** (empty file)

---

## Task 3: Reporter Class (runner/reporter.py)

**Files:**
- Create: `src/autotest_ide/runner/reporter.py`
- Create: `tests/test_reporter.py`

- [ ] **Step 1: Write failing tests**

```python
import json
import tempfile
from pathlib import Path

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
```

- [ ] **Step 2: Run tests** → FAIL

- [ ] **Step 3: Implement `src/autotest_ide/runner/reporter.py`**

```python
import json
import time
from pathlib import Path
from typing import Optional

from autotest_ide.core.report_model import ReportStep, ReportSummary


class Reporter:
    def __init__(self, air_dir: Path, device_type: str, device_serial: str):
        self._air_dir = air_dir
        self._device_type = device_type
        self._device_serial = device_serial
        self._steps: list[ReportStep] = []
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
        report = {"summary": summary.to_dict(), "steps": [s.to_dict() for s in self._steps]}
        report_path = self._air_dir / "report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    def _save_screenshot(self, step_index: int, data: bytes) -> str:
        filename = f"step_{step_index}.png"
        path = self._air_dir / filename
        path.write_bytes(data)
        return filename
```

- [ ] **Step 4: Run tests** → 3 passed

---

## Task 4: RecordingPocoClient (runner/recorder.py)

**Files:**
- Create: `src/autotest_ide/runner/recorder.py`
- Create: `tests/test_recorder.py`

- [ ] **Step 1: Write failing tests**

```python
from unittest.mock import MagicMock

from autotest_ide.runner.recorder import RecordingPocoClient


def test_query_methods_pass_through():
    inner = MagicMock()
    inner.get_root.return_value = {"node_id": "root"}
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    result = rec.get_root()
    assert result == {"node_id": "root"}
    inner.get_root.assert_called_once()
    reporter.step_start.assert_not_called()


def test_click_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.click(540, 960)
    reporter.step_start.assert_called_once_with("click(540, 960)")
    reporter.step_pass.assert_called_once()
    inner.click.assert_called_once_with(540, 960)


def test_click_failure_records_fail():
    inner = MagicMock()
    inner.click.side_effect = Exception("boom")
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    import pytest
    with pytest.raises(Exception, match="boom"):
        rec.click(540, 960)
    reporter.step_start.assert_called_once()
    reporter.step_fail.assert_called_once()
```

- [ ] **Step 2: Run tests** → FAIL

- [ ] **Step 3: Implement `src/autotest_ide/runner/recorder.py`**

```python
from autotest_ide.core.poco_client import PocoClient
from autotest_ide.runner.reporter import Reporter


class RecordingPocoClient:
    """Wraps PocoClient, records operation methods as report steps."""

    def __init__(self, inner: PocoClient, reporter: Reporter):
        self._inner = inner
        self._reporter = reporter

    # Query methods — pass through, no recording
    def get_root(self):
        return self._inner.get_root()

    def dump_hierarchy(self, depth=None):
        return self._inner.dump_hierarchy(depth)

    def get_screen_size(self):
        return self._inner.get_screen_size()

    def get_attributes(self, node_id):
        return self._inner.get_attributes(node_id)

    def inspect_by_point(self, x, y):
        return self._inner.inspect_by_point(x, y)

    def screenshot(self):
        return self._inner.screenshot()

    def heartbeat(self):
        return self._inner.heartbeat()

    def close(self):
        return self._inner.close()

    def connect(self):
        return self._inner.connect()

    # Operation methods — record as steps
    def click(self, x: int, y: int):
        self._reporter.step_start(f"click({x}, {y})")
        try:
            self._inner.click(x, y)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def set_text(self, node_id: str, text: str):
        self._reporter.step_start(f"set_text({node_id!r}, {text!r})")
        try:
            self._inner.set_text(node_id, text)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise
```

- [ ] **Step 4: Run tests** → 3 passed

---

## Task 5: PocoClient Protocol Extension (click, set_text)

**Files:**
- Modify: `src/autotest_ide/core/poco_client.py`
- Modify: `tests/test_poco_client.py`

- [ ] **Step 1: Add click and set_text methods to PocoClient**

In `poco_client.py`, add after `heartbeat()`:

```python
    def click(self, x: int, y: int) -> dict:
        return self._request_json("click", {"x": x, "y": y})

    def set_text(self, node_id: str, text: str) -> dict:
        return self._request_json("set_text", {"node_id": node_id, "text": text})
```

- [ ] **Step 2: Add click test to FakePocoServer**

In `fake_poco_server.py`, add to `_dispatch`:

```python
        if method == "click":
            return {"jsonrpc": "2.0", "id": seq, "result": {}}
        if method == "set_text":
            return {"jsonrpc": "2.0", "id": seq, "result": {}}
```

- [ ] **Step 3: Write test**

```python
def test_click_sends_request(fake_server):
    client = PocoClient(host="127.0.0.1", port=fake_server.port)
    client.connect()
    try:
        result = client.click(540, 960)
        assert isinstance(result, dict)
    finally:
        client.close()
```

- [ ] **Step 4: Run tests** → pass

---

## Task 6: Runtime Namespace (runner/runtime.py)

**Files:**
- Create: `src/autotest_ide/runner/runtime.py`
- Create: `tests/test_runtime.py`

- [ ] **Step 1: Write failing tests**

```python
from autotest_ide.runner.runtime import build_namespace
from unittest.mock import MagicMock


def test_namespace_has_poco():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    assert "poco" in ns
    assert ns["poco"] is recorder


def test_namespace_has_snapshot():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    assert callable(ns["snapshot"])


def test_namespace_has_log():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    assert callable(ns["log"])
```

- [ ] **Step 2: Implement `src/autotest_ide/runner/runtime.py`**

```python
from typing import Callable

from autotest_ide.runner.recorder import RecordingPocoClient
from autotest_ide.runner.reporter import Reporter


def build_namespace(poco: RecordingPocoClient, reporter: Reporter) -> dict:
    def snapshot() -> None:
        shot = poco.screenshot()
        reporter.step_start("snapshot()")
        reporter.step_pass(screenshot=shot)

    def assert_exists(locator: str, msg: str = "") -> None:
        reporter.step_start(f"assert_exists({locator!r})")
        try:
            poco.get_root()  # simple check — real impl would resolve locator
            reporter.step_pass(screenshot=poco.screenshot())
        except Exception as e:
            reporter.step_fail(error=str(e), screenshot=poco.screenshot())
            raise AssertionError(msg or str(e))

    def log(msg: str) -> None:
        reporter.step_start(f"log: {msg}")
        reporter.step_pass()

    return {
        "poco": poco,
        "snapshot": snapshot,
        "assert_exists": assert_exists,
        "log": log,
    }
```

- [ ] **Step 3: Run tests** → 3 passed

---

## Task 7: HTML Report Template

**Files:**
- Create: `src/autotest_ide/report/template.html`
- Create: `src/autotest_ide/report/report.css`
- Create: `src/autotest_ide/report/report.js`

- [ ] **Step 1: Write template.html**

A minimal Jinja2 template that receives `summary` and `steps` variables, renders a pass/fail summary table + step-by-step timeline with thumbnails.

- [ ] **Step 2: Write report.css** — Clean, minimal styling

- [ ] **Step 3: Write report.js** — Step thumbnail click-to-zoom

- [ ] **Step 4: Write a helper to render the report**

In `src/autotest_ide/report/__init__.py`:

```python
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent


def render_report(report_json_path: Path, output_path: Path) -> Path:
    data = json.loads(report_json_path.read_text(encoding="utf-8"))
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("template.html")
    html = template.render(summary=data["summary"], steps=data["steps"])
    output_path.write_text(html, encoding="utf-8")
    return output_path
```

---

## Task 8: RunController (ui/run_controller.py)

**Files:**
- Create: `src/autotest_ide/ui/run_controller.py`
- Create: `tests/test_run_controller.py`

- [ ] **Step 1: Write `src/autotest_ide/ui/run_controller.py`**

Manages subprocess lifecycle: start, read stdout, timeout, stop (psutil).

- [ ] **Step 2: Write basic import test**

---

## Task 9: ReportView (ui/report_view.py)

**Files:**
- Create: `src/autotest_ide/ui/report_view.py`

- [ ] **Step 1: Implement** — Try QWebEngineView, fallback to webbrowser.open()

---

## Task 10: Integration Test + Full Verification

- [ ] **Step 1: Write integration test** — Use fake_poco_server, run minimal script via runtest.py, verify report.json

- [ ] **Step 2: Run full test suite** → all pass

- [ ] **Step 3: Verify core/ no PyQt**

---

**文档结束**
