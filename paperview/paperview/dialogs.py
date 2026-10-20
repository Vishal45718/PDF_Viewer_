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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from paperview.document import DocumentMetadata
from paperview.theme import Theme


class PropertiesDialog(QDialog):
    """Displays structured document metadata and security attributes."""

    def __init__(self, metadata: DocumentMetadata, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
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

        # Card Container
        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def add_row(label: str, value: str) -> None:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-weight: 600; font-size: 12px;")
            val = QLabel(value if value else "—")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            val.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 12px;")
            form.addRow(lbl, val)

        size_kb = metadata.file_size_bytes / 1024.0
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{(size_kb/1024.0):.2f} MB"

        add_row("Title:", metadata.title)
        add_row("Author:", metadata.author)
        add_row("Subject:", metadata.subject)
        add_row("Keywords:", metadata.keywords)
        add_row("Page Count:", f"{metadata.page_count} pages")

        if metadata.page_dimensions:
            w, h = metadata.page_dimensions[0]
            w_in, h_in = w / 72.0, h / 72.0
            add_row("Page Size (P1):", f"{w:.1f} × {h:.1f} pts ({w_in:.2f} × {h_in:.2f} in)")

        add_row("PDF Format:", metadata.format_version)
        add_row("Application / Creator:", metadata.creator)
        add_row("PDF Producer:", metadata.producer)
        add_row("Created Date:", metadata.creation_date)
        add_row("Modified Date:", metadata.modification_date)
        add_row("File Size:", f"{size_str} ({metadata.file_size_bytes:,} bytes)")
        add_row("File Path:", metadata.file_path)

        sec_str = "Yes (Password Encrypted)" if metadata.is_encrypted else "None (Unencrypted)"
        add_row("Security:", sec_str)

        layout.addWidget(card)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


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
