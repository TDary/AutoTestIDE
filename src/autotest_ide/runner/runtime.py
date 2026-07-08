from autotest_ide.core.errors import PocoConnectionError
from autotest_ide.core.log import getLogger
from autotest_ide.runner.recorder import RecordingPocoClient
from autotest_ide.runner.reporter import Reporter

logger = getLogger(__name__)


class By:
    """Lookup strategies for ``poco.find_and_tap(by=...)``."""
    PATH = "path"
    NAME = "path"       # same as PATH for JX4
    TAG = "tag"
    LAYER = "layer"
    COMPONENT = "component"
    ID = "id"


def build_namespace(poco: RecordingPocoClient, reporter: Reporter) -> dict:
    def snapshot() -> None:
        shot = poco.screenshot()
        reporter.step_start("snapshot()")
        reporter.step_pass(screenshot=shot)

    def assert_exists(locator: str, msg: str = "") -> None:
        reporter.step_start(f"assert_exists({locator!r})")
        try:
            if not poco.heartbeat():
                raise PocoConnectionError("heartbeat failed")
            reporter.step_pass(screenshot=poco.screenshot())
        except Exception as e:
            reporter.step_fail(error=str(e), screenshot=poco.screenshot())
            logger.warning("assert_exists failed: %s", e)
            raise AssertionError(msg or str(e))

    def wait_for(locator: str, timeout: int = 10) -> None:
        poco.wait_for_node(locator, timeout)

    def wait_for_gone(locator: str, timeout: int = 10) -> None:
        poco.wait_for_gone(locator, timeout)

    def log(msg: str) -> None:
        reporter.step_start(f"log: {msg}")
        reporter.step_pass()
        print(msg)

    return {
        "auto": poco,
        "By": By,
        "snapshot": snapshot,
        "assert_exists": assert_exists,
        "wait_for": wait_for,
        "wait_for_gone": wait_for_gone,
        "log": log,
    }
