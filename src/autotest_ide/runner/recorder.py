from autotest_ide.core.log import getLogger
from autotest_ide.core.poco_client import PocoClient
from autotest_ide.runner.reporter import Reporter

logger = getLogger(__name__)


class RecordingPocoClient:
    """Wraps PocoClient, records operation methods as report steps."""

    def __init__(self, inner: PocoClient, reporter: Reporter):
        self._inner = inner
        self._reporter = reporter

    # Query methods — pass through, no recording
    def get_root(self):
        return self._inner.get_root()

    def dump_hierarchy(self, only_visible=True):
        return self._inner.dump_hierarchy(only_visible)

    def get_attributes(self, node_id, attr=""):
        return self._inner.get_attributes(node_id, attr)

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
                logger.warning("Screenshot fallback failed after click error", exc_info=True)
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
                logger.warning("Screenshot fallback failed after set_text error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def find_and_tap(self, path: str, camera: str = "", rml: int = -1, by: str = "path"):
        self._reporter.step_start(f"find_and_tap({path!r}, by={by!r})")
        try:
            self._inner.find_and_tap(path, camera, rml, by)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after find_and_tap error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def long_click(self, x: int, y: int, duration: float = 2.0):
        self._reporter.step_start(f"long_click({x}, {y}, duration={duration})")
        try:
            self._inner.long_click(x, y, duration=duration)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after long_click error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        self._reporter.step_start(f"swipe({x1}, {y1}, {x2}, {y2}, duration={duration})")
        try:
            self._inner.swipe(x1, y1, x2, y2, duration=duration)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after swipe error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def drag(self, node_id: str, x2: int, y2: int):
        self._reporter.step_start(f"drag({node_id!r}, {x2}, {y2})")
        try:
            self._inner.drag(node_id, x2, y2)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after drag error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def wait_for_node(self, path: str, timeout: float = 10.0):
        self._reporter.step_start(f"wait_for_node({path!r}, timeout={timeout})")
        try:
            self._inner.wait_for_node(path, timeout=timeout)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after wait_for_node error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def wait_for_gone(self, path: str, timeout: float = 10.0):
        self._reporter.step_start(f"wait_for_gone({path!r}, timeout={timeout})")
        try:
            self._inner.wait_for_gone(path, timeout=timeout)
            self._reporter.step_pass(screenshot=self._inner.screenshot())
        except Exception as e:
            try:
                shot = self._inner.screenshot()
            except Exception:
                logger.warning("Screenshot fallback failed after wait_for_gone error", exc_info=True)
                shot = b""
            self._reporter.step_fail(error=str(e), screenshot=shot)
            raise

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._inner, name)
