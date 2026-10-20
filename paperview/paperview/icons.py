"""
Vector SVG Icon provider for PaperView.
Generates crisp, high-DPI QIcons without external image dependencies or emoji.
"""

from typing import Dict
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

SVG_TEMPLATES: Dict[str, str] = {
    "open": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
</svg>""",

    "save": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
<polyline points="17 21 17 13 7 13 7 21"></polyline>
<polyline points="7 3 7 8 15 8"></polyline>
</svg>""",

    "sidebar": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
<line x1="9" y1="3" x2="9" y2="21"></line>
</svg>""",

    "prev": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<polyline points="15 18 9 12 15 6"></polyline>
</svg>""",

    "next": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<polyline points="9 18 15 12 9 6"></polyline>
</svg>""",

    "zoom_in": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="11" cy="11" r="8"></circle>
<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
<line x1="11" y1="8" x2="11" y2="14"></line>
<line x1="8" y1="11" x2="14" y2="11"></line>
</svg>""",

    "zoom_out": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="11" cy="11" r="8"></circle>
<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
<line x1="8" y1="11" x2="14" y2="11"></line>
</svg>""",

    "fit_width": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<line x1="2" y1="3" x2="2" y2="21"></line>
<line x1="22" y1="3" x2="22" y2="21"></line>
<polyline points="6 9 3 12 6 15"></polyline>
<polyline points="18 9 21 12 18 15"></polyline>
<line x1="3" y1="12" x2="21" y2="12"></line>
</svg>""",

    "fit_page": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="5" y="3" width="14" height="18" rx="2"></rect>
<line x1="9" y1="7" x2="15" y2="7"></line>
<line x1="9" y1="11" x2="15" y2="11"></line>
</svg>""",

    "find": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="11" cy="11" r="8"></circle>
<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
</svg>""",

    "properties": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<circle cx="12" cy="12" r="10"></circle>
<line x1="12" y1="16" x2="12" y2="12"></line>
<line x1="12" y1="8" x2="12.01" y2="8"></line>
</svg>""",

    "close": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<line x1="18" y1="6" x2="6" y2="18"></line>
<line x1="6" y1="6" x2="18" y2="18"></line>
</svg>""",

    "chevron_up": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<polyline points="18 15 12 9 6 15"></polyline>
</svg>""",

    "chevron_down": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<polyline points="6 9 12 15 18 9"></polyline>
</svg>""",

    "select": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M3 3l7 18 3-7 7-3L3 3z"></path>
</svg>""",

    "highlight": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="m9 11-6 6v3h3l6-6"></path>
<path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"></path>
</svg>""",

    "underline": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M6 3v7a6 6 0 0 0 12 0V3"></path>
<line x1="4" y1="21" x2="20" y2="21"></line>
</svg>""",

    "note": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
</svg>""",

    "pen": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
</svg>""",

    "view_continuous": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="6" y="2" width="12" height="8" rx="1"></rect>
<rect x="6" y="14" width="12" height="8" rx="1"></rect>
</svg>""",

    "view_single": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="5" y="3" width="14" height="18" rx="2"></rect>
<line x1="9" y1="7" x2="15" y2="7"></line>
<line x1="9" y1="11" x2="15" y2="11"></line>
</svg>""",

    "organize": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="7" height="7"></rect>
<rect x="14" y="3" width="7" height="7"></rect>
<rect x="14" y="14" width="7" height="7"></rect>
<rect x="3" y="14" width="7" height="7"></rect>
</svg>""",

    "rotate_cw": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38"/>
</svg>""",

    "rotate_ccw": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/>
</svg>""",

    "delete": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<polyline points="3 6 5 6 21 6"></polyline>
<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
</svg>""",

    "duplicate": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
</svg>""",

    "extract": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
<polyline points="14 2 14 8 20 8"></polyline>
<polyline points="16 13 12 9 8 13"></polyline>
<line x1="12" y1="9" x2="12" y2="18"></line>
</svg>""",

    "move_left": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<line x1="19" y1="12" x2="5" y2="12"></line>
<polyline points="12 19 5 12 12 5"></polyline>
</svg>""",

    "move_right": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
<line x1="5" y1="12" x2="19" y2="12"></line>
<polyline points="12 5 19 12 12 19"></polyline>
</svg>""",

    "merge": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M8 3v6l-4 4"></path>
<path d="M16 3v6l4 4"></path>
<path d="M12 11v10"></path>
<polyline points="8 17 12 21 16 17"></polyline>
</svg>""",

    "split": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
<polyline points="14 2 14 8 20 8"></polyline>
<line x1="2" y1="14" x2="22" y2="14" stroke-dasharray="3 3"></line>
</svg>""",

    "watermark": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path>
</svg>""",

    "optimize": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
</svg>""",
}


def _render_pixmap(svg_template: str, color: str, size: int) -> QPixmap:
    svg_str = svg_template.format(color=color)
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pixmap


def get_icon(name: str, size: int = 20) -> QIcon:
    """
    Returns a crisp multi-state QIcon for normal, active, and disabled states.
    Falls back to empty QIcon if icon name not found.
    """
    if name not in SVG_TEMPLATES:
        return QIcon()

    template = SVG_TEMPLATES[name]
    icon = QIcon()

    # Normal state (#d4d7dc)
    pix_normal = _render_pixmap(template, "#d4d7dc", size)
    icon.addPixmap(pix_normal, QIcon.Mode.Normal, QIcon.State.Off)

    # Active / Selected state (#ffffff)
    pix_active = _render_pixmap(template, "#ffffff", size)
    icon.addPixmap(pix_active, QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(pix_active, QIcon.Mode.Normal, QIcon.State.On)

    # Disabled state (#656870)
    pix_disabled = _render_pixmap(template, "#656870", size)
    icon.addPixmap(pix_disabled, QIcon.Mode.Disabled, QIcon.State.Off)

    return icon
