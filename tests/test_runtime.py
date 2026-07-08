from unittest.mock import MagicMock

from autotest_ide.runner.runtime import build_namespace


def test_namespace_has_auto():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    assert "auto" in ns
    assert ns["auto"] is recorder


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


def test_namespace_has_wait_for():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    assert callable(ns["wait_for"])


def test_namespace_has_wait_for_gone():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    assert callable(ns["wait_for_gone"])


def test_wait_for_delegates_to_poco():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    ns["wait_for"]("Panel/Btn", timeout=10)
    recorder.wait_for_node.assert_called_once_with("Panel/Btn", 10)


def test_wait_for_gone_delegates_to_poco():
    recorder = MagicMock()
    reporter = MagicMock()
    ns = build_namespace(recorder, reporter)
    ns["wait_for_gone"]("Panel/Loading", timeout=15)
    recorder.wait_for_gone.assert_called_once_with("Panel/Loading", 15)
