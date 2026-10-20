"""
Dialogs for PaperView:
1. Document Properties Dialog (organized metadata, security, and dimensions).
2. Password Prompt Dialog.
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from paperview.document import DocumentMetadata
from paperview.theme import Theme


class PropertiesDialog(QDialog):
    """Displays structured document metadata and security attributes.

    If doc_manager is provided (Milestone 5), metadata fields become editable
    and an "Apply Changes" button allows saving new metadata back to the document.
    """

    def __init__(
        self,
        metadata: DocumentMetadata,
        parent: Optional[QWidget] = None,
        doc_manager=None,  # Optional[DocumentManager] — avoids circular import
    ) -> None:
        super().__init__(parent)
        self._doc_manager = doc_manager
        self.setWindowTitle("Document Properties")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_TOOLBAR};
                color: {Theme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
            QFrame#card {{
                background-color: {Theme.BG_WINDOW};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 12px;
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
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: #ffffff;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 20px;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header Title
        header = QLabel("Document Properties")
        header.setFont(QFont("sans-serif", 15, QFont.Weight.Bold))
        header.setStyleSheet("color: #ffffff;")
        layout.addWidget(header)

        # Card Container — read-only fields
        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def add_row(label: str, value: str) -> None:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-weight: 600; font-size: 12px;")
            val = QLabel(value if value else "\u2014")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            val.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
            form.addRow(lbl, val)

        size_kb = metadata.file_size_bytes / 1024.0
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{(size_kb/1024.0):.2f} MB"

        add_row("Page Count:", f"{metadata.page_count} pages")

        if metadata.page_dimensions:
            w, h = metadata.page_dimensions[0]
            w_in, h_in = w / 72.0, h / 72.0
            add_row("Page Size (P1):", f"{w:.1f} \u00d7 {h:.1f} pts ({w_in:.2f} \u00d7 {h_in:.2f} in)")

        add_row("PDF Format:", metadata.format_version)
        add_row("Created Date:", metadata.creation_date)
        add_row("Modified Date:", metadata.modification_date)
        add_row("File Size:", f"{size_str} ({metadata.file_size_bytes:,} bytes)")
        add_row("File Path:", metadata.file_path)

        sec_str = "Yes (Password Encrypted)" if metadata.is_encrypted else "None (Unencrypted)"
        add_row("Security:", sec_str)

        layout.addWidget(card)

        # Editable metadata fields (only when doc_manager is provided — Milestone 5)
        if doc_manager is not None:
            edit_group = QGroupBox("Editable Metadata")
            edit_form = QFormLayout(edit_group)
            edit_form.setSpacing(8)

            def _make_field(value: str) -> QLineEdit:
                field = QLineEdit(value or "")
                return field

            self._title_edit = _make_field(metadata.title)
            self._author_edit = _make_field(metadata.author)
            self._subject_edit = _make_field(metadata.subject)
            self._keywords_edit = _make_field(metadata.keywords)
            self._creator_edit = _make_field(metadata.creator)
            self._producer_edit = _make_field(metadata.producer)

            def _lbl(text: str) -> QLabel:
                l = QLabel(text)
                l.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-weight: 600;")
                return l

            edit_form.addRow(_lbl("Title:"), self._title_edit)
            edit_form.addRow(_lbl("Author:"), self._author_edit)
            edit_form.addRow(_lbl("Subject:"), self._subject_edit)
            edit_form.addRow(_lbl("Keywords:"), self._keywords_edit)
            edit_form.addRow(_lbl("Creator:"), self._creator_edit)
            edit_form.addRow(_lbl("Producer:"), self._producer_edit)

            apply_btn = QPushButton("Apply Changes")
            apply_btn.clicked.connect(self._apply_metadata)
            edit_form.addRow("", apply_btn)

            layout.addWidget(edit_group)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def _apply_metadata(self) -> None:
        """Saves edited metadata back to the document via doc_manager."""
        if self._doc_manager is None:
            return
        meta = {
            "title": self._title_edit.text(),
            "author": self._author_edit.text(),
            "subject": self._subject_edit.text(),
            "keywords": self._keywords_edit.text(),
            "creator": self._creator_edit.text(),
            "producer": self._producer_edit.text(),
        }
        ok = self._doc_manager.set_metadata(meta)
        if ok:
            QMessageBox.information(
                self, "Metadata Saved",
                "Document metadata has been updated.\n"
                "Save the document to persist the changes."
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to update metadata.")

class PasswordDialog(QDialog):
    """Prompts the user for a password to unlock protected PDFs."""

    def __init__(self, filename: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Password Required")
        self.setMinimumWidth(380)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_TOOLBAR};
                color: {Theme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
                font-size: 13px;
            }}
            QLineEdit {{
                background-color: {Theme.BG_INPUT};
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 4px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {Theme.BORDER_FOCUS};
            }}
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        info_label = QLabel(f"The document <b>{filename}</b> is encrypted.<br>Please enter the password to open it:")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter document password...")
        layout.addWidget(self.password_input)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f28b82; font-size: 12px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_password(self) -> str:
        return self.password_input.text()

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        self.password_input.selectAll()
        self.password_input.setFocus()


class AboutDialog(QDialog):
    """
    Displays application identity, version, framework/engine versions,
    and open-source/AGPL licensing terms.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        import platform
        import PySide6
        from PySide6.QtCore import qVersion
        import pymupdf
        from paperview import __app_name__, __version__, __description__
        from paperview.icons import get_app_icon

        self.setWindowTitle(f"About {__app_name__}")
        self.setFixedSize(540, 500)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Theme.BG_TOOLBAR};
                color: {Theme.TEXT_PRIMARY};
            }}
            QLabel {{
                color: {Theme.TEXT_PRIMARY};
            }}
            QFrame#card {{
                background-color: {Theme.BG_WINDOW};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame#license_card {{
                background-color: {Theme.BG_WINDOW};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 10px;
            }}
            QPushButton {{
                background-color: {Theme.ACCENT};
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {Theme.ACCENT_HOVER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header with Icon and Title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        icon_label = QLabel()
        app_icon = get_app_icon()
        icon_pixmap = app_icon.pixmap(64, 64)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(64, 64)
        header_layout.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        app_title = QLabel(__app_name__)
        app_title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        version_label = QLabel(f"Version {__version__}")
        version_label.setStyleSheet(f"color: {Theme.ACCENT}; font-size: 13px; font-weight: 600;")
        tagline = QLabel(__description__)
        tagline.setWordWrap(True)
        tagline.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")

        title_layout.addWidget(app_title)
        title_layout.addWidget(version_label)
        title_layout.addWidget(tagline)
        header_layout.addLayout(title_layout, stretch=1)
        layout.addLayout(header_layout)

        # Environment & Engine Specifications Card
        specs_card = QFrame()
        specs_card.setObjectName("card")
        specs_layout = QFormLayout(specs_card)
        specs_layout.setContentsMargins(12, 10, 12, 10)
        specs_layout.setHorizontalSpacing(16)
        specs_layout.setVerticalSpacing(6)

        def add_spec_row(label: str, value: str) -> None:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 12px; font-weight: 500;")
            val = QLabel(value)
            val.setStyleSheet("color: #ffffff; font-size: 12px; font-family: monospace;")
            specs_layout.addRow(lbl, val)

        add_spec_row("GUI Framework:", f"PySide6 {PySide6.__version__} (Qt {qVersion()})")
        add_spec_row("PDF Engine:", f"PyMuPDF {pymupdf.__version__} (MuPDF backend)")
        add_spec_row("Python Runtime:", f"{platform.python_version()} ({platform.python_implementation()})")
        add_spec_row("Platform:", f"{platform.system()} {platform.release()} ({platform.machine()})")
        layout.addWidget(specs_card)

        # Licensing Card (Important AGPL Notice)
        license_card = QFrame()
        license_card.setObjectName("license_card")
        lic_layout = QVBoxLayout(license_card)
        lic_layout.setContentsMargins(12, 10, 12, 10)
        lic_layout.setSpacing(6)

        lic_title = QLabel("Licensing & Distribution Notice")
        lic_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #ffffff;")
        lic_text = QLabel(
            "PaperView is open-source software under the GNU AGPLv3. "
            "It links dynamically with PyMuPDF / MuPDF (Artifex Software, Inc.), which is licensed "
            "under GNU AGPLv3. Any distribution of packaged binaries or derived works must comply with "
            "the GNU AGPLv3 obligations, including providing complete corresponding source code. "
            "See LICENSE_NOTES.md for full details."
        )
        lic_text.setWordWrap(True)
        lic_text.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px; line-height: 1.4;")

        lic_layout.addWidget(lic_title)
        lic_layout.addWidget(lic_text)
        layout.addWidget(license_card)

        layout.addStretch(1)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        ok_btn = QPushButton("Close")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

