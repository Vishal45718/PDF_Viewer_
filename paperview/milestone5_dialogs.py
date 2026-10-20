"""
Milestone 5 Dialogs for PaperView:
1. CropDialog          — Set CropBox for one or more pages
2. HeaderFooterDialog  — Insert header/footer text with templates
3. ExportDialog        — Export pages as PNG/JPEG images
4. AttachmentDialog    — View, add, and extract embedded file attachments
5. SecurityDialog      — Create AES-256 password-protected PDF copies
6. BookmarkEditorDialog— Add, rename, delete, and reorder bookmarks
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from paperview.document import DocumentError, DocumentManager
from paperview.theme import Theme


def _apply_dialog_theme(dlg: QDialog) -> None:
    dlg.setStyleSheet(f"""
        QDialog {{
            background-color: {Theme.BG_WINDOW};
            color: {Theme.TEXT_PRIMARY};
        }}
        QLabel {{
            color: {Theme.TEXT_PRIMARY};
        }}
        QGroupBox {{
            color: {Theme.TEXT_SECONDARY};
            border: 1px solid {Theme.BORDER_SUBTLE};
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 8px;
            font-size: 11px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
        }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {Theme.BG_INPUT};
            border: 1px solid {Theme.BORDER_INPUT};
            border-radius: 4px;
            color: #ffffff;
            padding: 4px 8px;
            font-size: 12px;
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {Theme.BORDER_FOCUS};
        }}
        QPushButton {{
            background-color: {Theme.ACCENT};
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 6px 14px;
            font-weight: 500;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: {Theme.ACCENT_HOVER};
        }}
        QPushButton:disabled {{
            background-color: {Theme.BORDER_SUBTLE};
            color: {Theme.TEXT_SECONDARY};
        }}
        QTableWidget {{
            background-color: {Theme.BG_SIDEBAR};
            alternate-background-color: {Theme.BG_TOOLBAR};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_SUBTLE};
            gridline-color: {Theme.BORDER_SUBTLE};
        }}
        QHeaderView::section {{
            background-color: {Theme.BG_TOOLBAR};
            color: {Theme.TEXT_SECONDARY};
            border: none;
            padding: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        QTreeWidget {{
            background-color: {Theme.BG_SIDEBAR};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_SUBTLE};
        }}
        QCheckBox {{
            color: {Theme.TEXT_PRIMARY};
        }}
    """)


# =============================================================================
# CropDialog
# =============================================================================

class CropDialog(QDialog):
    """Dialog for setting the CropBox on one or more pages."""

    crop_applied = Signal()

    def __init__(
        self,
        doc_manager: DocumentManager,
        current_page: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._dm = doc_manager
        self._current_page = current_page
        self.setWindowTitle("Crop Pages")
        self.setMinimumWidth(380)
        _apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Crop Pages — Set CropBox")
        header.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        info = QLabel(
            "CropBox restricts the visible area of a page without deleting content.\n"
            "Set coordinates in PDF points (1 pt = 1/72 inch)."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(info)

        # Preset combo
        preset_grp = QGroupBox("Quick Preset")
        preset_layout = QHBoxLayout(preset_grp)
        self._preset_combo = QComboBox()
        self._preset_combo.addItem("Custom")
        for name in DocumentManager.CROP_PRESETS:
            self._preset_combo.addItem(name)
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(QLabel("Preset:"))
        preset_layout.addWidget(self._preset_combo)
        layout.addWidget(preset_grp)

        # Coordinate inputs
        coord_grp = QGroupBox("Crop Rectangle (points)")
        coord_form = QFormLayout(coord_grp)

        def _spin() -> QSpinBox:
            s = QSpinBox()
            s.setRange(0, 9999)
            return s

        self._x0_spin = _spin()
        self._y0_spin = _spin()
        self._x1_spin = QSpinBox()
        self._x1_spin.setRange(1, 9999)
        self._x1_spin.setValue(595)
        self._y1_spin = QSpinBox()
        self._y1_spin.setRange(1, 9999)
        self._y1_spin.setValue(842)

        coord_form.addRow("Left (x0):", self._x0_spin)
        coord_form.addRow("Top (y0):", self._y0_spin)
        coord_form.addRow("Right (x1):", self._x1_spin)
        coord_form.addRow("Bottom (y1):", self._y1_spin)
        layout.addWidget(coord_grp)

        # Apply to
        apply_grp = QGroupBox("Apply To")
        apply_layout = QHBoxLayout(apply_grp)
        self._apply_combo = QComboBox()
        self._apply_combo.addItems(["Current Page", "All Pages"])
        apply_layout.addWidget(self._apply_combo)
        layout.addWidget(apply_grp)

        # Buttons
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply Crop")
        apply_btn.clicked.connect(self._apply)
        reset_btn = QPushButton("Reset Crop")
        reset_btn.clicked.connect(self._reset)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Set current page defaults
        if doc_manager.is_open and doc_manager.doc:
            try:
                page = doc_manager.doc[current_page]
                mb = page.mediabox
                self._x1_spin.setValue(int(mb.x1))
                self._y1_spin.setValue(int(mb.y1))
            except Exception:
                pass

    def _on_preset_changed(self, name: str) -> None:
        if name in DocumentManager.CROP_PRESETS:
            x0, y0, x1, y1 = DocumentManager.CROP_PRESETS[name]
            self._x0_spin.setValue(int(x0))
            self._y0_spin.setValue(int(y0))
            self._x1_spin.setValue(int(x1))
            self._y1_spin.setValue(int(y1))

    def _apply(self) -> None:
        rect = pymupdf.Rect(
            self._x0_spin.value(),
            self._y0_spin.value(),
            self._x1_spin.value(),
            self._y1_spin.value(),
        )
        if rect.is_empty or rect.is_infinite:
            QMessageBox.warning(self, "Invalid Crop", "The crop rectangle is invalid (empty or infinite).")
            return
        apply_to = self._apply_combo.currentText()
        if apply_to == "Current Page":
            ok = self._dm.crop_page(self._current_page, rect)
        else:
            count = self._dm.crop_pages(list(range(self._dm.page_count)), rect)
            ok = count > 0
        if ok:
            self.crop_applied.emit()
            QMessageBox.information(self, "Crop Applied", "CropBox has been set.\nSave the document to persist changes.")
        else:
            QMessageBox.warning(self, "Crop Failed", "Failed to apply crop. Check the coordinate values.")

    def _reset(self) -> None:
        ok = self._dm.reset_crop(self._current_page)
        if ok:
            self.crop_applied.emit()
        else:
            QMessageBox.warning(self, "Reset Failed", "Failed to reset crop.")


# =============================================================================
# HeaderFooterDialog
# =============================================================================

class HeaderFooterDialog(QDialog):
    """Dialog for inserting header and footer text with template variables."""

    hf_applied = Signal()

    def __init__(
        self,
        doc_manager: DocumentManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._dm = doc_manager
        self.setWindowTitle("Header & Footer")
        self.setMinimumWidth(460)
        _apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Insert Header & Footer")
        header.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        info = QLabel(
            "Templates: {page} = page number, {total} = total pages, "
            "{date} = today's date, {filename} = file name."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(info)

        # Header group
        h_grp = QGroupBox("Header")
        h_form = QFormLayout(h_grp)
        self._hl_edit = QLineEdit()
        self._hc_edit = QLineEdit()
        self._hr_edit = QLineEdit()
        h_form.addRow("Left:", self._hl_edit)
        h_form.addRow("Center:", self._hc_edit)
        h_form.addRow("Right:", self._hr_edit)
        layout.addWidget(h_grp)

        # Footer group
        f_grp = QGroupBox("Footer")
        f_form = QFormLayout(f_grp)
        self._fl_edit = QLineEdit()
        self._fc_edit = QLineEdit()
        self._fr_edit = QLineEdit()
        f_form.addRow("Left:", self._fl_edit)
        f_form.addRow("Center:", self._fc_edit)
        f_form.addRow("Right:", self._fr_edit)
        layout.addWidget(f_grp)

        # Options
        opt_grp = QGroupBox("Options")
        opt_form = QFormLayout(opt_grp)
        self._fontsize_spin = QDoubleSpinBox()
        self._fontsize_spin.setRange(6.0, 24.0)
        self._fontsize_spin.setValue(10.0)
        self._fontsize_spin.setSuffix(" pt")
        self._margin_spin = QDoubleSpinBox()
        self._margin_spin.setRange(5.0, 100.0)
        self._margin_spin.setValue(20.0)
        self._margin_spin.setSuffix(" pt")
        self._apply_to_combo = QComboBox()
        self._apply_to_combo.addItems(["All Pages", "Current Page"])
        opt_form.addRow("Font Size:", self._fontsize_spin)
        opt_form.addRow("Margin:", self._margin_spin)
        opt_form.addRow("Apply To:", self._apply_to_combo)
        layout.addWidget(opt_grp)

        # Buttons
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(apply_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _apply(self) -> None:
        config = {
            "header_left": self._hl_edit.text(),
            "header_center": self._hc_edit.text(),
            "header_right": self._hr_edit.text(),
            "footer_left": self._fl_edit.text(),
            "footer_center": self._fc_edit.text(),
            "footer_right": self._fr_edit.text(),
            "font_size": self._fontsize_spin.value(),
            "margin": self._margin_spin.value(),
        }
        apply_to = self._apply_to_combo.currentText()
        pages = None  # None means all pages
        ok = self._dm.apply_header_footer(config, pages=pages)
        if ok:
            self.hf_applied.emit()
            QMessageBox.information(self, "Applied", "Header/footer inserted.\nSave the document to persist changes.")
        else:
            QMessageBox.warning(self, "Failed", "Failed to insert header/footer.")


# =============================================================================
# ExportDialog
# =============================================================================

class ExportDialog(QDialog):
    """Dialog for exporting pages as PNG or JPEG images."""

    export_done = Signal(list)

    def __init__(
        self,
        doc_manager: DocumentManager,
        current_page: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._dm = doc_manager
        self._current_page = current_page
        self.setWindowTitle("Export Pages as Images")
        self.setMinimumWidth(400)
        _apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Export Pages as Images")
        header.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        # Format
        fmt_grp = QGroupBox("Format")
        fmt_form = QFormLayout(fmt_grp)
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["PNG", "JPEG"])
        fmt_form.addRow("Image Format:", self._fmt_combo)

        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 600)
        self._dpi_spin.setValue(150)
        self._dpi_spin.setSuffix(" DPI")
        fmt_form.addRow("Resolution:", self._dpi_spin)

        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(1, 100)
        self._quality_spin.setValue(85)
        fmt_form.addRow("JPEG Quality:", self._quality_spin)

        layout.addWidget(fmt_grp)

        # Page range
        range_grp = QGroupBox("Page Range")
        range_layout = QHBoxLayout(range_grp)
        self._range_combo = QComboBox()
        self._range_combo.addItems(["All Pages", "Current Page"])
        range_layout.addWidget(self._range_combo)
        layout.addWidget(range_grp)

        # Output directory
        dir_grp = QGroupBox("Output Directory")
        dir_layout = QHBoxLayout(dir_grp)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Choose output folder…")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        dir_layout.addWidget(self._dir_edit)
        dir_layout.addWidget(browse_btn)
        layout.addWidget(dir_grp)

        # Buttons
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if d:
            self._dir_edit.setText(d)

    def _export(self) -> None:
        out_dir = self._dir_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "No Directory", "Please choose an output directory.")
            return
        fmt = self._fmt_combo.currentText().lower()
        dpi = self._dpi_spin.value()
        quality = self._quality_spin.value()
        page_range = self._range_combo.currentText()
        if page_range == "Current Page":
            indices = [self._current_page]
        else:
            indices = list(range(self._dm.page_count))
        try:
            paths = self._dm.export_pages_as_images(indices, out_dir, fmt, dpi, quality)
            self.export_done.emit([str(p) for p in paths])
            QMessageBox.information(self, "Export Complete", f"Exported {len(paths)} page(s) to:\n{out_dir}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))


# =============================================================================
# AttachmentDialog
# =============================================================================

class AttachmentDialog(QDialog):
    """Dialog for viewing, adding, and extracting embedded file attachments."""

    def __init__(
        self,
        doc_manager: DocumentManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._dm = doc_manager
        self.setWindowTitle("PDF Attachments")
        self.setMinimumSize(480, 320)
        _apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Embedded File Attachments")
        header.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Size", "Description"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        extract_btn = QPushButton("Extract Selected")
        extract_btn.clicked.connect(self._extract)
        add_btn = QPushButton("Add File…")
        add_btn.clicked.connect(self._add)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(extract_btn)
        btn_layout.addWidget(add_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._refresh()

    def _refresh(self) -> None:
        self._table.setRowCount(0)
        attachments = self._dm.get_attachments()
        for att in attachments:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(att["name"]))
            size_kb = att["size"] / 1024.0
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            self._table.setItem(row, 1, QTableWidgetItem(size_str))
            self._table.setItem(row, 2, QTableWidgetItem(att["description"]))

    def _extract(self) -> None:
        rows = [idx.row() for idx in self._table.selectedIndexes()]
        if not rows:
            QMessageBox.information(self, "No Selection", "Please select an attachment to extract.")
            return
        row = rows[0]
        name = self._table.item(row, 0).text()
        dest, _ = QFileDialog.getSaveFileName(self, "Save Attachment As", name)
        if not dest:
            return
        try:
            path = self._dm.extract_attachment(row, dest)
            QMessageBox.information(self, "Extracted", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Extract Failed", str(e))

    def _add(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Add File as Attachment")
        if not path:
            return
        ok = self._dm.add_attachment(path)
        if ok:
            self._refresh()
            QMessageBox.information(self, "Attached", f"Added: {Path(path).name}")
        else:
            QMessageBox.warning(self, "Failed", "Could not add attachment.")


# =============================================================================
# SecurityDialog
# =============================================================================

class SecurityDialog(QDialog):
    """Dialog for saving an AES-256 password-protected copy of the document."""

    def __init__(
        self,
        doc_manager: DocumentManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._dm = doc_manager
        self.setWindowTitle("Document Security")
        self.setMinimumWidth(420)
        _apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Password Protection")
        header.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        info = QLabel(
            "Creates an AES-256 encrypted copy of the document. "
            "The original file is not modified.\n\n"
            "Note: Encryption requires both user and owner passwords."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(info)

        # Passwords
        pwd_grp = QGroupBox("Passwords")
        pwd_form = QFormLayout(pwd_grp)
        self._user_edit = QLineEdit()
        self._user_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._user_edit.setPlaceholderText("Password to open the document…")
        self._owner_edit = QLineEdit()
        self._owner_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._owner_edit.setPlaceholderText("Password to change security settings…")
        pwd_form.addRow("User Password:", self._user_edit)
        pwd_form.addRow("Owner Password:", self._owner_edit)
        layout.addWidget(pwd_grp)

        # Permissions
        perm_grp = QGroupBox("Permissions")
        perm_layout = QVBoxLayout(perm_grp)
        self._perm_print = QCheckBox("Allow Printing")
        self._perm_copy = QCheckBox("Allow Copying Text")
        self._perm_modify = QCheckBox("Allow Modifying")
        self._perm_print.setChecked(True)
        self._perm_copy.setChecked(True)
        self._perm_modify.setChecked(False)
        perm_layout.addWidget(self._perm_print)
        perm_layout.addWidget(self._perm_copy)
        perm_layout.addWidget(self._perm_modify)
        layout.addWidget(perm_grp)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Protected Copy…")
        save_btn.clicked.connect(self._save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _build_permissions(self) -> int:
        # PDF permission bits (PDF spec, Table 22)
        perms = 0
        if self._perm_print.isChecked():
            perms |= pymupdf.PDF_PERM_PRINT        # bit 3
        if self._perm_copy.isChecked():
            perms |= pymupdf.PDF_PERM_COPY          # bit 5
        if self._perm_modify.isChecked():
            perms |= pymupdf.PDF_PERM_MODIFY        # bit 4
        return perms if perms else 0xFFFFFC

    def _save(self) -> None:
        user_pwd = self._user_edit.text()
        owner_pwd = self._owner_edit.text()
        if not user_pwd or not owner_pwd:
            QMessageBox.warning(self, "Missing Password", "Both user and owner passwords are required.")
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Save Protected PDF As", "", "PDF Files (*.pdf)")
        if not dest:
            return
        try:
            perms = self._build_permissions()
            path = self._dm.save_protected(dest, user_pwd, owner_pwd, permissions=perms)
            QMessageBox.information(self, "Saved", f"Protected PDF saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))


# =============================================================================
# BookmarkEditorDialog
# =============================================================================

class BookmarkEditorDialog(QDialog):
    """Dialog for adding, renaming, deleting, and changing page targets of bookmarks."""

    bookmarks_changed = Signal()

    def __init__(
        self,
        doc_manager: DocumentManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._dm = doc_manager
        self.setWindowTitle("Manage Bookmarks")
        self.setMinimumSize(500, 420)
        _apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Bookmark Editor")
        header.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Title", "Page"])
        self._tree.setColumnWidth(0, 340)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(self._add)
        rename_btn = QPushButton("Rename…")
        rename_btn.clicked.connect(self._rename)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(rename_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._refresh()

    def _refresh(self) -> None:
        self._tree.clear()
        toc = self._dm.get_toc()
        for entry in toc:
            level, title, page_num = entry[0], entry[1], entry[2]
            item = QTreeWidgetItem([title, str(page_num)])
            self._tree.addTopLevelItem(item)
        self._tree.expandAll()

    def _selected_index(self) -> int:
        items = self._tree.selectedItems()
        if not items:
            return -1
        # Return top-level index
        idx = self._tree.indexOfTopLevelItem(items[0])
        return idx

    def _add(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        title, ok = QInputDialog.getText(self, "Add Bookmark", "Bookmark title:")
        if not ok or not title:
            return
        page_idx = 0  # Default to first page
        if self._dm.page_count > 1:
            p, ok2 = QInputDialog.getInt(
                self, "Add Bookmark", "Target page number (1-based):", 1, 1, self._dm.page_count
            )
            if ok2:
                page_idx = p - 1
        self._dm.add_bookmark(title, page_idx)
        self._refresh()
        self.bookmarks_changed.emit()

    def _rename(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        idx = self._selected_index()
        if idx < 0:
            QMessageBox.information(self, "No Selection", "Select a bookmark to rename.")
            return
        items = self._tree.selectedItems()
        current_title = items[0].text(0)
        new_title, ok = QInputDialog.getText(self, "Rename Bookmark", "New title:", text=current_title)
        if ok and new_title:
            self._dm.rename_bookmark(idx, new_title)
            self._refresh()
            self.bookmarks_changed.emit()

    def _delete(self) -> None:
        idx = self._selected_index()
        if idx < 0:
            QMessageBox.information(self, "No Selection", "Select a bookmark to delete.")
            return
        items = self._tree.selectedItems()
        title = items[0].text(0)
        ans = QMessageBox.question(
            self, "Delete Bookmark",
            f"Delete bookmark \"{title}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            self._dm.delete_bookmark(idx)
            self._refresh()
            self.bookmarks_changed.emit()


# =============================================================================
# ImageExtractionDialog
# =============================================================================

class ImageExtractionDialog(QDialog):
    """Dialog for inspecting, previewing, and extracting embedded images."""

    def __init__(
        self,
        doc_manager: DocumentManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._dm = doc_manager
        self.setWindowTitle("Extract Embedded Images")
        self.setMinimumSize(640, 440)
        _apply_dialog_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("Embedded Images in Document")
        header.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        # Content: Table + Preview pane
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Page", "Dimensions", "Format", "XRef"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        content_layout.addWidget(self._table, 2)

        # Preview group
        preview_box = QGroupBox("Image Preview")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._preview_label = QLabel("No image selected")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(180, 180)
        self._preview_label.setStyleSheet("color: #888888; font-size: 11px;")
        preview_layout.addWidget(self._preview_label)

        self._info_label = QLabel("")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        preview_layout.addWidget(self._info_label)

        content_layout.addWidget(preview_box, 1)
        layout.addLayout(content_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self._btn_extract_selected = QPushButton("Extract Selected...")
        self._btn_extract_selected.clicked.connect(self._extract_selected)
        btn_layout.addWidget(self._btn_extract_selected)

        self._btn_extract_all = QPushButton("Extract All...")
        self._btn_extract_all.clicked.connect(self._extract_all)
        btn_layout.addWidget(self._btn_extract_all)

        btn_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        self._images: List[Dict[str, Any]] = []
        self._refresh()

    def _refresh(self) -> None:
        self._table.setRowCount(0)
        self._preview_label.clear()
        self._preview_label.setText("No image selected")
        self._info_label.setText("")

        if not self._dm.is_open:
            self._btn_extract_selected.setEnabled(False)
            self._btn_extract_all.setEnabled(False)
            return

        self._images = self._dm.get_embedded_images()
        if not self._images:
            self._preview_label.setText("No images found")
            self._btn_extract_selected.setEnabled(False)
            self._btn_extract_all.setEnabled(False)
            return

        self._btn_extract_selected.setEnabled(True)
        self._btn_extract_all.setEnabled(True)

        for img in self._images:
            row = self._table.rowCount()
            self._table.insertRow(row)

            page_item = QTableWidgetItem(f"Page {img.get('page', 0) + 1}")
            page_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, page_item)

            dim_text = f"{img.get('width', 0)} × {img.get('height', 0)} px"
            dim_item = QTableWidgetItem(dim_text)
            self._table.setItem(row, 1, dim_item)

            fmt_text = f"{img.get('ext', 'png').upper()} ({img.get('colorspace', 'RGB')})"
            fmt_item = QTableWidgetItem(fmt_text)
            fmt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, fmt_item)

            xref_item = QTableWidgetItem(str(img.get("xref", "")))
            xref_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, xref_item)

        if self._table.rowCount() > 0:
            self._table.selectRow(0)

    def _on_selection_changed(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._preview_label.clear()
            self._preview_label.setText("No image selected")
            self._info_label.setText("")
            return

        idx = rows[0].row()
        if idx < 0 or idx >= len(self._images):
            return

        img_meta = self._images[idx]
        xref = img_meta.get("xref", 0)

        try:
            pix = pymupdf.Pixmap(self._dm._doc, xref)
            if pix.n - pix.alpha > 3:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            img_format = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, img_format).copy()
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                180, 180,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(scaled)
            self._info_label.setText(f"{img_meta.get('width', 0)} × {img_meta.get('height', 0)} px • {img_meta.get('ext', '').upper()}")
        except Exception:
            self._preview_label.clear()
            self._preview_label.setText("Preview unavailable")
            self._info_label.setText("")

    def _extract_selected(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No Selection", "Please select an image to extract.")
            return

        idx = rows[0].row()
        img = self._images[idx]
        xref = img.get("xref", 0)
        ext = img.get("ext", "png")
        page = img.get("page", 0)

        default_name = f"page_{page + 1}_xref_{xref}.{ext}"
        dest_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save Extracted Image",
            default_name,
            f"Images (*.{ext});;All Files (*)",
        )
        if not dest_file:
            return

        try:
            out_path = self._dm.extract_embedded_image(xref, dest_file)
            QMessageBox.information(self, "Extraction Successful", f"Image saved to:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Extraction Failed", str(e))

    def _extract_all(self) -> None:
        if not self._images:
            return

        out_dir = QFileDialog.getExistingDirectory(self, "Select Destination Directory")
        if not out_dir:
            return

        dir_path = Path(out_dir)
        count = 0
        try:
            for img in self._images:
                xref = img.get("xref", 0)
                ext = img.get("ext", "png")
                page = img.get("page", 0)
                fname = f"extracted_p{page + 1}_xref_{xref}.{ext}"
                self._dm.extract_embedded_image(xref, dir_path / fname)
                count += 1
            QMessageBox.information(
                self,
                "Extraction Complete",
                f"Successfully extracted {count} image(s) to:\n{out_dir}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Extraction Failed", str(e))

