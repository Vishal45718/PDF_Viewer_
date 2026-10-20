"""
Milestone 4 Dialogs for PaperView:
1. RedactionDialog  — Mark and permanently apply redactions
2. SignatureDialog  — Create and place a visible (non-cryptographic) signature
3. StampDialog      — Select and place a predefined rubber stamp
4. FormViewerDialog — Browse and fill interactive form fields
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pymupdf

from PySide6.QtCore import (
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from paperview.document import DocumentError, DocumentManager
from paperview.icons import get_icon
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
            subcontrol-position: top left;
            padding: 0 6px;
            color: {Theme.TEXT_SECONDARY};
        }}
        QLineEdit, QTextEdit, QComboBox, QSpinBox {{
            background-color: {Theme.BG_INPUT};
            border: 1px solid {Theme.BORDER_INPUT};
            border-radius: 4px;
            color: {Theme.TEXT_PRIMARY};
            padding: 4px 8px;
            font-size: 12px;
        }}
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 1px solid {Theme.BORDER_FOCUS};
        }}
        QComboBox::drop-down {{ border-left: none; width: 18px; }}
        QComboBox QAbstractItemView {{
            background-color: {Theme.BG_TOOLBAR};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_SUBTLE};
            selection-background-color: {Theme.ACCENT};
        }}
        QPushButton {{
            background-color: {Theme.BG_HOVER};
            color: {Theme.TEXT_PRIMARY};
            border: 1px solid {Theme.BORDER_INPUT};
            border-radius: 5px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {Theme.ACCENT};
            color: #ffffff;
            border-color: {Theme.ACCENT};
        }}
        QPushButton:pressed {{
            background-color: {Theme.BG_ACTIVE};
        }}
        QPushButton:disabled {{
            color: {Theme.TEXT_MUTED};
            background-color: {Theme.BG_WINDOW};
            border-color: {Theme.BORDER_SUBTLE};
        }}
        QDialogButtonBox QPushButton {{
            min-width: 80px;
        }}
        QListWidget {{
            background-color: {Theme.BG_INPUT};
            border: 1px solid {Theme.BORDER_INPUT};
            border-radius: 4px;
            color: {Theme.TEXT_PRIMARY};
        }}
        QListWidget::item:selected {{
            background-color: {Theme.ACCENT};
            color: #ffffff;
        }}
        QCheckBox {{
            color: {Theme.TEXT_PRIMARY};
            spacing: 6px;
        }}
        QTabWidget::pane {{
            border: 1px solid {Theme.BORDER_SUBTLE};
            border-radius: 4px;
        }}
        QTabBar::tab {{
            background-color: {Theme.BG_TOOLBAR};
            color: {Theme.TEXT_SECONDARY};
            border: 1px solid {Theme.BORDER_SUBTLE};
            padding: 6px 14px;
            border-bottom: none;
        }}
        QTabBar::tab:selected {{
            background-color: {Theme.BG_WINDOW};
            color: {Theme.TEXT_PRIMARY};
        }}
    """)


# =============================================================================
# 1. Redaction Dialog
# =============================================================================

class RedactionDialog(QDialog):
    """
    Dialog for managing pending redactions and applying them permanently.

    Workflow:
    1. User marks regions via the Redact tool in the viewer (adds pending annotations).
    2. This dialog lists pending redactions and allows cancelling individual ones.
    3. 'Apply Redactions' permanently removes underlying PDF content via PyMuPDF.

    IMPORTANT: Applied redactions are DESTRUCTIVE and cannot be undone.
    The result should be saved to a new file; the original source is never modified.
    """

    redactions_applied = Signal()   # emitted after permanent apply

    def __init__(self, doc_mgr: DocumentManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.doc_mgr = doc_mgr
        self.setWindowTitle("Manage Redactions")
        self.resize(560, 460)
        self.setMinimumSize(400, 320)
        _apply_dialog_theme(self)
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        hdr = QLabel("Redaction Manager")
        hdr.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #e05050;")
        layout.addWidget(hdr)

        warning_box = QFrame()
        warning_box.setStyleSheet(
            "background-color: rgba(200,60,60,0.15); border: 1px solid rgba(200,60,60,0.5);"
            "border-radius: 6px; padding: 8px;"
        )
        wlayout = QVBoxLayout(warning_box)
        wlayout.setContentsMargins(10, 8, 10, 8)
        wlayout.setSpacing(4)

        w1 = QLabel("⚠  Applying redactions is PERMANENT and DESTRUCTIVE")
        w1.setStyleSheet("color: #ff8080; font-weight: 700; font-size: 12px;")
        wlayout.addWidget(w1)

        w2 = QLabel(
            "Once applied, the underlying PDF text and images within the marked regions\n"
            "are permanently removed and cannot be recovered. This only affects the saved\n"
            "copy — your original source file is never modified."
        )
        w2.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        wlayout.addWidget(w2)
        layout.addWidget(warning_box)

        # Pending redactions list
        grp = QGroupBox("Pending Redaction Regions (not yet applied)")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setContentsMargins(10, 16, 10, 10)

        self.redaction_list = QListWidget()
        self.list_widget = self.redaction_list
        self.redaction_list.setMinimumHeight(140)
        grp_layout.addWidget(self.redaction_list)

        btn_row = QHBoxLayout()
        self.btn_cancel_one = QPushButton("Remove Selected")
        self.btn_cancel_one.setToolTip("Remove the selected pending redaction region")
        self.btn_cancel_one.clicked.connect(self._cancel_selected)
        btn_row.addWidget(self.btn_cancel_one)

        self.btn_cancel_all = QPushButton("Remove All")
        self.btn_cancel_all.setToolTip("Remove all pending redaction regions from all pages")
        self.btn_cancel_all.clicked.connect(self._cancel_all)
        btn_row.addWidget(self.btn_cancel_all)
        btn_row.addStretch()
        grp_layout.addLayout(btn_row)
        layout.addWidget(grp)

        # Apply button
        self.btn_apply = QPushButton("⚫  Apply Redactions Permanently")
        self.btn_apply.setToolTip(
            "Permanently remove content under all pending redaction regions.\n"
            "Save to a NEW file after applying — never overwrites the original."
        )
        self.btn_apply.setStyleSheet(
            "QPushButton { background-color: #7b1515; color: #fff; border: 1px solid #a02020;"
            "border-radius: 5px; padding: 8px 16px; font-weight: 700; }"
            "QPushButton:hover { background-color: #a02020; }"
            "QPushButton:disabled { background-color: #333; color: #666; border-color: #444; }"
        )
        self.btn_apply.clicked.connect(self._apply_redactions)
        layout.addWidget(self.btn_apply)

        # Close button
        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.reject)
        layout.addWidget(close_btn)

    def _refresh_list(self) -> None:
        self.redaction_list.clear()
        if not self.doc_mgr.is_open:
            return
        total = 0
        for p_idx in range(self.doc_mgr.page_count):
            pending = self.doc_mgr.get_pending_redactions(p_idx)
            for rd in pending:
                r = rd["rect"]
                item = QListWidgetItem(
                    f"Page {p_idx + 1}  —  x:{r.x0:.0f}, y:{r.y0:.0f}  →  "
                    f"w:{r.width:.0f}, h:{r.height:.0f}"
                )
                item.setData(Qt.ItemDataRole.UserRole, (p_idx, rd["xref"]))
                item.setForeground(QColor("#ff9966"))
                self.redaction_list.addItem(item)
                total += 1
        has = total > 0
        self.btn_apply.setEnabled(has)
        self.btn_cancel_one.setEnabled(has)
        self.btn_cancel_all.setEnabled(has)

    def _cancel_selected(self) -> None:
        item = self.redaction_list.currentItem()
        if not item:
            return
        p_idx, xref = item.data(Qt.ItemDataRole.UserRole)
        self.doc_mgr.cancel_redaction(p_idx, xref)
        self._refresh_list()

    def _cancel_all(self) -> None:
        if not self.doc_mgr.is_open:
            return
        for p_idx in range(self.doc_mgr.page_count):
            self.doc_mgr.cancel_all_redactions(p_idx)
        self._refresh_list()

    def _apply_redactions(self, confirm: bool = True) -> None:
        if confirm:
            # Double-confirm destructive action
            res = QMessageBox.warning(
                self,
                "Confirm Permanent Redaction",
                "This will PERMANENTLY REMOVE the text, images, and content under all\n"
                "pending redaction regions. This action cannot be undone.\n\n"
                "The result must be saved to a NEW file — your original is safe.\n\n"
                "Proceed with permanent redaction?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if res != QMessageBox.StandardButton.Yes:
                return

        try:
            results = self.doc_mgr.apply_redactions()
            total_applied = sum(results.values())
            self.redactions_applied.emit()
            self._refresh_list()
            if confirm:
                QMessageBox.information(
                    self,
                    "Redactions Applied",
                    f"Successfully applied {total_applied} redaction(s) across "
                    f"{len(results)} page(s).\n\n"
                    "The redacted content has been permanently removed from the in-memory "
                    "document.\n\nRemember to save a copy to persist these changes.",
                )
        except DocumentError as e:
            if confirm:
                QMessageBox.critical(self, "Redaction Failed", str(e))
            else:
                raise

    def apply_all_redactions(self, confirm: bool = False) -> None:
        """Programmatic helper to apply pending redactions."""
        self._apply_redactions(confirm=confirm)

    def refresh(self) -> None:
        """Public refresh method for external callers."""
        self._refresh_list()


# =============================================================================
# 2. Signature Dialog
# =============================================================================

class SignatureDrawWidget(QWidget):
    """Simple canvas for drawing a freehand signature."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(400, 120)
        self._strokes: List[List[QPoint]] = []
        self._current: List[QPoint] = []
        self.setStyleSheet(
            "background-color: #ffffff; border: 2px dashed #3574f0; border-radius: 4px;"
        )
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._current = [event.position().toPoint()]

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._current is not None:
            self._current.append(event.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and len(self._current) >= 2:
            self._strokes.append(list(self._current))
        self._current = []
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))

        # Guide line
        painter.setPen(QPen(QColor(200, 200, 220), 1, Qt.PenStyle.DashLine))
        painter.drawLine(20, 90, 380, 90)

        # Signature strokes
        pen = QPen(QColor(20, 40, 140), 2, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        for stroke in self._strokes:
            if len(stroke) >= 2:
                painter.drawPolyline(stroke)
        if len(self._current) >= 2:
            painter.drawPolyline(self._current)

    def clear(self) -> None:
        self._strokes.clear()
        self._current = []
        self.update()

    def has_signature(self) -> bool:
        return bool(self._strokes)

    def to_ink_strokes(self) -> List[List[Tuple[float, float]]]:
        """Convert drawn strokes to PDF coordinate lists (y-flipped for PDF space)."""
        h = self.height()
        result = []
        for stroke in self._strokes:
            pts = [(float(pt.x()) / self.width(), float(h - pt.y()) / h)
                   for pt in stroke]
            result.append(pts)
        return result


class SignatureDialog(QDialog):
    """
    Dialog for creating and placing a visible signature.

    IMPORTANT DISCLAIMER (displayed in UI):
    This creates a VISIBLE SIGNATURE only. It is NOT a cryptographic digital
    signature and does NOT provide:
    - Certificate-based verification
    - PKI authenticity guarantees
    - Tamper-evident protection

    For legally binding digital signatures, use specialized PDF signing
    software with a valid certificate chain.
    """

    signature_ready = Signal(str, str, float, float, float, float, str)
    # Emits: page_hint, signer_name, x, y, w, h, sig_text

    def __init__(
        self,
        doc_mgr: DocumentManager,
        current_page: Any = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        if isinstance(current_page, QWidget):
            parent = current_page
            current_page = 0
        super().__init__(parent)
        self.doc_mgr = doc_mgr
        self.current_page = int(current_page) if isinstance(current_page, (int, float)) else 0
        self.setWindowTitle("Sign Document — Visible Signature")
        self.resize(520, 560)
        self.setMinimumSize(420, 440)
        _apply_dialog_theme(self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header
        hdr = QLabel("Place Visible Signature")
        hdr.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #ffffff;")
        layout.addWidget(hdr)

        # Disclaimer
        disc = QFrame()
        disc.setStyleSheet(
            "background-color: rgba(53,116,240,0.1); border: 1px solid rgba(53,116,240,0.4);"
            "border-radius: 6px;"
        )
        dl = QVBoxLayout(disc)
        dl.setContentsMargins(10, 8, 10, 8)
        dl.setSpacing(2)
        dl_title = QLabel("ℹ  Visible Signature — NOT a Cryptographic Digital Signature")
        dl_title.setStyleSheet("color: #6699ff; font-weight: 700; font-size: 11px;")
        dl.addWidget(dl_title)
        dl_body = QLabel(
            "This places a styled signature image on the PDF page. It does not provide\n"
            "certificate-based signing, PKI verification, or tamper-evident protection.\n"
            "For legally binding digital signatures, use dedicated signing software."
        )
        dl_body.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        dl.addWidget(dl_body)
        layout.addWidget(disc)

        # Tabs: Typed vs Drawn
        tabs = QTabWidget()

        # --- Typed Signature Tab ---
        typed_widget = QWidget()
        typed_layout = QFormLayout(typed_widget)
        typed_layout.setContentsMargins(12, 12, 12, 12)
        typed_layout.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter your full name")
        typed_layout.addRow("Signer Name:", self.name_edit)

        self.sig_text_edit = QLineEdit()
        self.sig_text_edit.setPlaceholderText("Custom signature text (leave blank to use name)")
        typed_layout.addRow("Signature Text:", self.sig_text_edit)

        self.fontsize_spin = QSpinBox()
        self.fontsize_spin.setRange(8, 48)
        self.fontsize_spin.setValue(18)
        typed_layout.addRow("Font Size:", self.fontsize_spin)

        tabs.addTab(typed_widget, "✏  Typed Signature")

        # --- Drawn Signature Tab ---
        draw_widget = QWidget()
        draw_layout = QVBoxLayout(draw_widget)
        draw_layout.setContentsMargins(12, 12, 12, 12)
        draw_layout.setSpacing(8)

        draw_lbl = QLabel("Draw your signature below:")
        draw_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        draw_layout.addWidget(draw_lbl)

        self.draw_canvas = SignatureDrawWidget()
        draw_layout.addWidget(self.draw_canvas, 0, Qt.AlignmentFlag.AlignHCenter)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(self.draw_canvas.clear)
        draw_layout.addWidget(clear_btn, 0, Qt.AlignmentFlag.AlignLeft)

        draw_note = QLabel("Note: Drawn signatures are embedded as styled text. For best results,\nuse the Typed Signature tab.")
        draw_note.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 10px;")
        draw_layout.addWidget(draw_note)
        draw_layout.addStretch()

        tabs.addTab(draw_widget, "✍  Drawn Signature")

        layout.addWidget(tabs)
        self._tabs = tabs

        # Placement options
        place_grp = QGroupBox("Placement on Page")
        place_layout = QFormLayout(place_grp)
        place_layout.setContentsMargins(10, 14, 10, 10)
        place_layout.setSpacing(8)

        if self.doc_mgr.is_open:
            pages = [f"Page {i + 1}" for i in range(self.doc_mgr.page_count)]
        else:
            pages = ["Page 1"]
        self.page_combo = QComboBox()
        self.page_combo.addItems(pages)
        if 0 <= self.current_page < len(pages):
            self.page_combo.setCurrentIndex(self.current_page)
        place_layout.addRow("Place on Page:", self.page_combo)

        preset_row = QWidget()
        pr_layout = QHBoxLayout(preset_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_combo = QComboBox()
        self.pos_combo = self.preset_combo
        self.preset_combo.addItems(["Bottom Right", "Bottom Left", "Bottom Center", "Top Right", "Custom"])
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        pr_layout.addWidget(self.preset_combo)
        place_layout.addRow("Preset:", preset_row)

        pos_widget = QWidget()
        pos_layout = QHBoxLayout(pos_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        pos_layout.setSpacing(8)

        for label, attr, default in [("X:", "_x_spin", 350), ("Y:", "_y_spin", 700),
                                      ("W:", "_w_spin", 200), ("H:", "_h_spin", 50)]:
            pos_layout.addWidget(QLabel(label))
            sp = QSpinBox()
            sp.setRange(0, 5000)
            sp.setValue(default)
            sp.setFixedWidth(70)
            setattr(self, attr, sp)
            pos_layout.addWidget(sp)

        place_layout.addRow("Position (pts):", pos_widget)
        layout.addWidget(place_grp)

        # Buttons
        btn_box = QDialogButtonBox()
        btn_place = btn_box.addButton("Place Signature", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_cancel = btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        btn_place.clicked.connect(self._on_place)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_preset_changed(self, text: str) -> None:
        p_idx = self.page_combo.currentIndex()
        pw, ph = 595.0, 842.0
        if self.doc_mgr.is_open and 0 <= p_idx < self.doc_mgr.page_count:
            try:
                page = self.doc_mgr.doc[p_idx]
                pw, ph = float(page.rect.width), float(page.rect.height)
            except Exception:
                pass
        w = self._w_spin.value()
        h = self._h_spin.value()
        if text == "Bottom Right":
            self._x_spin.setValue(max(0, int(pw - w - 40)))
            self._y_spin.setValue(max(0, int(ph - h - 50)))
        elif text == "Bottom Left":
            self._x_spin.setValue(40)
            self._y_spin.setValue(max(0, int(ph - h - 50)))
        elif text == "Bottom Center":
            self._x_spin.setValue(max(0, int((pw - w) / 2)))
            self._y_spin.setValue(max(0, int(ph - h - 50)))
        elif text == "Top Right":
            self._x_spin.setValue(max(0, int(pw - w - 40)))
            self._y_spin.setValue(40)

    def _on_place(self, show_msg: bool = True) -> None:
        page_idx = self.page_combo.currentIndex()
        signer = self.name_edit.text().strip()
        if not signer:
            QMessageBox.warning(self, "Missing Name", "Please enter a signer name.")
            return

        sig_text = self.sig_text_edit.text().strip() or signer
        fontsize = float(self.fontsize_spin.value())
        x = float(self._x_spin.value())
        y = float(self._y_spin.value())
        w = float(self._w_spin.value())
        h = float(self._h_spin.value())

        rect = pymupdf.Rect(x, y, x + w, y + h)

        if self._tabs.currentIndex() == 1 and self.draw_canvas.has_signature():
            cw = max(1.0, float(self.draw_canvas.width()))
            ch = max(1.0, float(self.draw_canvas.height()))
            scaled_strokes = [
                [(x + float(pt.x()) / cw * w, y + float(pt.y()) / ch * h) for pt in stroke]
                for stroke in self.draw_canvas._strokes
            ]
            ok = self.doc_mgr.add_visible_signature(
                page_idx, rect, signer_name=signer,
                signature_text=sig_text, drawn_strokes=scaled_strokes,
            )
        else:
            ok = self.doc_mgr.add_visible_signature(
                page_idx, rect, signer_name=signer,
                signature_text=sig_text, fontsize=fontsize,
            )

        if ok:
            self.signature_ready.emit(str(page_idx), signer, x, y, w, h, sig_text)
            if show_msg:
                QMessageBox.information(
                    self,
                    "Signature Placed",
                    f"Visible signature for '{signer}' placed on page {page_idx + 1}.\n\n"
                    "Remember to save a copy to persist this signature.",
                )
            self.accept()
        else:
            if show_msg:
                QMessageBox.critical(
                    self, "Signature Failed",
                    "Could not place the signature. Ensure a document is open."
                )

    def place_signature(self, show_msg: bool = False) -> None:
        """Programmatic helper to place signature."""
        self._on_place(show_msg=show_msg)


# =============================================================================
# 3. Stamp Dialog
# =============================================================================

class StampDialog(QDialog):
    """
    Dialog for selecting and placing a predefined rubber stamp on a PDF page.
    Stamps are embedded as PDF stamp annotations and persist on save.
    """

    stamp_placed = Signal()

    def __init__(
        self,
        doc_mgr: DocumentManager,
        current_page: Any = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        if isinstance(current_page, QWidget):
            parent = current_page
            current_page = 0
        super().__init__(parent)
        self.doc_mgr = doc_mgr
        self.current_page = int(current_page) if isinstance(current_page, (int, float)) else 0
        self.setWindowTitle("Add Stamp")
        self.resize(440, 480)
        self.setMinimumSize(360, 380)
        _apply_dialog_theme(self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        hdr = QLabel("Place Rubber Stamp")
        hdr.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #ffffff;")
        layout.addWidget(hdr)

        sub = QLabel("Select a stamp type and placement. The stamp is embedded in the PDF and persists on save.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(sub)

        # Stamp selector
        sel_grp = QGroupBox("Stamp Type")
        sel_layout = QVBoxLayout(sel_grp)
        sel_layout.setContentsMargins(10, 14, 10, 10)

        self.stamp_list = QListWidget()
        self.stamp_list.setMinimumHeight(160)
        for display_name in DocumentManager.USER_STAMPS.keys():
            item = QListWidgetItem(display_name)
            self.stamp_list.addItem(item)
        self.stamp_list.setCurrentRow(0)
        sel_layout.addWidget(self.stamp_list)
        layout.addWidget(sel_grp)

        # Placement
        place_grp = QGroupBox("Placement")
        place_form = QFormLayout(place_grp)
        place_form.setContentsMargins(10, 14, 10, 10)
        place_form.setSpacing(8)

        if self.doc_mgr.is_open:
            pages = [f"Page {i + 1}" for i in range(self.doc_mgr.page_count)]
        else:
            pages = ["Page 1"]
        self.page_combo = QComboBox()
        self.page_combo.addItems(pages)
        if 0 <= self.current_page < len(pages):
            self.page_combo.setCurrentIndex(self.current_page)
        place_form.addRow("Page:", self.page_combo)

        preset_row = QWidget()
        pr_layout = QHBoxLayout(preset_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Top Right", "Center", "Bottom Right", "Top Left", "Custom"])
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        pr_layout.addWidget(self.preset_combo)
        place_form.addRow("Preset:", preset_row)

        pos_row = QWidget()
        pr_layout = QHBoxLayout(pos_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(6)

        for label, attr, default in [("X:", "_sx", 350), ("Y:", "_sy", 40),
                                      ("W:", "_sw", 200), ("H:", "_sh", 60)]:
            pr_layout.addWidget(QLabel(label))
            sp = QSpinBox()
            sp.setRange(0, 5000)
            sp.setValue(default)
            sp.setFixedWidth(70)
            setattr(self, attr, sp)
            pr_layout.addWidget(sp)

        place_form.addRow("Position (pts):", pos_row)
        layout.addWidget(place_grp)

        # Buttons
        btn_box = QDialogButtonBox()
        btn_place = btn_box.addButton("Place Stamp", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_cancel = btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        btn_place.clicked.connect(self._on_place)
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_preset_changed(self, text: str) -> None:
        p_idx = self.page_combo.currentIndex()
        pw, ph = 595.0, 842.0
        if self.doc_mgr.is_open and 0 <= p_idx < self.doc_mgr.page_count:
            try:
                page = self.doc_mgr.doc[p_idx]
                pw, ph = float(page.rect.width), float(page.rect.height)
            except Exception:
                pass
        w = self._sw.value()
        h = self._sh.value()
        if text == "Top Right":
            self._sx.setValue(max(0, int(pw - w - 40)))
            self._sy.setValue(40)
        elif text == "Center":
            self._sx.setValue(max(0, int((pw - w) / 2)))
            self._sy.setValue(max(0, int((ph - h) / 2)))
        elif text == "Bottom Right":
            self._sx.setValue(max(0, int(pw - w - 40)))
            self._sy.setValue(max(0, int(ph - h - 50)))
        elif text == "Top Left":
            self._sx.setValue(40)
            self._sy.setValue(40)

    def _on_place(self, show_msg: bool = True) -> None:
        item = self.stamp_list.currentItem()
        if not item:
            QMessageBox.warning(self, "No Stamp", "Please select a stamp type.")
            return

        stamp_name = item.text()
        page_idx = self.page_combo.currentIndex()
        x = float(self._sx.value())
        y = float(self._sy.value())
        w = float(self._sw.value())
        h = float(self._sh.value())
        rect = pymupdf.Rect(x, y, x + w, y + h)

        ok = self.doc_mgr.add_stamp(page_idx, rect, stamp_name=stamp_name)
        if ok:
            self.stamp_placed.emit()
            if show_msg:
                QMessageBox.information(
                    self,
                    "Stamp Placed",
                    f"'{stamp_name}' stamp placed on page {page_idx + 1}.\n\n"
                    "Save a copy to persist this stamp.",
                )
            self.accept()
        else:
            if show_msg:
                QMessageBox.critical(
                    self, "Stamp Failed",
                    "Could not place the stamp. Ensure a document is open."
                )

    def place_stamp(self, show_msg: bool = False) -> None:
        """Programmatic helper to place stamp."""
        self._on_place(show_msg=show_msg)


# =============================================================================
# 4. Form Viewer / Fill Dialog
# =============================================================================

class FormViewerDialog(QDialog):
    """
    Dialog for inspecting and filling interactive PDF form fields (AcroForms).

    Supported field types:
    - Text fields (editable)
    - Checkboxes (toggle)
    - Radio buttons (text value)
    - Choice/Combo fields (editable)

    Unsupported field types are displayed as read-only for inspection.
    Field values are saved into the in-memory document when 'Apply' is clicked.
    Save a copy via File > Save Copy As to persist the filled form.
    """

    fields_applied = Signal()

    def __init__(
        self,
        doc_mgr: DocumentManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.doc_mgr = doc_mgr
        self._field_widgets: List[Tuple[int, str, QWidget]] = []
        # (page_index, field_name, input_widget)
        self.setWindowTitle("Fill & Inspect Form Fields")
        self.resize(600, 560)
        self.setMinimumSize(460, 380)
        _apply_dialog_theme(self)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        hdr = QLabel("Fill & Inspect Form Fields")
        hdr.setFont(QFont("sans-serif", 14, QFont.Weight.Bold))
        hdr.setStyleSheet("color: #ffffff;")
        layout.addWidget(hdr)

        if not self.doc_mgr.is_open:
            layout.addWidget(QLabel("No document is open."))
            layout.addWidget(QDialogButtonBox(QDialogButtonBox.StandardButton.Close))
            return

        if not self.doc_mgr.has_form_fields():
            no_form_lbl = QLabel(
                "This document does not contain interactive form fields.\n\n"
                "Open a PDF with AcroForm fields to use the Fill & Sign feature."
            )
            no_form_lbl.setWordWrap(True)
            no_form_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
            layout.addWidget(no_form_lbl)
            close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close_box.rejected.connect(self.reject)
            layout.addWidget(close_box)
            return

        sub = QLabel(
            "Edit the form fields below. Click 'Apply Fields' to write values into\n"
            "the document, then use File → Save Copy As to persist them."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(sub)

        # Scrollable field area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: 1px solid {Theme.BORDER_SUBTLE}; }}")
        field_container = QWidget()
        self._field_layout = QFormLayout(field_container)
        self._field_layout.setContentsMargins(12, 12, 12, 12)
        self._field_layout.setSpacing(10)
        self._field_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        all_fields = self.doc_mgr.get_all_form_fields()
        for p_idx in sorted(all_fields.keys()):
            fields = all_fields[p_idx]
            if not fields:
                continue
            # Section header per page
            page_sep = QLabel(f"── Page {p_idx + 1} ──")
            page_sep.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: 700; font-size: 11px;")
            self._field_layout.addRow("", page_sep)

            for fld in fields:
                ft = fld["field_type"]
                fname = fld["field_name"] or f"Field (xref={fld['xref']})"
                fval = fld["field_value"]
                ftype_str = fld["field_type_string"]

                label_text = f"{fname}\n({ftype_str})"
                label = QLabel(label_text)
                label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 11px;")
                label.setToolTip(f"Field: {fname}\nType: {ftype_str}\nPage: {p_idx + 1}")

                if ft == pymupdf.PDF_WIDGET_TYPE_TEXT:
                    widget = QLineEdit(str(fval) if fval is not None else "")
                    widget.setPlaceholderText(f"Enter value for {fname}")
                    self._field_widgets.append((p_idx, fname, widget))
                elif ft == pymupdf.PDF_WIDGET_TYPE_CHECKBOX:
                    widget = QCheckBox()
                    on_state = fld.get("on_state") or "Yes"
                    widget.setChecked(str(fval) == str(on_state))
                    widget.setText("Checked")
                    self._field_widgets.append((p_idx, fname, widget))
                elif ft in (pymupdf.PDF_WIDGET_TYPE_COMBOBOX, pymupdf.PDF_WIDGET_TYPE_LISTBOX):
                    choices = fld.get("choice_values", [])
                    if choices:
                        widget = QComboBox()
                        widget.addItems([str(c) for c in choices])
                        if fval and str(fval) in [str(c) for c in choices]:
                            widget.setCurrentText(str(fval))
                    else:
                        widget = QLineEdit(str(fval) if fval is not None else "")
                    self._field_widgets.append((p_idx, fname, widget))
                elif ft == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                    widget = QLineEdit(str(fval) if fval is not None else "")
                    widget.setToolTip("Radio button: enter the value to select")
                    self._field_widgets.append((p_idx, fname, widget))
                else:
                    # Read-only for unsupported types
                    widget = QLineEdit(str(fval) if fval is not None else "")
                    widget.setReadOnly(True)
                    widget.setToolTip(f"Field type '{ftype_str}' is read-only in this viewer")
                    widget.setStyleSheet(
                        f"background-color: {Theme.BG_CANVAS}; color: {Theme.TEXT_MUTED};"
                        "border: 1px solid #383b40; border-radius: 4px; padding: 4px 8px;"
                    )

                self._field_layout.addRow(label, widget)

        scroll.setWidget(field_container)
        layout.addWidget(scroll)

        # Button row
        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply Fields")
        self.apply_btn.setToolTip("Write current field values into the document (in memory)")
        self.apply_btn.clicked.connect(self._apply_fields)
        btn_row.addWidget(self.apply_btn)

        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @property
    def _entries(self) -> List[Tuple[int, str, QWidget]]:
        return self._field_widgets

    def _apply_fields(self, show_msg: bool = True) -> None:
        if not self.doc_mgr.is_open:
            return
        applied = 0
        for p_idx, fname, widget in self._field_widgets:
            try:
                if isinstance(widget, QCheckBox):
                    value = widget.isChecked()
                elif isinstance(widget, QComboBox):
                    value = widget.currentText()
                elif isinstance(widget, QLineEdit):
                    value = widget.text()
                else:
                    continue
                if self.doc_mgr.set_form_field_value(p_idx, fname, value):
                    applied += 1
            except Exception:
                pass

        self.fields_applied.emit()
        if show_msg:
            QMessageBox.information(
                self,
                "Fields Applied",
                f"Applied {applied} form field value(s) to the in-memory document.\n\n"
                "Use File → Save Copy As to save the filled form.",
            )

    def apply_all(self, show_msg: bool = False) -> None:
        """Programmatic helper to apply all form fields."""
        self._apply_fields(show_msg=show_msg)
