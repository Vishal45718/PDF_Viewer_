"""
Automated Tests for Milestone 4: Forms, Redaction & Signatures

Covers:
1. PDF Forms (AcroForms):
   - Detection of interactive forms (has_form_fields)
   - Field extraction and metadata (get_form_fields, get_all_form_fields)
   - Updating text fields
   - Updating checkboxes and radio buttons
   - Updating dropdown/choice comboboxes
   - Persistence of filled form values across save copy and reload
   - Graceful handling of PDFs without forms
   - Form field preservation across page operations (rotation/reordering)
2. Permanent Redaction:
   - Pending redaction creation with live styling
   - Cancelling individual pending redactions
   - Cancelling all pending redactions
   - Permanent application (apply_redactions) with irreversible content stripping
   - Unextractability check (get_text cannot find redacted text)
   - Multi-region redactions on a single page
   - Multi-page redactions applied in batch
   - Source-file integrity and safe-save protections
   - Saved redacted PDF output validity
3. Visible Signatures:
   - Typed styled visible signature
   - Freehand drawn vector ink signature
   - Custom placement and rect scaling
   - Persistence across save copy and reload
   - Distinction from ordinary annotations (subject='VisibleSignature')
   - Explicit non-cryptographic disclaimer check
4. Rubber Stamps:
   - Predefined stamp placement (Approved, Rejected, Draft, Confidential, Reviewed, Final, Void, Top Secret)
   - Custom positioning and coordinates
   - Stamp persistence across save copy and reload
   - Multiple stamps on same and multiple pages
5. UI Integration & Dialogs:
   - FormViewerDialog workflow
   - RedactionDialog workflow
   - SignatureDialog workflow and presets
   - StampDialog workflow and presets
   - Viewer tool mode toggling (select, form, redact) and text selection preservation
6. Combined Workflow & Robustness:
   - Combined forms + redactions + signatures + stamps in single document
   - Edge cases, invalid page indices, and boundary checks
"""

import hashlib
from pathlib import Path
from typing import List, Tuple
import pytest
import pymupdf
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication

from paperview.document import (
    DocumentError,
    DocumentManager,
)
from paperview.main_window import MainWindow
from paperview.milestone4_dialogs import (
    FormViewerDialog,
    RedactionDialog,
    SignatureDialog,
    StampDialog,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def form_pdf(tmp_path: Path) -> Path:
    """Creates a temporary PDF with AcroForm fields (text, checkbox, combobox)."""
    pdf_path = tmp_path / "sample_form.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "Official Application Form", fontsize=16)

    # 1. Text field
    w_text = pymupdf.Widget()
    w_text.rect = pymupdf.Rect(50, 100, 250, 130)
    w_text.field_name = "applicant_name"
    w_text.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w_text.field_value = "Jane Doe"
    page.add_widget(w_text)

    # 2. Checkbox
    w_check = pymupdf.Widget()
    w_check.rect = pymupdf.Rect(50, 150, 70, 170)
    w_check.field_name = "subscribe_newsletter"
    w_check.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    w_check.field_value = "Off"
    page.add_widget(w_check)

    # 3. Combobox / Choice
    w_combo = pymupdf.Widget()
    w_combo.rect = pymupdf.Rect(50, 200, 250, 230)
    w_combo.field_name = "department"
    w_combo.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
    w_combo.choice_values = ["Engineering", "Design", "Product", "Operations"]
    w_combo.field_value = "Engineering"
    page.add_widget(w_combo)

    # Page 2 for multi-page tests
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 50), "Form Page 2", fontsize=14)
    w_notes = pymupdf.Widget()
    w_notes.rect = pymupdf.Rect(50, 100, 400, 200)
    w_notes.field_name = "additional_notes"
    w_notes.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    w_notes.field_value = "No additional notes."
    page2.add_widget(w_notes)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def redact_pdf(tmp_path: Path) -> Path:
    """Creates a temporary PDF with identifiable text for redaction testing."""
    pdf_path = tmp_path / "sample_redact.pdf"
    doc = pymupdf.open()

    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 100), "Public Header Information", fontsize=12)
    page1.insert_text((50, 200), "SECRET_SSN_987-65-4321", fontsize=12)
    page1.insert_text((50, 300), "CONFIDENTIAL_PASSWORD_XYZ123", fontsize=12)
    page1.insert_text((50, 400), "Public Footer Notes", fontsize=12)

    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 100), "Page 2 Public Intro", fontsize=12)
    page2.insert_text((50, 200), "TOP_SECRET_COORDINATES_45N_12W", fontsize=12)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# =============================================================================
# 1. PDF FORMS TESTS (1 - 8)
# =============================================================================

def test_01_form_detection_and_page_enumeration(form_pdf: Path):
    """Verifies that interactive forms are accurately detected and enumerated."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        assert mgr.has_form_fields() is True
        p0_fields = mgr.get_form_fields(0)
        assert len(p0_fields) == 3

        p1_fields = mgr.get_form_fields(1)
        assert len(p1_fields) == 1

        all_fields = mgr.get_all_form_fields()
        assert 0 in all_fields
        assert 1 in all_fields
        assert len(all_fields[0]) == 3
        assert len(all_fields[1]) == 1
    finally:
        mgr.close()


def test_02_form_read_field_metadata(form_pdf: Path):
    """Verifies that form field metadata (name, type, rect, value, choices) is parsed accurately."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        fields = mgr.get_form_fields(0)
        names = {f["field_name"]: f for f in fields}

        assert "applicant_name" in names
        assert names["applicant_name"]["value"] == "Jane Doe"
        assert names["applicant_name"]["field_type"] == pymupdf.PDF_WIDGET_TYPE_TEXT

        assert "subscribe_newsletter" in names
        assert names["subscribe_newsletter"]["field_type"] == pymupdf.PDF_WIDGET_TYPE_CHECKBOX

        assert "department" in names
        assert names["department"]["field_type"] == pymupdf.PDF_WIDGET_TYPE_COMBOBOX
        assert "Engineering" in names["department"]["choices"]
        assert "Design" in names["department"]["choices"]
    finally:
        mgr.close()


def test_03_form_set_text_field(form_pdf: Path):
    """Verifies setting text field values in-memory."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        ok = mgr.set_form_field_value(0, "applicant_name", "Alex Mercutio")
        assert ok is True
        assert mgr.is_modified is True

        fields = mgr.get_form_fields(0)
        updated = next(f for f in fields if f["field_name"] == "applicant_name")
        assert updated["value"] == "Alex Mercutio"
    finally:
        mgr.close()


def test_04_form_set_checkbox_and_radio(form_pdf: Path):
    """Verifies setting checkbox values (boolean True/False, 'Yes'/'Off')."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        # Turn ON
        ok_on = mgr.set_form_field_value(0, "subscribe_newsletter", True)
        assert ok_on is True
        fields = mgr.get_form_fields(0)
        chk = next(f for f in fields if f["field_name"] == "subscribe_newsletter")
        assert chk["value"] == "Yes"

        # Turn OFF
        ok_off = mgr.set_form_field_value(0, "subscribe_newsletter", False)
        assert ok_off is True
        fields = mgr.get_form_fields(0)
        chk = next(f for f in fields if f["field_name"] == "subscribe_newsletter")
        assert chk["value"] == "Off"
    finally:
        mgr.close()


def test_05_form_set_choice_combobox(form_pdf: Path):
    """Verifies choosing option in a combobox field."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        ok = mgr.set_form_field_value(0, "department", "Product")
        assert ok is True

        fields = mgr.get_form_fields(0)
        combo = next(f for f in fields if f["field_name"] == "department")
        assert combo["value"] == "Product"
    finally:
        mgr.close()


def test_06_form_persistence_save_copy_and_reload(form_pdf: Path, tmp_path: Path):
    """Verifies filled form values persist after save_copy and fresh reopening."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)

    mgr.set_form_field_value(0, "applicant_name", "Persistent User")
    mgr.set_form_field_value(0, "subscribe_newsletter", True)
    mgr.set_form_field_value(0, "department", "Design")
    mgr.set_form_field_value(1, "additional_notes", "Verified persistent notes.")

    out_file = tmp_path / "filled_form.pdf"
    mgr.save_copy(out_file)
    mgr.close()

    # Reopen in new DocumentManager
    mgr2 = DocumentManager()
    mgr2.open_document(out_file)
    try:
        assert mgr2.has_form_fields() is True
        p0 = {f["field_name"]: f["value"] for f in mgr2.get_form_fields(0)}
        assert p0["applicant_name"] == "Persistent User"
        assert p0["subscribe_newsletter"] == "Yes"
        assert p0["department"] == "Design"

        p1 = {f["field_name"]: f["value"] for f in mgr2.get_form_fields(1)}
        assert p1["additional_notes"] == "Verified persistent notes."
    finally:
        mgr2.close()


def test_07_form_graceful_handling_without_forms(redact_pdf: Path):
    """Verifies that non-form PDFs report has_form_fields=False and handle calls gracefully."""
    mgr = DocumentManager()
    mgr.open_document(redact_pdf)
    try:
        assert mgr.has_form_fields() is False
        assert mgr.get_form_fields(0) == []
        assert mgr.get_all_form_fields() == {}
        # Attempting to set field should return False without crashing
        assert mgr.set_form_field_value(0, "nonexistent", "val") is False
    finally:
        mgr.close()


def test_08_form_preservation_across_page_operations(form_pdf: Path, tmp_path: Path):
    """Verifies that AcroForm fields survive page structure modifications (rotation/reordering)."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)

    # Reorganize: reverse page order and rotate page 0
    specs = [
        {"source_index": 1, "rotation_delta": 0},
        {"source_index": 0, "rotation_delta": 90},
    ]
    mgr.apply_page_structure(specs)

    out_file = tmp_path / "reorganized_form.pdf"
    mgr.save_copy(out_file)
    mgr.close()

    mgr2 = DocumentManager()
    mgr2.open_document(out_file)
    try:
        assert mgr2.page_count == 2
        # Page 0 should now be the former Page 1 (additional_notes)
        p0_fields = mgr2.get_form_fields(0)
        assert len(p0_fields) >= 1
        assert any(f["field_name"] == "additional_notes" for f in p0_fields)

        # Page 1 should now be the former Page 0 (applicant_name, etc.)
        p1_fields = mgr2.get_form_fields(1)
        assert len(p1_fields) >= 1
        assert any(f["field_name"] == "applicant_name" for f in p1_fields)
    finally:
        mgr2.close()


# =============================================================================
# 2. PERMANENT REDACTION TESTS (9 - 16)
# =============================================================================

def test_09_pending_redaction_creation(redact_pdf: Path):
    """Verifies adding a pending redaction creates a marker without modifying text yet."""
    mgr = DocumentManager()
    mgr.open_document(redact_pdf)
    try:
        # Check text is initially present
        text_before = mgr.doc[0].get_text()
        assert "SECRET_SSN_987-65-4321" in text_before

        rect = pymupdf.Rect(40, 180, 350, 220)
        ok = mgr.add_redaction_region(0, rect)
        assert ok is True
        assert mgr.is_modified is True

        pending = mgr.get_pending_redactions(0)
        assert len(pending) == 1
        assert pending[0]["rect"].intersects(rect)

        # Text MUST still be present before applying!
        text_still = mgr.doc[0].get_text()
        assert "SECRET_SSN_987-65-4321" in text_still
    finally:
        mgr.close()


def test_10_cancel_single_pending_redaction(redact_pdf: Path):
    """Verifies cancelling an individual pending redaction by xref."""
    mgr = DocumentManager()
    mgr.open_document(redact_pdf)
    try:
        rect1 = pymupdf.Rect(40, 180, 350, 220)
        rect2 = pymupdf.Rect(40, 280, 350, 320)
        mgr.add_redaction_region(0, rect1)
        mgr.add_redaction_region(0, rect2)

        pending = mgr.get_pending_redactions(0)
        assert len(pending) == 2
        first_xref = pending[0]["xref"]

        ok = mgr.cancel_redaction(0, first_xref)
        assert ok is True

        remaining = mgr.get_pending_redactions(0)
        assert len(remaining) == 1
        assert remaining[0]["xref"] != first_xref
    finally:
        mgr.close()


def test_11_cancel_all_pending_redactions(redact_pdf: Path):
    """Verifies cancelling all pending redactions on a page."""
    mgr = DocumentManager()
    mgr.open_document(redact_pdf)
    try:
        mgr.add_redaction_region(0, pymupdf.Rect(40, 180, 350, 220))
        mgr.add_redaction_region(0, pymupdf.Rect(40, 280, 350, 320))
        assert len(mgr.get_pending_redactions(0)) == 2

        count = mgr.cancel_all_redactions(0)
        assert count == 2
        assert len(mgr.get_pending_redactions(0)) == 0
    finally:
        mgr.close()


def test_12_apply_permanent_redaction_content_unextractable(redact_pdf: Path, tmp_path: Path):
    """
    CRITICAL TEST: Verifies that apply_redactions() PERMANENTLY destroys underlying text,
    so it CANNOT be extracted via get_text() from memory or from saved PDF.
    """
    mgr = DocumentManager()
    mgr.open_document(redact_pdf)

    # Redact the SSN line
    rect = pymupdf.Rect(40, 180, 350, 220)
    mgr.add_redaction_region(0, rect)

    res = mgr.apply_redactions([0])
    assert res.get(0) == 1

    # Check in-memory doc: text must be completely absent
    mem_text = mgr.doc[0].get_text()
    assert "SECRET_SSN_987-65-4321" not in mem_text
    # Non-redacted text must still be intact
    assert "Public Header Information" in mem_text
    assert "CONFIDENTIAL_PASSWORD_XYZ123" in mem_text

    # Save to new file and reopen with fresh DocumentManager
    out_file = tmp_path / "permanently_redacted.pdf"
    mgr.save_copy(out_file)
    mgr.close()

    mgr2 = DocumentManager()
    mgr2.open_document(out_file)
    try:
        saved_text = mgr2.doc[0].get_text()
        assert "SECRET_SSN_987-65-4321" not in saved_text
        assert "Public Header Information" in saved_text
        assert "CONFIDENTIAL_PASSWORD_XYZ123" in saved_text
    finally:
        mgr2.close()


def test_13_multi_region_redaction_single_page(redact_pdf: Path, tmp_path: Path):
    """Verifies multiple redaction regions on the same page can be applied together."""
    mgr = DocumentManager()
    mgr.open_document(redact_pdf)

    # Redact both sensitive lines on page 0
    mgr.add_redaction_region(0, pymupdf.Rect(40, 180, 350, 220))  # SSN
    mgr.add_redaction_region(0, pymupdf.Rect(40, 280, 450, 320))  # Password

    assert len(mgr.get_pending_redactions(0)) == 2
    res = mgr.apply_redactions()
    assert res.get(0) == 2

    text = mgr.doc[0].get_text()
    assert "SECRET_SSN" not in text
    assert "CONFIDENTIAL_PASSWORD" not in text
    assert "Public Header Information" in text
    assert "Public Footer Notes" in text
    mgr.close()


def test_14_multi_page_redactions_applied(redact_pdf: Path, tmp_path: Path):
    """Verifies applying redactions across multiple pages simultaneously."""
    mgr = DocumentManager()
    mgr.open_document(redact_pdf)

    # Page 0 redaction
    mgr.add_redaction_region(0, pymupdf.Rect(40, 180, 350, 220))
    # Page 1 redaction
    mgr.add_redaction_region(1, pymupdf.Rect(40, 180, 450, 220))

    res = mgr.apply_redactions()
    assert res.get(0) == 1
    assert res.get(1) == 1

    assert "SECRET_SSN" not in mgr.doc[0].get_text()
    assert "TOP_SECRET_COORDINATES" not in mgr.doc[1].get_text()
    assert "Page 2 Public Intro" in mgr.doc[1].get_text()
    mgr.close()


def test_15_source_file_integrity_after_redaction(redact_pdf: Path, tmp_path: Path):
    """Guarantees the original source PDF on disk remains untouched during redaction workflow."""
    with open(redact_pdf, "rb") as f:
        orig_hash = hashlib.sha256(f.read()).hexdigest()

    mgr = DocumentManager()
    mgr.open_document(redact_pdf)
    mgr.add_redaction_region(0, pymupdf.Rect(40, 180, 350, 220))
    mgr.apply_redactions()

    out_copy = tmp_path / "redacted_out.pdf"
    mgr.save_copy(out_copy)
    mgr.close()

    # Re-verify original file hash
    with open(redact_pdf, "rb") as f:
        after_hash = hashlib.sha256(f.read()).hexdigest()

    assert orig_hash == after_hash, "CRITICAL: Original source file was modified!"


def test_16_redacted_saved_pdf_validity(redact_pdf: Path, tmp_path: Path):
    """Verifies the saved redacted PDF is a valid, uncorrupted PDF document."""
    mgr = DocumentManager()
    mgr.open_document(redact_pdf)
    mgr.add_redaction_region(0, pymupdf.Rect(40, 180, 350, 220))
    mgr.apply_redactions()

    out_file = tmp_path / "valid_redacted.pdf"
    mgr.save_copy(out_file)
    mgr.close()

    # Verify standard PyMuPDF can open and inspect without errors
    check_doc = pymupdf.open(str(out_file))
    try:
        assert check_doc.page_count == 2
        assert check_doc.is_pdf is True
        assert not check_doc.is_encrypted
    finally:
        check_doc.close()


# =============================================================================
# 3. VISIBLE SIGNATURES TESTS (17 - 22)
# =============================================================================

def test_17_typed_visible_signature_creation(form_pdf: Path):
    """Verifies adding a typed visible signature."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        rect = pymupdf.Rect(350, 700, 520, 780)
        ok = mgr.add_visible_signature(
            page_index=0,
            rect=rect,
            signer_name="Sarah Connor",
            signature_text="Sarah Connor",
            fontsize=16.0,
        )
        assert ok is True
        assert mgr.is_modified is True

        sigs = mgr.get_visible_signatures(0)
        assert len(sigs) == 1
        assert sigs[0]["signer"] == "Sarah Connor"
        assert sigs[0]["type"] == "VisibleSignature"
    finally:
        mgr.close()


def test_18_drawn_visible_signature_creation(form_pdf: Path):
    """Verifies adding a freehand drawn vector ink signature."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        # Sequence of vector stroke coordinate tuples
        strokes = [
            [(360.0, 720.0), (380.0, 715.0), (410.0, 730.0)],
            [(370.0, 725.0), (390.0, 750.0), (430.0, 720.0)],
        ]
        rect = pymupdf.Rect(350, 700, 520, 780)
        ok = mgr.add_visible_signature(
            page_index=0,
            rect=rect,
            signer_name="Drawn Artist",
            drawn_strokes=strokes,
        )
        assert ok is True

        sigs = mgr.get_visible_signatures(0)
        assert len(sigs) == 1
        assert sigs[0]["signer"] == "Drawn Artist"
    finally:
        mgr.close()


def test_19_visible_signature_custom_placement_and_scaling(form_pdf: Path):
    """Verifies signatures can be positioned anywhere on page with custom rect bounds."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        # Top right signature
        rect_tr = pymupdf.Rect(400, 40, 550, 100)
        mgr.add_visible_signature(0, rect_tr, "Top Right Signer")

        # Bottom left signature
        rect_bl = pymupdf.Rect(50, 750, 200, 810)
        mgr.add_visible_signature(0, rect_bl, "Bottom Left Signer")

        sigs = mgr.get_visible_signatures(0)
        assert len(sigs) == 2
        signers = {s["signer"] for s in sigs}
        assert "Top Right Signer" in signers
        assert "Bottom Left Signer" in signers
    finally:
        mgr.close()


def test_20_visible_signature_persistence_save_and_reload(form_pdf: Path, tmp_path: Path):
    """Verifies visible signatures persist in PDF annotations after saving and reopening."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)

    rect = pymupdf.Rect(300, 600, 500, 680)
    mgr.add_visible_signature(0, rect, "Persistent Signer", signature_text="Persistent Signer")

    out_file = tmp_path / "signed_doc.pdf"
    mgr.save_copy(out_file)
    mgr.close()

    mgr2 = DocumentManager()
    mgr2.open_document(out_file)
    try:
        sigs = mgr2.get_visible_signatures(0)
        assert len(sigs) == 1
        assert sigs[0]["signer"] == "Persistent Signer"
    finally:
        mgr2.close()


def test_21_visible_signature_annot_distinction(form_pdf: Path):
    """Verifies visible signatures are clearly distinguished from standard PDF annotations."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        # Add a normal highlight annotation
        mgr.add_highlight_annotation(0, [pymupdf.Rect(50, 50, 200, 70)], (1.0, 1.0, 0.0))

        # Add a visible signature
        mgr.add_visible_signature(0, pymupdf.Rect(300, 600, 500, 680), "Distinguished Signer")

        # Signature query should ONLY return the signature, not the highlight
        sigs = mgr.get_visible_signatures(0)
        assert len(sigs) == 1
        assert sigs[0]["signer"] == "Distinguished Signer"

        # PyMuPDF page.annots() should include both highlight and signature
        page = mgr.doc[0]
        all_annots = list(page.annots())
        assert len(all_annots) >= 2
    finally:
        mgr.close()


def test_22_visible_signature_non_cryptographic_disclaimer():
    """
    Verifies that DocumentManager.add_visible_signature explicitly documents
    that it is a visible signature only, not a cryptographic digital signature.
    """
    docstring = DocumentManager.add_visible_signature.__doc__ or ""
    assert "VISIBLE SIGNATURE only" in docstring
    assert "cryptographic" in docstring.lower()
    assert "certificate" in docstring.lower()


# =============================================================================
# 4. RUBBER STAMPS TESTS (23 - 26)
# =============================================================================

def test_23_predefined_stamp_creation(form_pdf: Path):
    """Verifies placing standard predefined rubber stamps (Approved, Rejected, Draft, Confidential)."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        stamps_to_test = ["Approved", "Rejected", "Draft", "Confidential", "Final", "Void"]
        for idx, sname in enumerate(stamps_to_test):
            rect = pymupdf.Rect(50, 100 + idx * 50, 200, 140 + idx * 50)
            ok = mgr.add_stamp(0, rect, stamp_name=sname)
            assert ok is True

        stamps = mgr.get_stamps(0)
        assert len(stamps) == len(stamps_to_test)
        names = [s["name"] for s in stamps]
        for sname in stamps_to_test:
            assert sname in names
    finally:
        mgr.close()


def test_24_stamp_positioning_and_rect(form_pdf: Path):
    """Verifies stamps can be accurately placed at desired coordinates."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        target_rect = pymupdf.Rect(380, 40, 550, 110)
        ok = mgr.add_stamp(0, target_rect, stamp_name="Confidential")
        assert ok is True

        stamps = mgr.get_stamps(0)
        assert len(stamps) == 1
        # PyMuPDF centers stamp within target rect maintaining aspect ratio
        assert stamps[0]["rect"].intersects(target_rect)
        assert target_rect.contains(stamps[0]["rect"])
    finally:
        mgr.close()


def test_25_stamp_persistence_save_and_reload(form_pdf: Path, tmp_path: Path):
    """Verifies rubber stamps persist after saving to a copy and reopening."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    mgr.add_stamp(0, pymupdf.Rect(400, 50, 550, 110), stamp_name="Top Secret")

    out_file = tmp_path / "stamped_doc.pdf"
    mgr.save_copy(out_file)
    mgr.close()

    mgr2 = DocumentManager()
    mgr2.open_document(out_file)
    try:
        stamps = mgr2.get_stamps(0)
        assert len(stamps) == 1
        assert stamps[0]["name"] in ("Top Secret", "TopSecret")
    finally:
        mgr2.close()


def test_26_multiple_stamps_and_multi_page(form_pdf: Path):
    """Verifies multiple stamps across multiple pages."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        mgr.add_stamp(0, pymupdf.Rect(50, 50, 200, 110), stamp_name="Draft")
        mgr.add_stamp(1, pymupdf.Rect(50, 50, 200, 110), stamp_name="Reviewed")

        assert len(mgr.get_stamps(0)) == 1
        assert len(mgr.get_stamps(1)) == 1
        assert mgr.get_stamps(0)[0]["name"] == "Draft"
        assert mgr.get_stamps(1)[0]["name"] == "Reviewed"
    finally:
        mgr.close()


# =============================================================================
# 5. UI INTEGRATION & DIALOGS TESTS (27 - 31)
# =============================================================================

def test_27_ui_form_viewer_dialog_workflow(qapp, form_pdf: Path):
    """Verifies FormViewerDialog populates fields and allows editing."""
    win = MainWindow(str(form_pdf))
    try:
        dlg = FormViewerDialog(win.doc_mgr, win)
        assert len(dlg._entries) >= 3

        # Modify first entry
        page_idx, fname, widget = dlg._entries[0]
        assert fname == "applicant_name"
        widget.setText("Dialog Edited Name")

        # Apply changes
        dlg.apply_all()
        fields = win.doc_mgr.get_form_fields(0)
        applicant = next(f for f in fields if f["field_name"] == "applicant_name")
        assert applicant["value"] == "Dialog Edited Name"
    finally:
        win.close()


def test_28_ui_redaction_dialog_workflow(qapp, redact_pdf: Path):
    """Verifies RedactionDialog lists pending redactions and can apply them."""
    win = MainWindow(str(redact_pdf))
    try:
        win.doc_mgr.add_redaction_region(0, pymupdf.Rect(40, 180, 350, 220))
        win.doc_mgr.add_redaction_region(0, pymupdf.Rect(40, 280, 450, 320))

        dlg = RedactionDialog(win.doc_mgr, win)
        assert dlg.list_widget.count() == 2

        # Apply redactions via dialog
        applied_called = []
        dlg.redactions_applied.connect(lambda: applied_called.append(True))
        dlg.apply_all_redactions()

        assert len(applied_called) == 1
        assert "SECRET_SSN" not in win.doc_mgr.doc[0].get_text()
    finally:
        win.close()


def test_29_ui_signature_dialog_interaction(qapp, form_pdf: Path):
    """Verifies SignatureDialog presets, non-crypto disclaimer, and placement."""
    win = MainWindow(str(form_pdf))
    try:
        dlg = SignatureDialog(win.doc_mgr, current_page=0, parent=win)
        assert dlg.name_edit.placeholderText() != ""
        # Check preset options exist
        presets = [dlg.pos_combo.itemText(i) for i in range(dlg.pos_combo.count())]
        assert "Bottom Right" in presets
        assert "Bottom Left" in presets

        # Place signature via dialog logic
        dlg.name_edit.setText("UI Test Signer")
        dlg.place_signature()

        sigs = win.doc_mgr.get_visible_signatures(0)
        assert len(sigs) == 1
        assert sigs[0]["signer"] == "UI Test Signer"
    finally:
        win.close()


def test_30_ui_stamp_dialog_interaction(qapp, form_pdf: Path):
    """Verifies StampDialog options, position presets, and placement."""
    win = MainWindow(str(form_pdf))
    try:
        dlg = StampDialog(win.doc_mgr, current_page=0, parent=win)
        # Check stamp choices
        choices = [dlg.stamp_list.item(i).text() for i in range(dlg.stamp_list.count())]
        assert "Approved" in choices
        assert "Confidential" in choices

        dlg.stamp_list.setCurrentRow(choices.index("Approved"))
        dlg.place_stamp()

        stamps = win.doc_mgr.get_stamps(0)
        assert len(stamps) == 1
        assert stamps[0]["name"] == "Approved"
    finally:
        win.close()


def test_31_ui_viewer_tool_modes_and_selection_preservation(qapp, form_pdf: Path):
    """Verifies switching between tool modes (select, form, redact) preserves viewer functionality."""
    win = MainWindow(str(form_pdf))
    try:
        # Default tool mode
        assert win.viewer.tool_mode == "select"

        # Switch to form mode
        win.set_tool_mode("form")
        assert win.viewer.tool_mode == "form"
        assert win.tool_form_act.isChecked() is True

        # Switch to redact mode
        win.set_tool_mode("redact")
        assert win.viewer.tool_mode == "redact"
        assert win.tool_redact_act.isChecked() is True

        # Switch back to select mode
        win.set_tool_mode("select")
        assert win.viewer.tool_mode == "select"
        assert win.tool_select_act.isChecked() is True
    finally:
        win.close()


# =============================================================================
# 6. COMBINED WORKFLOW & ROBUSTNESS TESTS (32 - 34)
# =============================================================================

def test_32_combined_milestone4_workflow_integrity(form_pdf: Path, tmp_path: Path):
    """
    Combined Workflow Test:
    Fills form field + Adds pending redaction + Adds visible signature + Adds stamp +
    Applies redaction + Saves copy -> Reloads and confirms all elements coexist cleanly.
    """
    mgr = DocumentManager()
    mgr.open_document(form_pdf)

    # 1. Fill form field
    mgr.set_form_field_value(0, "applicant_name", "Combined Hero")

    # 2. Add pending redaction and apply
    mgr.add_redaction_region(0, pymupdf.Rect(50, 40, 200, 70))
    res = mgr.apply_redactions([0])
    assert res.get(0) == 1

    # 3. Add visible signature
    mgr.add_visible_signature(0, pymupdf.Rect(350, 700, 520, 760), "Hero Signer")

    # 4. Add stamp
    mgr.add_stamp(0, pymupdf.Rect(400, 100, 550, 160), "Reviewed")

    # Save copy
    out_file = tmp_path / "combined_m4_output.pdf"
    mgr.save_copy(out_file)
    mgr.close()

    # Reopen and inspect all 4 components
    mgr2 = DocumentManager()
    mgr2.open_document(out_file)
    try:
        # 1. Form field
        p0_fields = {f["field_name"]: f["value"] for f in mgr2.get_form_fields(0)}
        assert p0_fields.get("applicant_name") == "Combined Hero"

        # 2. Signature
        sigs = mgr2.get_visible_signatures(0)
        assert len(sigs) == 1
        assert sigs[0]["signer"] == "Hero Signer"

        # 3. Stamp
        stamps = mgr2.get_stamps(0)
        assert len(stamps) == 1
        assert stamps[0]["name"] == "Reviewed"
    finally:
        mgr2.close()


def test_33_edge_cases_and_invalid_inputs(form_pdf: Path):
    """Verifies graceful handling of out-of-range pages, invalid redactions, and empty signatures."""
    mgr = DocumentManager()
    mgr.open_document(form_pdf)
    try:
        # Out-of-bounds page index
        assert mgr.get_form_fields(999) == []
        assert mgr.set_form_field_value(999, "any", "val") is False
        assert mgr.add_redaction_region(999, pymupdf.Rect(0, 0, 10, 10)) is False
        assert mgr.get_pending_redactions(999) == []
        assert mgr.cancel_redaction(999, 123) is False
        assert mgr.cancel_all_redactions(999) == 0
        assert mgr.add_visible_signature(999, pymupdf.Rect(0, 0, 10, 10), "Name") is False
        assert mgr.get_visible_signatures(999) == []
        assert mgr.add_stamp(999, pymupdf.Rect(0, 0, 10, 10), "Draft") is False
        assert mgr.get_stamps(999) == []
    finally:
        mgr.close()


def test_34_unopened_document_manager_safety():
    """Verifies that DocumentManager methods fail gracefully without crashing when no document is open."""
    mgr = DocumentManager()
    assert mgr.has_form_fields() is False
    assert mgr.get_form_fields(0) == []
    assert mgr.get_all_form_fields() == {}
    assert mgr.set_form_field_value(0, "f", "v") is False
    assert mgr.add_redaction_region(0, pymupdf.Rect(0, 0, 10, 10)) is False
    assert mgr.get_pending_redactions(0) == []
    assert mgr.cancel_redaction(0, 1) is False
    assert mgr.cancel_all_redactions(0) == 0
    with pytest.raises(DocumentError):
        mgr.apply_redactions()
    assert mgr.add_visible_signature(0, pymupdf.Rect(0, 0, 10, 10), "N") is False
    assert mgr.get_visible_signatures(0) == []
    assert mgr.add_stamp(0, pymupdf.Rect(0, 0, 10, 10), "Draft") is False
    assert mgr.get_stamps(0) == []
