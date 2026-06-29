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
