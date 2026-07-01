import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from autotest_ide.core.log import getLogger

logger = getLogger(__name__)


def _template_dir() -> Path:
    """Find report templates — works both in dev and in PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        return base / "autotest_ide" / "report"
    return Path(__file__).parent


TEMPLATE_DIR = _template_dir()
logger.debug("Template dir: %s", TEMPLATE_DIR)


def render_report(report_json_path: Path, output_path: Path) -> Path:
    data = json.loads(report_json_path.read_text(encoding="utf-8"))
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("template.html")
    html = template.render(summary=data["summary"], steps=data["steps"])
    output_path.write_text(html, encoding="utf-8")
    logger.info("Report rendered: %s", output_path)
    return output_path
