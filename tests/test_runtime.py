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
