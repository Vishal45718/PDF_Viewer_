"""
Document Operation Dialogs for PaperView:
1. MergePDFsDialog: Combines multiple PDFs in chosen order with validation & password support.
2. SplitPDFDialog: Splits PDF by page ranges or individual pages with filename previews.
3. WatermarkDialog: Adds configurable text watermarks with interactive live preview.
4. OptimizePDFDialog: Compresses structure, deflates streams, downsamples images, and reports metrics.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pymupdf

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from paperview.dialogs import PasswordDialog
from paperview.document import (
    DocumentError,
    DocumentManager,
    InvalidPasswordError,
    PasswordRequiredError,
)
from paperview.icons import get_icon
from paperview.theme import Theme


# ============================================================================
# 1. Merge PDFs Dialog
# ============================================================================

class MergePDFsDialog(QDialog):
    """Allows choosing multiple PDF files, reordering them, and merging into one output PDF."""

    merged_file_ready = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Merge PDF Documents")
        self.resize(650, 500)
        self.setMinimumSize(500, 380)
        self._apply_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QLabel("Merge Multiple PDF Documents")
        header.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        info_lbl = QLabel(
            "Select and order the PDF files you want to combine. "
            "Bookmarks and links are preserved where supported."
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(info_lbl)

        # File List and Reorder Buttons
        list_container = QWidget()
        list_layout = QHBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(10)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        list_layout.addWidget(self.file_list, 1)

        btn_box = QVBoxLayout()
        btn_box.setSpacing(8)

        btn_add = QPushButton("Add Files...")
        btn_add.clicked.connect(self._add_files)
        btn_box.addWidget(btn_add)

        btn_remove = QPushButton("Remove")
        btn_remove.clicked.connect(self._remove_selected)
        btn_box.addWidget(btn_remove)

        btn_up = QPushButton("Move Up")
        btn_up.clicked.connect(self._move_up)
        btn_box.addWidget(btn_up)

        btn_down = QPushButton("Move Down")
        btn_down.clicked.connect(self._move_down)
        btn_box.addWidget(btn_down)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self.file_list.clear)
        btn_box.addWidget(btn_clear)

        btn_box.addStretch(1)
        list_layout.addLayout(btn_box)
        layout.addWidget(list_container, 1)

        # Destination Selection
        dest_card = QFrame()
        dest_card.setObjectName("card")
        dest_layout = QHBoxLayout(dest_card)
        dest_layout.setContentsMargins(10, 8, 10, 8)
        dest_layout.setSpacing(8)

        lbl_dest = QLabel("Output Destination:")
        lbl_dest.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        dest_layout.addWidget(lbl_dest)

        default_out = str(Path.home() / "Desktop" / "merged_document.pdf")
        self.dest_edit = QLineEdit(default_out)
        dest_layout.addWidget(self.dest_edit, 1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_destination)
        dest_layout.addWidget(btn_browse)

        layout.addWidget(dest_card)

        # Checkbox: Open immediately
        self.chk_open_merged = QCheckBox("Open merged document in PaperView when finished")
        self.chk_open_merged.setChecked(True)
        self.chk_open_merged.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
        layout.addWidget(self.chk_open_merged)

        # Bottom Button Box
        buttons = QHBoxLayout()
        buttons.addStretch(1)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        self.btn_merge = QPushButton("Merge Documents")
        self.btn_merge.setObjectName("btn_accent")
        self.btn_merge.clicked.connect(self._perform_merge)
        buttons.addWidget(self.btn_merge)

        layout.addLayout(buttons)

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_WINDOW};
                color: {Theme.TEXT_PRIMARY};
            }}
            QListWidget {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 6px;
                border-radius: 3px;
            }}
            QListWidget::item:selected {{
                background-color: {Theme.ACCENT};
                color: #ffffff;
            }}
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: #ffffff;
                padding: 6px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.BORDER_FOCUS};
            }}
            QFrame#card {{
                background-color: {Theme.BG_TOOLBAR};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: {Theme.BG_TOOLBAR};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_HOVER};
                border-color: {Theme.BORDER_FOCUS};
            }}
            QPushButton#btn_accent {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                color: #ffffff;
                font-weight: 600;
            }}
            QPushButton#btn_accent:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
        """)

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF Files to Merge",
            str(Path.home() / "Desktop"),
            "PDF Files (*.pdf)",
        )
        for f in files:
            p = Path(f).resolve()
            # Avoid duplicate visual entries
            existing = [self.file_list.item(i).toolTip() for i in range(self.file_list.count())]
            if str(p) not in existing:
                item = QListWidgetItem(f"{p.name}  ({p.parent})")
                item.setToolTip(str(p))
                self.file_list.addItem(item)

    def _remove_selected(self) -> None:
        row = self.file_list.currentRow()
        if row >= 0:
            self.file_list.takeItem(row)

    def _move_up(self) -> None:
        row = self.file_list.currentRow()
        if row > 0:
            item = self.file_list.takeItem(row)
            self.file_list.insertItem(row - 1, item)
            self.file_list.setCurrentRow(row - 1)

    def _move_down(self) -> None:
        row = self.file_list.currentRow()
        if 0 <= row < self.file_list.count() - 1:
            item = self.file_list.takeItem(row)
            self.file_list.insertItem(row + 1, item)
            self.file_list.setCurrentRow(row + 1)

    def _browse_destination(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Merge Destination",
            self.dest_edit.text(),
            "PDF Files (*.pdf)",
        )
        if dest:
            self.dest_edit.setText(dest)

    def _perform_merge(self) -> None:
        count = self.file_list.count()
        if count < 2:
            QMessageBox.warning(
                self,
                "Insufficient Files",
                "Please add at least two PDF files to merge into a single document.",
            )
            return

        dest_str = self.dest_edit.text().strip()
        if not dest_str:
            QMessageBox.warning(self, "Invalid Destination", "Please specify a valid destination file path.")
            return

        dest_path = Path(dest_str).resolve()
        file_paths = [Path(self.file_list.item(i).toolTip()) for i in range(count)]

        for p in file_paths:
            if dest_path == p:
                QMessageBox.warning(
                    self,
                    "Destination Conflict",
                    f"Merge output cannot overwrite input file '{p.name}'.\nPlease specify a different output filename.",
                )
                return

        passwords: Dict[str, str] = {}
        # Pre-check encrypted files
        for p in file_paths:
            try:
                doc = pymupdf.open(str(p))
                if doc.is_encrypted and doc.needs_pass:
                    dlg = PasswordDialog(p.name, self)
                    if dlg.exec():
                        passwords[str(p)] = dlg.get_password()
                    else:
                        doc.close()
                        QMessageBox.information(self, "Merge Cancelled", f"Password required for {p.name}.")
                        return
                doc.close()
            except Exception as e:
                QMessageBox.critical(self, "File Error", f"Cannot open '{p.name}':\n{e}")
                return

        try:
            saved = DocumentManager.merge_pdfs(file_paths, dest_path, passwords=passwords)
            QMessageBox.information(
                self,
                "Merge Completed",
                f"Successfully merged {len(file_paths)} PDF documents into:\n{saved}",
            )
            if self.chk_open_merged.isChecked():
                self.merged_file_ready.emit(str(saved))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Merge Failed", f"An error occurred during merge:\n{e}")


# ============================================================================
# 2. Split PDF Dialog
# ============================================================================

class SplitPDFDialog(QDialog):
    """Allows splitting the active PDF by page ranges, single pages, or fixed page chunks."""

    def __init__(self, doc_mgr: DocumentManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.doc_mgr = doc_mgr
        doc_name = doc_mgr.file_path.name if doc_mgr.file_path else "Untitled"
        self.setWindowTitle(f"Split PDF — {doc_name}")
        self.resize(600, 480)
        self.setMinimumSize(480, 360)
        self._apply_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QLabel("Split PDF Document")
        header.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        # Mode Selection
        grp_mode = QGroupBox("Split Mode")
        grp_mode.setStyleSheet(f"""
            QGroupBox {{
                color: {Theme.TEXT_PRIMARY};
                font-weight: 600;
                font-size: 13px;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
        """)
        mode_layout = QVBoxLayout(grp_mode)
        mode_layout.setSpacing(8)

        self.rb_ranges = QRadioButton("Split by custom page ranges (e.g. '1-3, 4-5, 6-10')")
        self.rb_ranges.setChecked(True)
        self.rb_ranges.toggled.connect(self._on_mode_toggled)
        mode_layout.addWidget(self.rb_ranges)

        range_input_layout = QHBoxLayout()
        range_input_layout.setContentsMargins(20, 0, 0, 0)
        self.range_edit = QLineEdit("1-2")
        self.range_edit.setPlaceholderText("e.g. 1-3, 5, 7-10")
        self.range_edit.textChanged.connect(self._update_preview)
        range_input_layout.addWidget(self.range_edit)
        mode_layout.addLayout(range_input_layout)

        self.rb_single = QRadioButton("Extract all pages as individual separate PDFs (1 page per file)")
        self.rb_single.toggled.connect(self._on_mode_toggled)
        mode_layout.addWidget(self.rb_single)

        self.rb_chunks = QRadioButton("Split every N pages:")
        self.rb_chunks.toggled.connect(self._on_mode_toggled)
        chunk_layout = QHBoxLayout()
        chunk_layout.setContentsMargins(20, 0, 0, 0)
        chunk_layout.addWidget(self.rb_chunks)
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(1, max(1, self.doc_mgr.page_count))
        self.chunk_spin.setValue(1)
        self.chunk_spin.setEnabled(False)
        self.chunk_spin.valueChanged.connect(self._update_preview)
        chunk_layout.addWidget(self.chunk_spin)
        chunk_layout.addStretch(1)
        mode_layout.addLayout(chunk_layout)

        layout.addWidget(grp_mode)

        # Output Directory
        dest_card = QFrame()
        dest_card.setObjectName("card")
        dest_layout = QHBoxLayout(dest_card)
        dest_layout.setContentsMargins(10, 8, 10, 8)
        dest_layout.setSpacing(8)

        lbl_dir = QLabel("Save to Folder:")
        lbl_dir.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        dest_layout.addWidget(lbl_dir)

        default_dir = str(Path.home() / "Desktop")
        self.dir_edit = QLineEdit(default_dir)
        dest_layout.addWidget(self.dir_edit, 1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_directory)
        dest_layout.addWidget(btn_browse)

        layout.addWidget(dest_card)

        # Live Filename Preview
        preview_lbl = QLabel("Output Files Preview:")
        preview_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        layout.addWidget(preview_lbl)

        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setFixedHeight(85)
        self.preview_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
                color: {Theme.TEXT_MUTED};
                font-family: monospace;
                font-size: 12px;
                padding: 6px;
            }}
        """)
        layout.addWidget(self.preview_box)

        # Action Buttons
        buttons = QHBoxLayout()
        buttons.addStretch(1)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        self.btn_split = QPushButton("Split PDF")
        self.btn_split.setObjectName("btn_accent")
        self.btn_split.clicked.connect(self._perform_split)
        buttons.addWidget(self.btn_split)

        layout.addLayout(buttons)

        # Initial preview
        self._update_preview()

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_WINDOW};
                color: {Theme.TEXT_PRIMARY};
            }}
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: #ffffff;
                padding: 6px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {Theme.BORDER_FOCUS};
            }}
            QFrame#card {{
                background-color: {Theme.BG_TOOLBAR};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: {Theme.BG_TOOLBAR};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_HOVER};
                border-color: {Theme.BORDER_FOCUS};
            }}
            QPushButton#btn_accent {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                color: #ffffff;
                font-weight: 600;
            }}
            QPushButton#btn_accent:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
            QRadioButton {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 12px;
            }}
        """)

    def _on_mode_toggled(self) -> None:
        self.range_edit.setEnabled(self.rb_ranges.isChecked())
        self.chunk_spin.setEnabled(self.rb_chunks.isChecked())
        self._update_preview()

    def _browse_directory(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory for Split PDFs",
            self.dir_edit.text(),
        )
        if dir_path:
            self.dir_edit.setText(dir_path)

    def _get_computed_ranges(self) -> List[List[int]]:
        total = self.doc_mgr.page_count
        if self.rb_ranges.isChecked():
            txt = self.range_edit.text().strip()
            return DocumentManager.parse_page_ranges(txt, total)
        elif self.rb_single.isChecked():
            return [[i] for i in range(total)]
        elif self.rb_chunks.isChecked():
            step = max(1, self.chunk_spin.value())
            res = []
            for i in range(0, total, step):
                res.append(list(range(i, min(i + step, total))))
            return res
        return []

    def _update_preview(self) -> None:
        try:
            ranges = self._get_computed_ranges()
            base = self.doc_mgr.file_path.stem if self.doc_mgr.file_path else "split_doc"
            lines = []
            for r_idx, page_list in enumerate(ranges):
                if len(page_list) == 1:
                    fname = f"{base}_page_{page_list[0] + 1}.pdf"
                else:
                    fname = f"{base}_part_{r_idx + 1}_pages_{page_list[0] + 1}-{page_list[-1] + 1}.pdf"
                lines.append(f"• {fname}  ({len(page_list)} page{'s' if len(page_list) > 1 else ''})")

            self.preview_box.setText("\n".join(lines) if lines else "(No ranges specified)")
            self.preview_box.setStyleSheet("color: #d4d7dc; font-family: monospace; font-size: 12px;")
            self.btn_split.setEnabled(len(lines) > 0)
        except Exception as e:
            self.preview_box.setText(f"Invalid range: {e}")
            self.preview_box.setStyleSheet("color: #f28b82; font-family: monospace; font-size: 12px;")
            self.btn_split.setEnabled(False)

    def _perform_split(self) -> None:
        try:
            ranges = self._get_computed_ranges()
        except Exception as e:
            QMessageBox.warning(self, "Invalid Ranges", f"Please check the page range specification:\n{e}")
            return

        out_dir = Path(self.dir_edit.text().strip()).resolve()
        if not out_dir.is_dir():
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Directory Error", f"Could not create output directory:\n{e}")
                return

        try:
            created = self.doc_mgr.split_pdf(ranges, out_dir)
            QMessageBox.information(
                self,
                "Split Completed",
                f"Successfully created {len(created)} PDF file(s) in:\n{out_dir}",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Split Failed", f"Could not split PDF:\n{e}")


# ============================================================================
# 3. Watermark Dialog (with Live Interactive Preview)
# ============================================================================

class WatermarkPreviewWidget(QWidget):
    """Renders a thumbnail of the target page with a dynamic live preview of the watermark."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(220, 290)
        self.base_pixmap: Optional[QPixmap] = None
        self.text: str = "CONFIDENTIAL"
        self.fontsize: int = 40
        self.color: QColor = QColor(220, 50, 50)
        self.opacity: float = 0.3
        self.placement: str = "diagonal"

    def set_base_pixmap(self, pixmap: QPixmap) -> None:
        self.base_pixmap = pixmap
        self.update()

    def update_settings(
        self,
        text: str,
        fontsize: int,
        color: QColor,
        opacity: float,
        placement: str,
    ) -> None:
        self.text = text
        self.fontsize = fontsize
        self.color = color
        self.opacity = opacity
        self.placement = placement
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw card background
        painter.fillRect(self.rect(), QColor("#1e2024"))
        painter.setPen(QColor(Theme.BORDER_SUBTLE))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        if self.base_pixmap:
            # Scale thumbnail to fit within widget preserving aspect ratio
            scaled_pix = self.base_pixmap.scaled(
                self.width() - 16,
                self.height() - 16,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x_offset = (self.width() - scaled_pix.width()) // 2
            y_offset = (self.height() - scaled_pix.height()) // 2
            painter.drawPixmap(x_offset, y_offset, scaled_pix)

            # Draw Watermark text preview scaled proportionally
            if self.text.strip():
                scale_ratio = scaled_pix.width() / max(1.0, float(self.base_pixmap.width()))
                preview_font_size = max(8, int(self.fontsize * scale_ratio * 0.8))
                font = QFont("Helvetica", preview_font_size, QFont.Weight.Bold)
                painter.setFont(font)

                draw_color = QColor(self.color)
                draw_color.setAlphaF(max(0.05, min(1.0, self.opacity)))
                painter.setPen(draw_color)

                cx = x_offset + scaled_pix.width() / 2.0
                cy = y_offset + scaled_pix.height() / 2.0

                painter.save()
                if self.placement == "diagonal":
                    painter.translate(cx, cy)
                    painter.rotate(-45)
                    painter.drawText(QRectF(-120, -30, 240, 60), Qt.AlignmentFlag.AlignCenter, self.text)
                elif self.placement == "horizontal":
                    painter.translate(cx, cy)
                    painter.drawText(QRectF(-120, -30, 240, 60), Qt.AlignmentFlag.AlignCenter, self.text)
                elif self.placement == "header":
                    painter.drawText(
                        QRectF(x_offset, y_offset + 12, scaled_pix.width(), 40),
                        Qt.AlignmentFlag.AlignCenter,
                        self.text,
                    )
                elif self.placement == "footer":
                    painter.drawText(
                        QRectF(x_offset, y_offset + scaled_pix.height() - 36, scaled_pix.width(), 40),
                        Qt.AlignmentFlag.AlignCenter,
                        self.text,
                    )
                painter.restore()
        else:
            painter.setPen(QColor(Theme.TEXT_MUTED))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Preview")


class WatermarkDialog(QDialog):
    """Dialog for configuring and applying embedded text watermarks."""

    watermark_applied = Signal()

    def __init__(self, doc_mgr: DocumentManager, current_page: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.doc_mgr = doc_mgr
        self.current_page = current_page
        self.setWindowTitle("Add Watermark")
        self.resize(680, 500)
        self.setMinimumSize(560, 420)
        self._watermark_color = QColor(220, 50, 50)
        self._apply_theme()

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(18)

        # Left Column: Controls
        controls = QVBoxLayout()
        controls.setSpacing(12)

        header = QLabel("Watermark Configuration")
        header.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        header.setStyleSheet("color: #ffffff;")
        controls.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 1. Text input
        self.text_input = QLineEdit("CONFIDENTIAL")
        self.text_input.textChanged.connect(self._sync_preview)
        form.addRow("Text:", self.text_input)

        # 2. Font size
        size_layout = QHBoxLayout()
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(16, 120)
        self.size_slider.setValue(48)
        self.size_slider.valueChanged.connect(self._on_slider_size_changed)
        size_layout.addWidget(self.size_slider)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(16, 120)
        self.size_spin.setValue(48)
        self.size_spin.valueChanged.connect(self._on_spin_size_changed)
        size_layout.addWidget(self.size_spin)
        form.addRow("Font Size:", size_layout)

        # 3. Placement
        self.placement_combo = QComboBox()
        self.placement_combo.addItem("Diagonal Center (45°)", "diagonal")
        self.placement_combo.addItem("Horizontal Center", "horizontal")
        self.placement_combo.addItem("Top Header", "header")
        self.placement_combo.addItem("Bottom Footer", "footer")
        self.placement_combo.currentIndexChanged.connect(self._sync_preview)
        form.addRow("Placement:", self.placement_combo)

        # 4. Color Picker
        color_layout = QHBoxLayout()
        self.color_sample = QLabel()
        self.color_sample.setFixedSize(28, 24)
        self._update_color_sample()
        color_layout.addWidget(self.color_sample)

        btn_pick_color = QPushButton("Choose Color...")
        btn_pick_color.clicked.connect(self._pick_color)
        color_layout.addWidget(btn_pick_color)
        color_layout.addStretch(1)
        form.addRow("Color:", color_layout)

        # 5. Opacity Slider
        opacity_layout = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(30)
        self.opacity_slider.valueChanged.connect(self._sync_preview)
        opacity_layout.addWidget(self.opacity_slider)

        self.opacity_label = QLabel("30%")
        self.opacity_label.setFixedWidth(40)
        opacity_layout.addWidget(self.opacity_label)
        form.addRow("Opacity:", opacity_layout)

        # 6. Page selection
        self.pages_combo = QComboBox()
        self.pages_combo.addItem("All Pages", "all")
        self.pages_combo.addItem(f"Current Page Only (Page {current_page + 1})", "current")
        self.pages_combo.addItem("Custom Page Range", "range")
        self.pages_combo.currentIndexChanged.connect(self._on_pages_combo_changed)
        form.addRow("Pages:", self.pages_combo)

        self.custom_range_edit = QLineEdit("1-2")
        self.custom_range_edit.setPlaceholderText("e.g. 1-3, 5")
        self.custom_range_edit.hide()
        form.addRow("", self.custom_range_edit)

        controls.addLayout(form)
        controls.addStretch(1)

        # Bottom buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_apply = QPushButton("Apply Watermark")
        btn_apply.setObjectName("btn_accent")
        btn_apply.clicked.connect(self._perform_apply)
        btn_box.addWidget(btn_apply)

        controls.addLayout(btn_box)
        main_layout.addLayout(controls, 1)

        # Right Column: Live Interactive Preview
        preview_col = QVBoxLayout()
        preview_col.setSpacing(6)
        lbl_prev = QLabel("Live Preview:")
        lbl_prev.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        preview_col.addWidget(lbl_prev)

        self.preview_widget = WatermarkPreviewWidget()
        preview_col.addWidget(self.preview_widget)
        preview_col.addStretch(1)

        main_layout.addLayout(preview_col)

        # Load current page thumbnail for preview
        self._load_page_thumbnail()
        self._sync_preview()

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_WINDOW};
                color: {Theme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: #ffffff;
                padding: 5px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border-color: {Theme.BORDER_FOCUS};
            }}
            QPushButton {{
                background-color: {Theme.BG_TOOLBAR};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_HOVER};
                border-color: {Theme.BORDER_FOCUS};
            }}
            QPushButton#btn_accent {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                color: #ffffff;
                font-weight: 600;
            }}
            QPushButton#btn_accent:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
        """)

    def _load_page_thumbnail(self) -> None:
        if self.doc_mgr.is_open and self.doc_mgr.doc is not None:
            p_idx = max(0, min(self.current_page, self.doc_mgr.page_count - 1))
            page = self.doc_mgr.doc[p_idx]
            pix = page.get_pixmap(matrix=pymupdf.Matrix(0.35, 0.35), alpha=False)
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            self.preview_widget.set_base_pixmap(QPixmap.fromImage(qimg))

    def _update_color_sample(self) -> None:
        self.color_sample.setStyleSheet(
            f"background-color: {self._watermark_color.name()}; "
            f"border: 1px solid {Theme.BORDER_INPUT}; border-radius: 3px;"
        )

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(self._watermark_color, self, "Select Watermark Color")
        if c.isValid():
            self._watermark_color = c
            self._update_color_sample()
            self._sync_preview()

    def _on_slider_size_changed(self, val: int) -> None:
        self.size_spin.blockSignals(True)
        self.size_spin.setValue(val)
        self.size_spin.blockSignals(False)
        self._sync_preview()

    def _on_spin_size_changed(self, val: int) -> None:
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(val)
        self.size_slider.blockSignals(False)
        self._sync_preview()

    def _on_pages_combo_changed(self) -> None:
        is_range = self.pages_combo.currentData() == "range"
        self.custom_range_edit.setVisible(is_range)

    def _sync_preview(self) -> None:
        op = self.opacity_slider.value() / 100.0
        self.opacity_label.setText(f"{self.opacity_slider.value()}%")
        self.preview_widget.update_settings(
            text=self.text_input.text(),
            fontsize=self.size_spin.value(),
            color=self._watermark_color,
            opacity=op,
            placement=self.placement_combo.currentData(),
        )

    def _perform_apply(self) -> None:
        text = self.text_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Invalid Watermark", "Please provide watermark text.")
            return

        mode = self.pages_combo.currentData()
        target_pages: Optional[List[int]] = None

        if mode == "all":
            target_pages = None  # means all pages
        elif mode == "current":
            target_pages = [self.current_page]
        elif mode == "range":
            txt = self.custom_range_edit.text().strip()
            try:
                sub_ranges = DocumentManager.parse_page_ranges(txt, self.doc_mgr.page_count)
                flat_pages: List[int] = []
                for sr in sub_ranges:
                    flat_pages.extend(sr)
                target_pages = sorted(list(set(flat_pages)))
            except Exception as e:
                QMessageBox.warning(self, "Invalid Page Range", f"Could not parse page range:\n{e}")
                return

        color_tuple = (
            self._watermark_color.redF(),
            self._watermark_color.greenF(),
            self._watermark_color.blueF(),
        )
        op = self.opacity_slider.value() / 100.0
        placement = self.placement_combo.currentData()

        try:
            self.doc_mgr.apply_watermark(
                text=text,
                pages=target_pages,
                fontsize=float(self.size_spin.value()),
                color=color_tuple,
                opacity=op,
                placement=placement,
                overlay=True,
            )
            self.watermark_applied.emit()
            QMessageBox.information(
                self,
                "Watermark Added",
                "Watermark successfully applied to the document.\nRemember to Save Copy As to persist changes to disk.",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Watermark Failed", f"Could not embed watermark:\n{e}")


# ============================================================================
# 4. Optimize PDF Dialog
# ============================================================================

class OptimizePDFDialog(QDialog):
    """Allows selecting optimization options and produces an optimized output PDF."""

    optimized_file_ready = Signal(str)

    def __init__(self, doc_mgr: DocumentManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.doc_mgr = doc_mgr
        doc_name = doc_mgr.file_path.name if doc_mgr.file_path else "Untitled"
        self.setWindowTitle(f"Optimize PDF — {doc_name}")
        self.resize(580, 480)
        self.setMinimumSize(480, 360)
        self._apply_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QLabel("Optimize PDF File Size")
        header.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        # Options Container
        opt_group = QGroupBox("Optimization Methods")
        opt_group.setStyleSheet(f"""
            QGroupBox {{
                color: {Theme.TEXT_PRIMARY};
                font-weight: 600;
                font-size: 13px;
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                margin-top: 10px;
                padding: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
        """)
        opt_layout = QVBoxLayout(opt_group)
        opt_layout.setSpacing(10)

        # 1. Structural optimization
        self.chk_structural = QCheckBox("Safe Structural Compression && Garbage Collection (Recommended)")
        self.chk_structural.setChecked(True)
        opt_layout.addWidget(self.chk_structural)
        lbl_struct = QLabel("Removes orphaned PDF objects, deduplicates font streams, and compresses table cross-references.")
        lbl_struct.setWordWrap(True)
        lbl_struct.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; margin-left: 20px;")
        opt_layout.addWidget(lbl_struct)

        # 2. Stream deflation
        self.chk_deflate = QCheckBox("Compress Text and Vector Content Streams (Deflate)")
        self.chk_deflate.setChecked(True)
        opt_layout.addWidget(self.chk_deflate)

        # 3. Image recompression
        self.chk_images = QCheckBox("Recompress Embedded Raster Images")
        self.chk_images.toggled.connect(self._on_images_toggled)
        opt_layout.addWidget(self.chk_images)

        self.img_options_widget = QWidget()
        img_layout = QFormLayout(self.img_options_widget)
        img_layout.setContentsMargins(20, 0, 0, 0)
        img_layout.setSpacing(8)

        self.dpi_combo = QComboBox()
        self.dpi_combo.addItem("150 DPI (Balanced Quality / Size)", 150)
        self.dpi_combo.addItem("96 DPI (Screen / Mobile Viewing)", 96)
        self.dpi_combo.addItem("72 DPI (Minimum Size / Web)", 72)
        self.dpi_combo.addItem("200 DPI (High Resolution)", 200)
        img_layout.addRow("Max Resolution:", self.dpi_combo)

        quality_layout = QHBoxLayout()
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(40, 95)
        self.quality_slider.setValue(75)
        self.quality_slider.valueChanged.connect(lambda v: self.quality_lbl.setText(f"{v}%"))
        quality_layout.addWidget(self.quality_slider)

        self.quality_lbl = QLabel("75%")
        self.quality_lbl.setFixedWidth(35)
        quality_layout.addWidget(self.quality_lbl)
        img_layout.addRow("JPEG Quality:", quality_layout)

        self.img_options_widget.setEnabled(False)
        opt_layout.addWidget(self.img_options_widget)

        layout.addWidget(opt_group)

        # Realistic expectation warning
        warn_lbl = QLabel(
            "Note: Recompressing images reduces file size at the cost of visual fidelity. "
            "If your document contains predominantly vector text or already compressed streams, "
            "file size may not significantly decrease."
        )
        warn_lbl.setWordWrap(True)
        warn_lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(warn_lbl)

        # Destination Selection
        dest_card = QFrame()
        dest_card.setObjectName("card")
        dest_layout = QHBoxLayout(dest_card)
        dest_layout.setContentsMargins(10, 8, 10, 8)
        dest_layout.setSpacing(8)

        lbl_dest = QLabel("Save Optimized Copy To:")
        lbl_dest.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
        dest_layout.addWidget(lbl_dest)

        stem = self.doc_mgr.file_path.stem if self.doc_mgr.file_path else "document"
        default_out = str(Path.home() / "Desktop" / f"{stem}_optimized.pdf")
        self.dest_edit = QLineEdit(default_out)
        dest_layout.addWidget(self.dest_edit, 1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_destination)
        dest_layout.addWidget(btn_browse)

        layout.addWidget(dest_card)

        # Action Buttons
        buttons = QHBoxLayout()
        buttons.addStretch(1)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        self.btn_optimize = QPushButton("Optimize PDF")
        self.btn_optimize.setObjectName("btn_accent")
        self.btn_optimize.clicked.connect(self._perform_optimize)
        buttons.addWidget(self.btn_optimize)

        layout.addLayout(buttons)

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_WINDOW};
                color: {Theme.TEXT_PRIMARY};
            }}
            QLineEdit, QComboBox {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: #ffffff;
                padding: 6px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {Theme.BORDER_FOCUS};
            }}
            QFrame#card {{
                background-color: {Theme.BG_TOOLBAR};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: {Theme.BG_TOOLBAR};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: {Theme.TEXT_PRIMARY};
                padding: 6px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {Theme.BG_HOVER};
                border-color: {Theme.BORDER_FOCUS};
            }}
            QPushButton#btn_accent {{
                background-color: {Theme.ACCENT};
                border: 1px solid {Theme.ACCENT};
                color: #ffffff;
                font-weight: 600;
            }}
            QPushButton#btn_accent:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
            QCheckBox {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 12px;
            }}
        """)

    def _on_images_toggled(self, checked: bool) -> None:
        self.img_options_widget.setEnabled(checked)

    def _browse_destination(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save Optimized PDF As",
            self.dest_edit.text(),
            "PDF Files (*.pdf)",
        )
        if dest:
            self.dest_edit.setText(dest)

    def _perform_optimize(self) -> None:
        dest_str = self.dest_edit.text().strip()
        if not dest_str:
            QMessageBox.warning(self, "Invalid Destination", "Please specify an output destination path.")
            return

        dest_path = Path(dest_str).resolve()
        if self.doc_mgr.file_path and dest_path == self.doc_mgr.file_path.resolve():
            QMessageBox.warning(
                self,
                "Destination Conflict",
                "Optimization output cannot overwrite the active original file directly.\nPlease specify a different filename.",
            )
            return

        do_struct = self.chk_structural.isChecked()
        do_deflate = self.chk_deflate.isChecked()
        do_images = self.chk_images.isChecked()
        dpi_target = int(self.dpi_combo.currentData())
        quality = self.quality_slider.value()

        try:
            saved, orig_bytes, new_bytes = self.doc_mgr.optimize_document(
                destination=dest_path,
                garbage=4 if do_struct else 0,
                deflate=do_deflate,
                clean=do_struct,
                linear=do_struct,
                rewrite_images=do_images,
                dpi_target=dpi_target,
                image_quality=quality,
            )

            # Report stats
            orig_kb = orig_bytes / 1024.0
            new_kb = new_bytes / 1024.0
            diff_kb = orig_kb - new_kb
            pct = ((orig_bytes - new_bytes) / max(1, orig_bytes)) * 100.0

            if pct > 0.5:
                stat_msg = f"Reduced size by {pct:.1f}% ({diff_kb:.1f} KB saved)\nOriginal: {orig_kb:.1f} KB → Optimized: {new_kb:.1f} KB"
            else:
                stat_msg = f"File is already well-compressed (saved {diff_kb:.1f} KB)\nOriginal: {orig_kb:.1f} KB → Optimized: {new_kb:.1f} KB"

            res = QMessageBox.information(
                self,
                "Optimization Complete",
                f"Successfully optimized document!\n\n{stat_msg}\n\nSaved to:\n{saved}",
            )
            self.optimized_file_ready.emit(str(saved))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Optimization Failed", f"Could not optimize document:\n{e}")
