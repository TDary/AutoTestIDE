import json
import tempfile
from pathlib import Path

import pytest

from autotest_ide.core.poco_client import PocoClient
from autotest_ide.runner.reporter import Reporter
from autotest_ide.runner.recorder import RecordingPocoClient
from autotest_ide.report import render_report

from tests.fake_poco_server import FakePocoServer


def test_click_and_report():
    """Integration: run click through RecordingPocoClient, verify report.json + HTML render."""
    server = FakePocoServer()
    server.start()
    try:
        poco = PocoClient(host="127.0.0.1", port=server.port)
        poco.connect()

        with tempfile.TemporaryDirectory() as tmp:
            reporter = Reporter(Path(tmp), "android", "test-serial")
            recorder = RecordingPocoClient(poco, reporter)

            recorder.click(540, 960)
            recorder.close()

            reporter.finish("pass", script="test.air/script.py")

            report_path = Path(tmp) / "report.json"
            assert report_path.exists()

            data = json.loads(report_path.read_text(encoding="utf-8"))
            assert data["summary"]["status"] == "pass"
            assert len(data["steps"]) == 1
            assert data["steps"][0]["name"] == "click(540, 960)"
            assert data["steps"][0]["status"] == "pass"

            # Render HTML
            html_path = Path(tmp) / "report.html"
            render_report(report_path, html_path)
            assert html_path.exists()
            html_content = html_path.read_text(encoding="utf-8")
            assert "click(540, 960)" in html_content
            assert "pass" in html_content
    finally:
        poco.close()
        server.stop()
