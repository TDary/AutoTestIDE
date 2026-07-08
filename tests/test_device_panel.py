from autotest_ide.core.code_gen import OpMode
from autotest_ide.ui.device_panel import DevicePanel, OverlayWidget


def test_default_opmode_is_click(qtbot):
    panel = DevicePanel()
    assert panel.op_mode == OpMode.CLICK


def test_opmode_switch_click(qtbot):
    panel = DevicePanel()
    panel._btn_long_press.click()
    assert panel.op_mode == OpMode.LONG_PRESS
    panel._btn_swipe.click()
    assert panel.op_mode == OpMode.SWIPE
    panel._btn_input.click()
    assert panel.op_mode == OpMode.INPUT
    panel._btn_click.click()
    assert panel.op_mode == OpMode.CLICK


def test_overlay_swipe_line(qtbot):
    overlay = OverlayWidget()
    from PyQt5.QtCore import QPoint
    overlay.set_swipe_line(QPoint(10, 20), QPoint(100, 200))
    assert overlay._show_swipe is True
    overlay.clear_swipe_line()
    assert overlay._show_swipe is False
