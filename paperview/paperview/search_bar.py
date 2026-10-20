"""
Search Bar Widget for PaperView.
Provides a modern docked search toolbar with match counters, navigation,
and case-sensitivity options.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QWidget,
)
from paperview.icons import get_icon
from paperview.theme import Theme


class SearchBar(QFrame):
    """
    Search bar overlay docked above the document workspace.
    """
    search_requested = Signal(str, bool)  # query, case_sensitive
    next_match_requested = Signal()
    prev_match_requested = Signal()
    closed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.BG_TOOLBAR};
                border-bottom: 1px solid {Theme.BORDER_SUBTLE};
                padding: 4px 10px;
            }}
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                padding: 4px 10px;
                font-size: 13px;
                min-width: 240px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.BORDER_FOCUS};
            }}
            QToolButton {{
                background-color: transparent;
                color: {Theme.TEXT_PRIMARY};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 500;
            }}
            QToolButton:hover {{
                background-color: {Theme.BG_HOVER};
                border: 1px solid {Theme.BORDER_SUBTLE};
            }}
            QToolButton:pressed {{
                background-color: {Theme.BG_ACTIVE};
            }}
            QCheckBox {{
                color: {Theme.TEXT_SECONDARY};
                font-size: 12px;
                margin-left: 4px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid {Theme.BORDER_INPUT};
                background-color: {Theme.BG_INPUT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
            }}
            QLabel {{
                color: {Theme.TEXT_SECONDARY};
                font-size: 12px;
                padding: 0 6px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Search Query Input Field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Find in document... (Enter to search)")
        self.input_field.returnPressed.connect(self._on_search_triggered)
        layout.addWidget(self.input_field)

        # Match Case Option
        self.case_box = QCheckBox("Match Case")
        self.case_box.toggled.connect(self._on_case_toggled)
        layout.addWidget(self.case_box)

        # Match Status Count
        self.count_label = QLabel("0 matches")
        layout.addWidget(self.count_label)

        # Previous Match Button
        self.prev_btn = QToolButton()
        self.prev_btn.setIcon(get_icon("chevron_up", 18))
        self.prev_btn.setText(" Prev")
        self.prev_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.prev_btn.setToolTip("Previous match (Shift+Enter)")
        self.prev_btn.clicked.connect(self.prev_match_requested.emit)
        layout.addWidget(self.prev_btn)

        # Next Match Button
        self.next_btn = QToolButton()
        self.next_btn.setIcon(get_icon("chevron_down", 18))
        self.next_btn.setText(" Next")
        self.next_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.next_btn.setToolTip("Next match (Enter)")
        self.next_btn.clicked.connect(self._on_next_clicked)
        layout.addWidget(self.next_btn)

        layout.addStretch()

        # Close Search Button
        self.close_btn = QToolButton()
        self.close_btn.setIcon(get_icon("close", 18))
        self.close_btn.setToolTip("Close search (Esc)")
        self.close_btn.clicked.connect(self.hide_bar)
        layout.addWidget(self.close_btn)

        # Esc shortcut inside input
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self.hide_bar)

    def show_and_focus(self) -> None:
        self.show()
        self.input_field.setFocus()
        self.input_field.selectAll()

    def hide_bar(self) -> None:
        self.hide()
        self.closed.emit()

    def set_match_status(self, current: int, total: int) -> None:
        if total == 0:
            self.count_label.setText("No matches found")
            self.count_label.setStyleSheet("color: #f28b82; font-weight: 500;")
        else:
            self.count_label.setText(f"{current} of {total} matches")
            self.count_label.setStyleSheet("color: #81c784; font-weight: 500;")

    def set_searching_status(self) -> None:
        self.count_label.setText("Searching document...")
        self.count_label.setStyleSheet("color: #fdd663; font-weight: 500;")

    def _on_search_triggered(self) -> None:
        q = self.input_field.text()
        if q:
            self.search_requested.emit(q, self.case_box.isChecked())

    def _on_case_toggled(self, checked: bool) -> None:
        q = self.input_field.text()
        if q:
            self.search_requested.emit(q, checked)

    def _on_next_clicked(self) -> None:
        self.next_match_requested.emit()
