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

    def __getattr__(self, name):
        return getattr(self._inner, name)
