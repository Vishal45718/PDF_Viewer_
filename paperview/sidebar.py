"""
Sidebar Component for PaperView.
Provides a refined Page Thumbnails strip and hierarchical Bookmarks/Outline tree.
"""

from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from paperview.theme import Theme


class ThumbnailItemWidget(QWidget):
    """
    Individual thumbnail card inside the sidebar page list.
    Displays crisp white page preview, drop shadow, and clean selection border.
    """

    def __init__(self, page_index: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.page_index = page_index
        self.is_selected: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Thumbnail Image Container
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(130, 180)
        self.update_selection_style(False)

        # Page Number Label
        self.num_label = QLabel(f"Page {page_index + 1}")
        self.num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.num_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; font-weight: 500;")

        layout.addWidget(self.image_label)
        layout.addWidget(self.num_label)

    def set_thumbnail(self, qimage: QImage) -> None:
        dpr = float(self.devicePixelRatioF()) if hasattr(self, "devicePixelRatioF") else float(self.devicePixelRatio())
        target_size = self.image_label.size() * dpr
        scaled = qimage.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if dpr != 1.0:
            scaled.setDevicePixelRatio(dpr)
        self.image_label.setPixmap(QPixmap.fromImage(scaled))

    def update_selection_style(self, selected: bool) -> None:
        self.is_selected = selected
        if selected:
            self.image_label.setStyleSheet(f"""
                QLabel {{
                    background-color: #ffffff;
                    border: 2px solid {Theme.ACCENT};
                    border-radius: 4px;
                }}
            """)
            if hasattr(self, "num_label"):
                self.num_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 11px; font-weight: 600;")
        else:
            self.image_label.setStyleSheet(f"""
                QLabel {{
                    background-color: #ffffff;
                    border: 1px solid #3c4046;
                    border-radius: 3px;
                }}
            """)
            if hasattr(self, "num_label"):
                self.num_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; font-weight: 500;")


class Sidebar(QWidget):
    """
    Left sidebar containing Pages (thumbnails) and Outline (TOC) tabs.
    """
    page_selected = Signal(int)  # 0-indexed page to navigate to

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_SIDEBAR};
                color: {Theme.TEXT_PRIMARY};
            }}
            QTabWidget::pane {{
                border: none;
                background-color: {Theme.BG_SIDEBAR};
            }}
            QTabBar::tab {{
                background-color: {Theme.BG_WINDOW};
                color: {Theme.TEXT_SECONDARY};
                padding: 7px 18px;
                border: none;
                font-weight: 500;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background-color: {Theme.BG_SIDEBAR};
                color: {Theme.TEXT_PRIMARY};
                border-bottom: 2px solid {Theme.ACCENT};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #272a2e;
                color: #d0d4dc;
            }}
            QListWidget {{
                background-color: {Theme.BG_SIDEBAR};
                border: none;
                padding: 6px 2px;
                outline: none;
            }}
            QListWidget::item {{
                border-radius: 6px;
                margin: 4px 6px;
                border: 1px solid transparent;
                background-color: transparent;
            }}
            QListWidget::item:hover {{
                background-color: #2c3036;
            }}
            QListWidget::item:selected {{
                background-color: #253147;
                border: 1px solid #355385;
            }}
            QTreeWidget {{
                background-color: {Theme.BG_SIDEBAR};
                border: none;
                color: {Theme.TEXT_PRIMARY};
                font-size: 12px;
                padding: 4px;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 5px 4px;
                border-radius: 4px;
            }}
            QTreeWidget::item:hover {{
                background-color: #2c3036;
            }}
            QTreeWidget::item:selected {{
                background-color: #253147;
                color: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Tab 1: Thumbnails List
        self.thumb_list = QListWidget()
        self.thumb_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.thumb_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.thumb_list.itemClicked.connect(self._on_thumb_clicked)
        self.tab_widget.addTab(self.thumb_list, "Pages")

        # Tab 2: Bookmarks / Outline Tree
        self.toc_tree = QTreeWidget()
        self.toc_tree.setHeaderHidden(True)
        self.toc_tree.itemClicked.connect(self._on_toc_clicked)
        self.tab_widget.addTab(self.toc_tree, "Outline")

        self.thumbnail_widgets: List[ThumbnailItemWidget] = []
        self._current_selected_page: int = -1

    def set_page_count(self, count: int) -> None:
        """Sets up empty placeholder items in the thumbnail list."""
        self.thumb_list.clear()
        self.thumbnail_widgets.clear()
        self._current_selected_page = -1

        for idx in range(count):
            item = QListWidgetItem(self.thumb_list)
            item.setSizeHint(QSize(190, 220))
            w = ThumbnailItemWidget(idx)
            self.thumb_list.addItem(item)
            self.thumb_list.setItemWidget(item, w)
            self.thumbnail_widgets.append(w)

    def set_thumbnail_image(self, page_index: int, qimage: QImage) -> None:
        if 0 <= page_index < len(self.thumbnail_widgets):
            self.thumbnail_widgets[page_index].set_thumbnail(qimage)

    def request_thumbnail_range(self, start_idx: int, end_idx: int) -> List[int]:
        """Returns page indices that still need thumbnails."""
        needed = []
        for i in range(max(0, start_idx), min(len(self.thumbnail_widgets), end_idx + 1)):
            pm = self.thumbnail_widgets[i].image_label.pixmap()
            if pm is None or pm.isNull():
                needed.append(i)
        return needed

    def select_thumbnail(self, page_index: int) -> None:
        if 0 <= page_index < self.thumb_list.count():
            # Update card selection styles
            if 0 <= self._current_selected_page < len(self.thumbnail_widgets):
                self.thumbnail_widgets[self._current_selected_page].update_selection_style(False)
            self._current_selected_page = page_index
            if page_index < len(self.thumbnail_widgets):
                self.thumbnail_widgets[page_index].update_selection_style(True)

            self.thumb_list.blockSignals(True)
            self.thumb_list.setCurrentRow(page_index)
            # Ensure visible without erratic jumping
            item = self.thumb_list.item(page_index)
            if item:
                self.thumb_list.scrollToItem(item, QListWidget.ScrollHint.EnsureVisible)
            self.thumb_list.blockSignals(False)

    def set_toc(self, toc: List[List[Any]]) -> None:
        """
        Populates outline tree from TOC list:
        [[level, title, page_1_indexed, ...], ...]
        """
        self.toc_tree.clear()
        if not toc:
            item = QTreeWidgetItem(self.toc_tree, ["No outline entries found"])
            item.setDisabled(True)
            return

        level_stack: List[Tuple[int, QTreeWidgetItem]] = []

        for entry in toc:
            level = entry[0]
            title = entry[1]
            page_1_indexed = entry[2] if len(entry) > 2 else 1
            target_page_0 = max(0, page_1_indexed - 1)

            tree_item = QTreeWidgetItem([title])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, target_page_0)
            tree_item.setToolTip(0, f"{title} (Page {page_1_indexed})")

            while level_stack and level_stack[-1][0] >= level:
                level_stack.pop()

            if not level_stack:
                self.toc_tree.addTopLevelItem(tree_item)
            else:
                level_stack[-1][1].addChild(tree_item)

            level_stack.append((level, tree_item))

        self.toc_tree.expandAll()

    @Slot(QListWidgetItem)
    def _on_thumb_clicked(self, item: QListWidgetItem) -> None:
        idx = self.thumb_list.row(item)
        self.page_selected.emit(idx)

    @Slot(QTreeWidgetItem, int)
    def _on_toc_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        page_idx = item.data(0, Qt.ItemDataRole.UserRole)
        if page_idx is not None and isinstance(page_idx, int):
            self.page_selected.emit(page_idx)
