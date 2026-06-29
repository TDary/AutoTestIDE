import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent


def render_report(report_json_path: Path, output_path: Path) -> Path:
    data = json.loads(report_json_path.read_text(encoding="utf-8"))
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("template.html")
    html = template.render(summary=data["summary"], steps=data["steps"])
    output_path.write_text(html, encoding="utf-8")
    return output_path
