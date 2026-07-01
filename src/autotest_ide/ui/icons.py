"""SVG-based icons for toolbar buttons.

Renders clean line-art SVG strings into ``QIcon`` so the toolbar
doesn't depend on external image assets. Colors are injected at
render time to match the Catppuccin Mocha palette.
"""
from PyQt5.QtCore import QByteArray, QSize, Qt
from PyQt5.QtGui import QPixmap, QPainter, QIcon
from PyQt5.QtSvg import QSvgRenderer

_SVG_TEMPLATES = {
    "refresh": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/>'
        '<path d="M21 3v5h-5"/></svg>'
    ),
    "connect": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 22v-5"/>'
        '<path d="M9 8V2"/>'
        '<path d="M15 8V2"/>'
        '<path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/></svg>'
    ),
    "disconnect": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 2v10"/>'
        '<path d="M18.4 6.6a9 9 0 1 1-12.77.04"/></svg>'
    ),
    "run": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="{color}" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="6 3 20 12 6 21 6 3"/></svg>'
    ),
    "stop": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="{color}" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="6" y="6" width="12" height="12" rx="1"/></svg>'
    ),
    "logo": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="8 17 12 21 16 17"/>'
        '<line x1="12" y1="12" x2="12" y2="21"/>'
        '<path d="M16 4H8a2 2 0 0 0-2 2v3a6 6 0 0 0 12 0V6a2 2 0 0 0-2-2z"/>'
        '<line x1="8" y1="10" x2="2" y2="12"/>'
        '<line x1="22" y1="12" x2="16" y2="10"/></svg>'
    ),
}


def _render_svg(svg: str, size: int = 18) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def make_icon(name: str, color: str = "#cdd6f4",
              disabled_color: str = "#585b70", size: int = 18) -> QIcon:
    """Build a QIcon from a named SVG template.

    Generates Normal and Disabled modes so disabled buttons look grayed out.
    """
    if name not in _SVG_TEMPLATES:
        raise KeyError(f"unknown icon: {name!r}")
    icon = QIcon()
    svg_normal = _SVG_TEMPLATES[name].replace("{color}", color)
    svg_disabled = _SVG_TEMPLATES[name].replace("{color}", disabled_color)
    icon.addPixmap(_render_svg(svg_normal, size), QIcon.Normal, QIcon.Off)
    icon.addPixmap(_render_svg(svg_disabled, size), QIcon.Disabled, QIcon.Off)
    return icon
