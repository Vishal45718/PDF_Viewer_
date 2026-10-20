"""
Organize Pages Dialog for PaperView.
Provides a modern visual thumbnail workspace for selecting, rotating,
reordering (drag-and-drop or buttons), duplicating, deleting, and extracting pages.
"""

from pathlib import Path
from typing import Dict, List, Optional
import pymupdf

from PySide6.QtCore import QByteArray, QPoint, QSize, Qt, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from paperview.document import DocumentError, DocumentManager
from paperview.icons import get_icon
from paperview.theme import Theme


class PageThumbnailItem(QListWidgetItem):
    """ListWidgetItem carrying metadata for an organized page."""

    def __init__(
        self,
        source_index: int,
        display_label: str,
        base_pixmap: QPixmap,
        initial_rotation: int = 0,
    ) -> None:
        super().__init__()
        self.source_index = source_index
        self.rotation_delta = 0  # relative to initial_rotation
        self.initial_rotation = initial_rotation
        self.base_pixmap = base_pixmap
        self.display_label = display_label
        self._update_appearance()

    @property
    def current_rotation(self) -> int:
        return (self.initial_rotation + self.rotation_delta) % 360

    def rotate(self, delta: int) -> None:
        self.rotation_delta = (self.rotation_delta + delta) % 360
        self._update_appearance()

    def _update_appearance(self) -> None:
        # Rotate pixmap if needed
        if self.current_rotation != self.initial_rotation:
            transform = QTransform().rotate(self.rotation_delta)
            pix = self.base_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        else:
            pix = self.base_pixmap

        self.setIcon(QIcon(pix))
        rot_badge = f" ({self.current_rotation}°)" if self.current_rotation != 0 else ""
        self.setText(f"{self.display_label}{rot_badge}")
        self.setToolTip(f"Original: Page {self.source_index + 1}\nRotation: {self.current_rotation}°")


class OrganizePagesDialog(QDialog):
    """
    Dialog for visually reorganizing, rotating, reordering, deleting,
    duplicating, and extracting PDF pages.
    """

    pages_applied = Signal()

    def __init__(self, doc_mgr: DocumentManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.doc_mgr = doc_mgr
        doc_name = doc_mgr.file_path.name if doc_mgr.file_path else "Untitled"
        self.setWindowTitle(f"Organize Pages — {doc_name}")
        self.resize(1000, 720)
        self.setMinimumSize(750, 520)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_WINDOW};
                color: {Theme.TEXT_PRIMARY};
            }}
            QListWidget {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 12px;
                color: {Theme.TEXT_PRIMARY};
            }}
            QListWidget::item {{
                background-color: {Theme.BG_WINDOW};
                border: 2px solid transparent;
                border-radius: 6px;
                padding: 6px;
                margin: 4px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 12px;
                text-align: center;
            }}
            QListWidget::item:hover {{
                border-color: {Theme.BORDER_INPUT};
                background-color: #2a2d33;
            }}
            QListWidget::item:selected {{
                border-color: {Theme.ACCENT};
                background-color: #1e3a5f;
                color: #ffffff;
            }}
            QToolBar {{
                background-color: {Theme.BG_TOOLBAR};
                border-bottom: 1px solid {Theme.BORDER_SUBTLE};
                spacing: 6px;
                padding: 6px 10px;
            }}
            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 12px;
                padding: 4px 8px;
            }}
            QToolButton:hover {{
                background-color: {Theme.BG_HOVER};
                border-color: {Theme.BORDER_SUBTLE};
            }}
            QToolButton:pressed {{
                background-color: {Theme.BG_ACTIVE};
            }}
            QPushButton {{
                background-color: {Theme.BG_TOOLBAR};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_HOVER};
                border-color: {Theme.BORDER_FOCUS};
            }}
            QPushButton#btn_apply {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                color: #ffffff;
                font-weight: 600;
            }}
            QPushButton#btn_apply:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main List Widget
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(130, 170))
        self.list_widget.setGridSize(QSize(160, 215))
        self.list_widget.setSpacing(12)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Snap)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

        # 1. Header Toolbar
        self._create_toolbar()
        layout.addWidget(self.toolbar)

        # 2. Main List Container
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(14, 14, 14, 14)
        list_layout.addWidget(self.list_widget)
        layout.addWidget(list_container, 1)

        # 3. Footer Bar
        self._create_footer()
        layout.addWidget(self.footer)

        # Populate thumbnails
        self._populate_pages()

    def _create_toolbar(self) -> None:
        self.toolbar = QToolBar("Organize Actions", self)
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(16, 16))

        # Rotate CW
        self.btn_rotate_cw = QToolButton()
        self.btn_rotate_cw.setIcon(get_icon("rotate_cw"))
        self.btn_rotate_cw.setText("Rotate CW")
        self.btn_rotate_cw.setToolTip("Rotate Selected Pages Clockwise 90° (Ctrl+R)")
        self.btn_rotate_cw.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_rotate_cw.clicked.connect(lambda: self.rotate_selected(90))
        self.toolbar.addWidget(self.btn_rotate_cw)

        # Rotate CCW
        self.btn_rotate_ccw = QToolButton()
        self.btn_rotate_ccw.setIcon(get_icon("rotate_ccw"))
        self.btn_rotate_ccw.setText("Rotate CCW")
        self.btn_rotate_ccw.setToolTip("Rotate Selected Pages Counterclockwise 90° (Ctrl+Shift+R)")
        self.btn_rotate_ccw.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_rotate_ccw.clicked.connect(lambda: self.rotate_selected(-90))
        self.toolbar.addWidget(self.btn_rotate_ccw)

        self._add_divider()

        # Move Left
        self.btn_move_left = QToolButton()
        self.btn_move_left.setIcon(get_icon("move_left"))
        self.btn_move_left.setText("Move Left")
        self.btn_move_left.setToolTip("Move Selected Page Earlier")
        self.btn_move_left.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_move_left.clicked.connect(self.move_selected_left)
        self.toolbar.addWidget(self.btn_move_left)

        # Move Right
        self.btn_move_right = QToolButton()
        self.btn_move_right.setIcon(get_icon("move_right"))
        self.btn_move_right.setText("Move Right")
        self.btn_move_right.setToolTip("Move Selected Page Later")
        self.btn_move_right.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_move_right.clicked.connect(self.move_selected_right)
        self.toolbar.addWidget(self.btn_move_right)

        self._add_divider()

        # Duplicate
        self.btn_duplicate = QToolButton()
        self.btn_duplicate.setIcon(get_icon("duplicate"))
        self.btn_duplicate.setText("Duplicate")
        self.btn_duplicate.setToolTip("Duplicate Selected Pages")
        self.btn_duplicate.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_duplicate.clicked.connect(self.duplicate_selected)
        self.toolbar.addWidget(self.btn_duplicate)

        # Delete
        self.btn_delete = QToolButton()
        self.btn_delete.setIcon(get_icon("delete"))
        self.btn_delete.setText("Delete")
        self.btn_delete.setToolTip("Delete Selected Pages (Delete)")
        self.btn_delete.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.toolbar.addWidget(self.btn_delete)

        self._add_divider()

        # Extract
        self.btn_extract = QToolButton()
        self.btn_extract.setIcon(get_icon("extract"))
        self.btn_extract.setText("Extract...")
        self.btn_extract.setToolTip("Extract Selected Pages into a New PDF Document")
        self.btn_extract.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_extract.clicked.connect(self.extract_selected)
        self.toolbar.addWidget(self.btn_extract)

        # Spacer to right-align selection helpers
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy().Expanding,
            spacer.sizePolicy().verticalPolicy().Preferred,
        )
        self.toolbar.addWidget(spacer)

        # Select All
        btn_sel_all = QToolButton()
        btn_sel_all.setText("Select All")
        btn_sel_all.setToolTip("Select All Pages (Ctrl+A)")
        btn_sel_all.clicked.connect(self.list_widget.selectAll)
        self.toolbar.addWidget(btn_sel_all)

        # Clear Selection
        btn_clear_sel = QToolButton()
        btn_clear_sel.setText("Deselect")
        btn_clear_sel.setToolTip("Clear Selection")
        btn_clear_sel.clicked.connect(self.list_widget.clearSelection)
        self.toolbar.addWidget(btn_clear_sel)

    def _add_divider(self) -> None:
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        divider.setStyleSheet(f"color: {Theme.BORDER_SUBTLE}; margin: 2px 6px;")
        divider.setFixedHeight(20)
        self.toolbar.addWidget(divider)

    def _create_footer(self) -> None:
        self.footer = QWidget()
        self.footer.setStyleSheet(f"""
            QWidget {{
                background-color: {Theme.BG_TOOLBAR};
                border-top: 1px solid {Theme.BORDER_SUBTLE};
            }}
        """)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)

        self.status_label = QLabel("Loading pages...")
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 13px;")
        footer_layout.addWidget(self.status_label)

        footer_layout.addStretch(1)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        self.btn_apply = QPushButton("Apply Changes")
        self.btn_apply.setObjectName("btn_apply")
        self.btn_apply.clicked.connect(self.apply_changes)
        footer_layout.addWidget(self.btn_apply)

    def _populate_pages(self) -> None:
        """Renders thumbnails for all pages and populates the list widget."""
        self.list_widget.clear()
        if not self.doc_mgr.is_open or self.doc_mgr.doc is None:
            self.status_label.setText("No document loaded.")
            return

        total = self.doc_mgr.page_count
        for i in range(total):
            page = self.doc_mgr.doc[i]
            # Render a low-dpi thumbnail (e.g. 0.25 scale)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(0.25, 0.25), alpha=False)
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            item = PageThumbnailItem(
                source_index=i,
                display_label=f"Page {i + 1}",
                base_pixmap=pixmap,
                initial_rotation=page.rotation,
            )
            self.list_widget.addItem(item)

        self._renumber_labels()
        self._update_status()

    def _on_selection_changed(self) -> None:
        self._update_status()

    def _update_status(self) -> None:
        total = self.list_widget.count()
        selected_count = len(self.list_widget.selectedItems())
        if selected_count == 0:
            self.status_label.setText(f"Total: {total} pages  (No pages selected)")
        elif selected_count == 1:
            idx = self.list_widget.row(self.list_widget.selectedItems()[0]) + 1
            self.status_label.setText(f"Total: {total} pages  |  Page {idx} selected")
        else:
            self.status_label.setText(f"Total: {total} pages  |  {selected_count} pages selected")

        has_sel = selected_count > 0
        self.btn_rotate_cw.setEnabled(has_sel)
        self.btn_rotate_ccw.setEnabled(has_sel)
        self.btn_move_left.setEnabled(has_sel)
        self.btn_move_right.setEnabled(has_sel)
        self.btn_duplicate.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_extract.setEnabled(has_sel)

    def _renumber_labels(self) -> None:
        """Updates display text to reflect current position in order."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if isinstance(item, PageThumbnailItem):
                item.display_label = f"Page {i + 1}"
                item._update_appearance()

    # --- Actions ---

    def rotate_selected(self, delta: int) -> None:
        selected = self.list_widget.selectedItems()
        for item in selected:
            if isinstance(item, PageThumbnailItem):
                item.rotate(delta)

    def move_selected_left(self) -> None:
        selected_rows = sorted([self.list_widget.row(it) for it in self.list_widget.selectedItems()])
        if not selected_rows or selected_rows[0] == 0:
            return  # already at beginning

        for row in selected_rows:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            item.setSelected(True)

        self._renumber_labels()
        self._update_status()

    def move_selected_right(self) -> None:
        selected_rows = sorted(
            [self.list_widget.row(it) for it in self.list_widget.selectedItems()],
            reverse=True,
        )
        if not selected_rows or selected_rows[0] >= self.list_widget.count() - 1:
            return  # already at end

        for row in selected_rows:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            item.setSelected(True)

        self._renumber_labels()
        self._update_status()

    def duplicate_selected(self) -> None:
        selected = list(self.list_widget.selectedItems())
        if not selected:
            return

        for it in selected:
            if isinstance(it, PageThumbnailItem):
                curr_row = self.list_widget.row(it)
                new_item = PageThumbnailItem(
                    source_index=it.source_index,
                    display_label=it.display_label,
                    base_pixmap=it.base_pixmap,
                    initial_rotation=it.initial_rotation,
                )
                new_item.rotation_delta = it.rotation_delta
                new_item._update_appearance()
                self.list_widget.insertItem(curr_row + 1, new_item)

        self._renumber_labels()
        self._update_status()

    def delete_selected(self) -> None:
        selected = list(self.list_widget.selectedItems())
        if not selected:
            return

        total = self.list_widget.count()
        if len(selected) >= total:
            QMessageBox.warning(
                self,
                "Cannot Delete All Pages",
                "A document must contain at least one page.\nYou cannot delete all pages.",
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete {len(selected)} selected page(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        for it in selected:
            row = self.list_widget.row(it)
            self.list_widget.takeItem(row)

        self._renumber_labels()
        self._update_status()

    def extract_selected(self) -> None:
        selected = list(self.list_widget.selectedItems())
        if not selected:
            QMessageBox.information(self, "No Pages Selected", "Please select one or more pages to extract.")
            return

        curr_path = self.doc_mgr.file_path
        default_name = f"{curr_path.stem}_extracted.pdf" if curr_path else "extracted_pages.pdf"
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Extract Pages to PDF",
            str(Path.home() / "Desktop" / default_name),
            "PDF Files (*.pdf)",
        )
        if not dest:
            return

        dest_path = Path(dest).resolve()
        if curr_path and dest_path == curr_path.resolve():
            QMessageBox.warning(
                self,
                "Invalid Destination",
                "Extraction cannot overwrite the active original file.\nPlease specify a different filename.",
            )
            return

        # Extract according to the current order of selected items in the list
        source_indices = []
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if it in selected and isinstance(it, PageThumbnailItem):
                source_indices.append(it.source_index)

        try:
            saved = self.doc_mgr.extract_pages(source_indices, dest_path)
            QMessageBox.information(
                self,
                "Pages Extracted",
                f"Successfully extracted {len(source_indices)} pages to:\n{saved}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Extraction Failed", f"Could not extract pages:\n{e}")

    def apply_changes(self) -> None:
        """
        Gathers final page structure and applies it to DocumentManager.
        """
        count = self.list_widget.count()
        if count == 0:
            QMessageBox.warning(self, "Empty Document", "Document must contain at least one page.")
            return

        page_specs: List[Dict[str, int]] = []
        for i in range(count):
            item = self.list_widget.item(i)
            if isinstance(item, PageThumbnailItem):
                page_specs.append({
                    "source_index": item.source_index,
                    "rotation_delta": item.rotation_delta,
                })

        try:
            self.doc_mgr.apply_page_structure(page_specs)
            self.pages_applied.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error Applying Changes", f"Could not reorganize pages:\n{e}")

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected()
        elif event.key() == Qt.Key.Key_R and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.rotate_selected(90)
        elif event.key() == Qt.Key.Key_R and event.modifiers() == (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            self.rotate_selected(-90)
        else:
            super().keyPressEvent(event)
