"""
Automated Tests for Milestone 3:
1. Page rotation and ordering.
2. Page deletion, duplication, and extraction.
3. PDF merge and range-based split.
4. Invalid input and invalid ranges handling.
5. Watermark persistence after saving and reopening.
6. Optimization output validity and metric reporting.
7. Preservation of annotations where supported.
8. Source-file integrity and save-path safeguards.
9. Application UI workflow and dialog integration.
"""

import hashlib
from pathlib import Path
import pytest
import pymupdf
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from paperview.document import (
    DocumentError,
    DocumentManager,
    PasswordRequiredError,
)
from paperview.main_window import MainWindow
from paperview.operations_dialogs import (
    MergePDFsDialog,
    OptimizePDFDialog,
    SplitPDFDialog,
    WatermarkDialog,
)
from paperview.organize_dialog import OrganizePagesDialog, PageThumbnailItem


SAMPLE_RESUME = "/home/jonsnow/Desktop/Resume_CV.pdf"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_page_rotation_and_ordering():
    """Verifies page rotation (clockwise & counterclockwise) and reordering."""
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)
    initial_pages = mgr.page_count
    assert initial_pages >= 2

    # Rotate page 0 clockwise (+90)
    rot1 = mgr.rotate_page(0, 90)
    assert rot1 == 90
    assert mgr.doc[0].rotation == 90
    assert mgr.is_modified

    # Rotate page 0 counterclockwise (-90)
    rot2 = mgr.rotate_page(0, -90)
    assert rot2 == 0
    assert mgr.doc[0].rotation == 0

    # Reorder pages: reverse order
    new_order = list(range(initial_pages))[::-1]
    text_before_p0 = mgr.get_page_text(0)[:30]
    text_before_last = mgr.get_page_text(initial_pages - 1)[:30]

    assert mgr.reorder_pages(new_order) is True
    # Now page 0 should have the text of the old last page
    assert mgr.get_page_text(0)[:30] == text_before_last
    assert mgr.get_page_text(initial_pages - 1)[:30] == text_before_p0

    # Invalid permutation must be rejected
    with pytest.raises(DocumentError, match="Invalid page order"):
        mgr.reorder_pages([0, 0])

    mgr.close()


def test_page_deletion_duplication_and_extraction(tmp_path):
    """Verifies page duplication, extraction to new PDF, and deletion guards."""
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)
    orig_count = mgr.page_count

    # 1. Duplicate page 0
    new_idx = mgr.duplicate_page(0)
    assert new_idx == 1
    assert mgr.page_count == orig_count + 1
    assert mgr.doc.page_count == orig_count + 1

    # 2. Extract selected pages to a new PDF
    extract_dest = tmp_path / "extracted_subset.pdf"
    res = mgr.extract_pages([0, 1], extract_dest)
    assert res == extract_dest
    assert extract_dest.is_file()

    # Verify extracted PDF structure
    ext_doc = pymupdf.open(str(extract_dest))
    assert ext_doc.page_count == 2
    ext_doc.close()

    # Guard: Cannot extract into active source
    with pytest.raises(DocumentError, match="Cannot extract into the active source"):
        mgr.extract_pages([0], SAMPLE_RESUME)

    # 3. Delete duplicated page
    assert mgr.delete_pages([1]) is True
    assert mgr.page_count == orig_count

    # 4. Guard: Cannot delete all pages in document
    all_pages = list(range(mgr.page_count))
    with pytest.raises(DocumentError, match="Cannot delete all pages"):
        mgr.delete_pages(all_pages)

    mgr.close()


def test_pdf_merge_and_guards(tmp_path):
    """Verifies merging multiple PDFs with order preservation and source guards."""
    # Create two distinct test PDFs
    pdf1 = tmp_path / "doc_alpha.pdf"
    doc1 = pymupdf.open()
    p1 = doc1.new_page()
    p1.insert_text((50, 50), "ALPHA DOCUMENT CONTENT")
    doc1.set_toc([[1, "Alpha Section", 1]])
    doc1.save(str(pdf1))
    doc1.close()

    pdf2 = tmp_path / "doc_beta.pdf"
    doc2 = pymupdf.open()
    p2 = doc2.new_page()
    p2.insert_text((50, 50), "BETA DOCUMENT CONTENT")
    doc2.set_toc([[1, "Beta Section", 1]])
    doc2.save(str(pdf2))
    doc2.close()

    # Merge into destination
    merged_dest = tmp_path / "combined_output.pdf"
    saved = DocumentManager.merge_pdfs([pdf1, pdf2], merged_dest)
    assert saved == merged_dest
    assert merged_dest.is_file()

    # Inspect merged PDF
    merged_doc = pymupdf.open(str(merged_dest))
    assert merged_doc.page_count == 2
    assert "ALPHA DOCUMENT" in merged_doc[0].get_text()
    assert "BETA DOCUMENT" in merged_doc[1].get_text()

    # Verify TOC remapped with offsets
    toc = merged_doc.get_toc()
    assert len(toc) == 2
    assert toc[0][1] == "Alpha Section"
    assert toc[0][2] == 1
    assert toc[1][1] == "Beta Section"
    assert toc[1][2] == 2  # Offset by 1 page
    merged_doc.close()

    # Guard: Cannot overwrite one of the source inputs
    with pytest.raises(DocumentError, match="cannot overwrite input file"):
        DocumentManager.merge_pdfs([pdf1, pdf2], pdf1)


def test_split_pdf_and_range_parsing(tmp_path):
    """Verifies page range parsing, validation of invalid ranges, and splitting."""
    total_pages = 5

    # 1. Valid range parsing
    r1 = DocumentManager.parse_page_ranges("1-2, 4, 5", total_pages)
    assert r1 == [[0, 1], [3], [4]]

    # All pages keyword
    r_all = DocumentManager.parse_page_ranges("all", total_pages)
    assert len(r_all) == 5
    assert r_all[0] == [0]

    # 2. Invalid range inputs rejected with informative ValueErrors
    with pytest.raises(ValueError, match="cannot be empty"):
        DocumentManager.parse_page_ranges("", total_pages)

    with pytest.raises(ValueError, match="must be >= 1"):
        DocumentManager.parse_page_ranges("0-3", total_pages)

    with pytest.raises(ValueError, match="exceeds total pages"):
        DocumentManager.parse_page_ranges("1-10", total_pages)

    with pytest.raises(ValueError, match="Inverted range"):
        DocumentManager.parse_page_ranges("4-2", total_pages)

    with pytest.raises(ValueError, match="non-numeric"):
        DocumentManager.parse_page_ranges("1-abc", total_pages)

    # 3. Test actual splitting of an active document
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)
    ranges = [[0], [1]]
    split_files = mgr.split_pdf(ranges, tmp_path, base_name="test_split")
    assert len(split_files) == 2
    for f in split_files:
        assert f.is_file()
        d = pymupdf.open(str(f))
        assert d.page_count == 1
        d.close()
    mgr.close()


def test_watermark_persistence_after_saving_and_reopening(tmp_path):
    """Verifies watermark is embedded into PDF content and persists after save/reload."""
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)

    watermark_text = "PAPERVIEW_CONFIDENTIAL_TEST"
    success = mgr.apply_watermark(
        text=watermark_text,
        pages=[0],
        fontsize=42.0,
        color=(0.8, 0.1, 0.1),
        opacity=0.35,
        placement="diagonal",
    )
    assert success is True
    assert mgr.is_modified

    # Save to a fresh copy
    dest = tmp_path / "watermarked_resume.pdf"
    mgr.save_copy(dest)
    mgr.close()

    # Reopen in a new DocumentManager and verify text presence
    verify_mgr = DocumentManager()
    verify_mgr.open_document(dest)
    page0_text = verify_mgr.get_page_text(0)
    assert watermark_text in page0_text
    verify_mgr.close()


def test_optimization_output_validity(tmp_path):
    """Verifies optimization produces valid PDFs with size comparison and preserves content."""
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)

    dest = tmp_path / "optimized_resume.pdf"
    saved_path, orig_size, new_size = mgr.optimize_document(
        destination=dest,
        garbage=4,
        deflate=True,
        clean=True,
    )

    assert saved_path == dest
    assert dest.is_file()
    assert new_size > 0
    assert orig_size > 0

    # Verify optimized file is readable and has intact page count
    opt_doc = pymupdf.open(str(dest))
    assert opt_doc.page_count == mgr.page_count
    assert len(opt_doc[0].get_text()) > 50
    opt_doc.close()

    # Guard: Cannot overwrite active original file
    with pytest.raises(DocumentError, match="cannot overwrite"):
        mgr.optimize_document(SAMPLE_RESUME)

    mgr.close()


def test_preservation_of_annotations_across_operations(tmp_path):
    """Verifies that annotations remain intact across page operations."""
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)

    # Add highlight and sticky note
    rect = pymupdf.Rect(80, 80, 220, 100)
    assert mgr.add_highlight_annotation(0, [rect]) is True
    assert mgr.add_text_annotation(0, (90, 120), "Important note") is True

    # Duplicate page 0
    mgr.duplicate_page(0)
    assert mgr.page_count == 3

    # Check annotations on page 0 and page 1 (the duplicate)
    annots_p0 = list(mgr.doc[0].annots())
    annots_p1 = list(mgr.doc[1].annots())
    assert len(annots_p0) >= 2
    assert len(annots_p1) >= 2

    # Save and verify on disk
    dest = tmp_path / "annotated_duped.pdf"
    mgr.save_copy(dest)
    mgr.close()

    reopened = pymupdf.open(str(dest))
    assert reopened.page_count == 3
    assert len(list(reopened[0].annots())) >= 2
    assert len(list(reopened[1].annots())) >= 2
    reopened.close()


def test_source_file_integrity_and_safeguards(tmp_path):
    """Ensures source files are never corrupted and atomic saves leave no partial junk."""
    source_path = Path(SAMPLE_RESUME)
    with open(source_path, "rb") as f:
        orig_hash = hashlib.sha256(f.read()).hexdigest()

    mgr = DocumentManager()
    mgr.open_document(source_path)

    # Perform various in-memory operations
    mgr.rotate_page(0, 90)
    mgr.duplicate_page(0)
    mgr.delete_pages([1])
    mgr.apply_watermark("INTEGRITY_CHECK", pages=[0])

    # Save copy to new destination
    copy_dest = tmp_path / "integrity_copy.pdf"
    mgr.save_copy(copy_dest)
    mgr.close()

    # Check original source file has not been touched at all
    with open(source_path, "rb") as f:
        after_hash = hashlib.sha256(f.read()).hexdigest()
    assert orig_hash == after_hash, "Original source file was modified!"


def test_ui_organize_pages_dialog_interaction(qapp, tmp_path, monkeypatch):
    """Verifies OrganizePagesDialog user workflow, item manipulation, and reload callback."""
    win = MainWindow(SAMPLE_RESUME)
    initial_count = win.doc_mgr.page_count

    dlg = OrganizePagesDialog(win.doc_mgr, win)
    assert dlg.list_widget.count() == initial_count

    # Select first item and rotate
    dlg.list_widget.setCurrentRow(0)
    dlg.rotate_selected(90)
    item0 = dlg.list_widget.item(0)
    assert isinstance(item0, PageThumbnailItem)
    assert item0.rotation_delta == 90

    # Duplicate item
    dlg.duplicate_selected()
    assert dlg.list_widget.count() == initial_count + 1

    # Extract to temporary file
    extract_out = tmp_path / "ui_extracted.pdf"
    saved = win.doc_mgr.extract_pages([0], extract_out)
    assert saved.is_file()

    # Apply changes
    applied_flag = []
    dlg.pages_applied.connect(win._reload_after_modification)
    dlg.pages_applied.connect(lambda: applied_flag.append(True))
    dlg.apply_changes()

    assert len(applied_flag) == 1
    assert win.doc_mgr.page_count == initial_count + 1
    assert win.page_total_label.text() == f"/ {initial_count + 1}"
    assert win.doc_mgr.is_modified is True

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    win.close()


def test_ui_operation_dialogs_instantiation(qapp, tmp_path):
    """Verifies that Merge, Split, Watermark, and Optimize dialogs instantiate cleanly."""
    win = MainWindow(SAMPLE_RESUME)

    # 1. Merge Dialog
    merge_dlg = MergePDFsDialog(win)
    assert merge_dlg.file_list.count() == 0
    merge_dlg.close()

    # 2. Split Dialog
    split_dlg = SplitPDFDialog(win.doc_mgr, win)
    assert "1-2" in split_dlg.range_edit.text()
    assert split_dlg.preview_box.toPlainText() != ""
    split_dlg.close()

    # 3. Watermark Dialog
    watermark_dlg = WatermarkDialog(win.doc_mgr, 0, win)
    assert watermark_dlg.text_input.text() == "CONFIDENTIAL"
    assert watermark_dlg.preview_widget.base_pixmap is not None
    watermark_dlg.close()

    # 4. Optimize Dialog
    opt_dlg = OptimizePDFDialog(win.doc_mgr, win)
    assert opt_dlg.chk_structural.isChecked() is True
    assert opt_dlg.chk_deflate.isChecked() is True
    opt_dlg.close()

    win.close()
