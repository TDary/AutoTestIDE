from autotest_ide.runner.recorder import RecordingPocoClient
from autotest_ide.runner.reporter import Reporter


def build_namespace(poco: RecordingPocoClient, reporter: Reporter) -> dict:
    def snapshot() -> None:
        shot = poco.screenshot()
        reporter.step_start("snapshot()")
        reporter.step_pass(screenshot=shot)

    def assert_exists(locator: str, msg: str = "") -> None:
        reporter.step_start(f"assert_exists({locator!r})")
        try:
            poco.get_root()
            reporter.step_pass(screenshot=poco.screenshot())
        except Exception as e:
            reporter.step_fail(error=str(e), screenshot=poco.screenshot())
            raise AssertionError(msg or str(e))

    def log(msg: str) -> None:
        reporter.step_start(f"log: {msg}")
        reporter.step_pass()

    return {
        "poco": poco,
        "snapshot": snapshot,
        "assert_exists": assert_exists,
        "log": log,
    }
