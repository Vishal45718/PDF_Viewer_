"""
Design tokens, color palettes, and global stylesheets for PaperView.
Provides a cohesive, professional dark charcoal theme with a distraction-free workspace.
"""

class Theme:
    # Color Tokens
    BG_WINDOW = "#1e2023"          # Deep charcoal window chrome
    BG_TOOLBAR = "#26282c"         # Slightly lifted header bar
    BG_SIDEBAR = "#222428"         # Left sidebar surface
    BG_CANVAS = "#33363c"          # Neutral distraction-free document canvas
    BG_INPUT = "#181a1d"           # Dark inset inputs
    BG_HOVER = "#303338"           # Hover state
    BG_ACTIVE = "#283750"          # Selected/Active state
    
    ACCENT = "#3574f0"             # Restrained primary blue
    ACCENT_HOVER = "#4b85f5"
    ACCENT_MUTED = "rgba(53, 116, 240, 0.18)"

    TEXT_PRIMARY = "#f0f2f5"
    TEXT_SECONDARY = "#9da2ab"
    TEXT_MUTED = "#686c75"

    BORDER_SUBTLE = "#363940"
    BORDER_INPUT = "#444750"
    BORDER_FOCUS = "#3574f0"

    PAGE_BORDER = "#d6d9de"

    @classmethod
    def main_stylesheet(cls) -> str:
        return f"""
        QMainWindow {{
            background-color: {cls.BG_WINDOW};
        }}

        /* Toolbar Styling */
        QToolBar {{
            background-color: {cls.BG_TOOLBAR};
            border-bottom: 1px solid {cls.BORDER_SUBTLE};
            spacing: 4px;
            padding: 4px 10px;
        }}

        QToolButton {{
            background-color: transparent;
            color: {cls.TEXT_PRIMARY};
            border: 1px solid transparent;
            border-radius: 5px;
            padding: 5px 8px;
            font-weight: 500;
            font-size: 12px;
        }}
        QToolButton:hover {{
            background-color: {cls.BG_HOVER};
            border: 1px solid {cls.BORDER_SUBTLE};
        }}
        QToolButton:pressed {{
            background-color: {cls.BG_ACTIVE};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.ACCENT};
        }}
        QToolButton:checked {{
            background-color: {cls.BG_ACTIVE};
            color: #70a0ff;
            border: 1px solid {cls.ACCENT};
        }}
        QToolButton:disabled {{
            color: {cls.TEXT_MUTED};
        }}

        /* Inputs & Combos */
        QLineEdit {{
            background-color: {cls.BG_INPUT};
            border: 1px solid {cls.BORDER_INPUT};
            border-radius: 4px;
            color: {cls.TEXT_PRIMARY};
            padding: 4px 8px;
            font-size: 12px;
            selection-background-color: {cls.ACCENT};
        }}
        QLineEdit:focus {{
            border: 1px solid {cls.BORDER_FOCUS};
        }}

        QComboBox {{
            background-color: {cls.BG_INPUT};
            border: 1px solid {cls.BORDER_INPUT};
            border-radius: 4px;
            color: {cls.TEXT_PRIMARY};
            padding: 3px 8px;
            font-size: 12px;
            min-width: 68px;
        }}
        QComboBox:hover {{
            border: 1px solid {cls.BORDER_SUBTLE};
        }}
        QComboBox:focus {{
            border: 1px solid {cls.BORDER_FOCUS};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 18px;
            border-left: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {cls.BG_TOOLBAR};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER_SUBTLE};
            selection-background-color: {cls.ACCENT};
            outline: none;
        }}

        /* Splitter */
        QSplitter::handle {{
            background-color: {cls.BORDER_SUBTLE};
            width: 1px;
        }}

        /* Status Bar */
        QStatusBar {{
            background-color: {cls.BG_WINDOW};
            color: {cls.TEXT_SECONDARY};
            border-top: 1px solid {cls.BORDER_SUBTLE};
            font-size: 11px;
            padding: 2px 8px;
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            background: {cls.BG_CANVAS};
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #50545c;
            min-height: 24px;
            border-radius: 4px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #686e78;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {cls.BG_CANVAS};
            height: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: #50545c;
            min-width: 24px;
            border-radius: 4px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #686e78;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* Menu Bar & Menus */
        QMenuBar {{
            background-color: {cls.BG_TOOLBAR};
            color: {cls.TEXT_PRIMARY};
            border-bottom: 1px solid {cls.BORDER_SUBTLE};
            padding: 2px 6px;
            font-size: 12px;
        }}
        QMenuBar::item {{
            background-color: transparent;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background-color: {cls.BG_HOVER};
            color: {cls.TEXT_PRIMARY};
        }}
        QMenuBar::item:pressed {{
            background-color: {cls.BG_ACTIVE};
        }}

        QMenu {{
            background-color: {cls.BG_TOOLBAR};
            color: {cls.TEXT_PRIMARY};
            border: 1px solid {cls.BORDER_SUBTLE};
            border-radius: 6px;
            padding: 4px;
            font-size: 12px;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {cls.ACCENT};
            color: #ffffff;
        }}
        QMenu::item:disabled {{
            color: {cls.TEXT_MUTED};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {cls.BORDER_SUBTLE};
            margin: 4px 6px;
        }}

        /* Tooltips */
        QToolTip {{
            background-color: #161719;
            color: #ffffff;
            border: 1px solid #3c3f44;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
        }}
        """
