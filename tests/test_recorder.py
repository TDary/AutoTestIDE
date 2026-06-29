from unittest.mock import MagicMock

import pytest

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

    with pytest.raises(Exception, match="boom"):
        rec.click(540, 960)
    reporter.step_start.assert_called_once()
    reporter.step_fail.assert_called_once()


def test_set_text_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.set_text("btn_play", "Hello")
    reporter.step_start.assert_called_once_with("set_text('btn_play', 'Hello')")
    reporter.step_pass.assert_called_once()
    inner.set_text.assert_called_once_with("btn_play", "Hello")
