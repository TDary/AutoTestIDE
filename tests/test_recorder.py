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


def test_long_click_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.long_click(540, 960, duration=2.0)
    reporter.step_start.assert_called_once_with("long_click(540, 960, duration=2.0)")
    reporter.step_pass.assert_called_once()
    inner.long_click.assert_called_once_with(540, 960, duration=2.0)


def test_long_click_failure_records_fail():
    inner = MagicMock()
    inner.long_click.side_effect = Exception("timeout")
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    with pytest.raises(Exception, match="timeout"):
        rec.long_click(540, 960)
    reporter.step_start.assert_called_once()
    reporter.step_fail.assert_called_once()


def test_swipe_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.swipe(100, 200, 300, 400, duration=0.5)
    reporter.step_start.assert_called_once_with("swipe(100, 200, 300, 400, duration=0.5)")
    reporter.step_pass.assert_called_once()
    inner.swipe.assert_called_once_with(100, 200, 300, 400, duration=0.5)


def test_drag_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.drag("node_1", 500, 600)
    reporter.step_start.assert_called_once_with("drag('node_1', 500, 600)")
    reporter.step_pass.assert_called_once()
    inner.drag.assert_called_once_with("node_1", 500, 600)


def test_wait_for_node_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.wait_for_node("Panel/Btn", timeout=10.0)
    reporter.step_start.assert_called_once_with("wait_for_node('Panel/Btn', timeout=10.0)")
    reporter.step_pass.assert_called_once()
    inner.wait_for_node.assert_called_once_with("Panel/Btn", timeout=10.0)


def test_wait_for_gone_records_step():
    inner = MagicMock()
    inner.screenshot.return_value = b"\x89PNG"
    reporter = MagicMock()
    rec = RecordingPocoClient(inner, reporter)

    rec.wait_for_gone("Panel/Loading", timeout=15.0)
    reporter.step_start.assert_called_once_with("wait_for_gone('Panel/Loading', timeout=15.0)")
    reporter.step_pass.assert_called_once()
    inner.wait_for_gone.assert_called_once_with("Panel/Loading", timeout=15.0)
