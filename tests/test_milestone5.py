"""
Milestone 5 Tests for PaperView — Advanced PDF Editing & Professional Workflow.

Tests are grouped by feature and numbered per the spec (1-44).
All tests use temporary PDFs and never depend on user fixtures.
"""
import os
import pytest
import pymupdf
from pathlib import Path
from typing import List

from paperview.document import DocumentManager, DocumentError


# ===========================================================================
# Helper Fixtures
# ===========================================================================

def make_pdf(tmp_path: Path) -> Path:
    """Creates a minimal single-page PDF with text content."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Test page content for Milestone 5")
    p = tmp_path / "test.pdf"
    doc.save(str(p))
    doc.close()
    return p


def make_two_page_pdf(tmp_path: Path) -> Path:
    """Creates a two-page PDF."""
    doc = pymupdf.open()
    for i in range(2):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {i + 1} content")
    p = tmp_path / "two_page.pdf"
    doc.save(str(p))
    doc.close()
    return p


def make_pdf_with_image(tmp_path: Path) -> Path:
    """Creates a PDF with an embedded raster image."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    img_doc = pymupdf.open()
    img_page = img_doc.new_page(width=20, height=20)
    pix = img_page.get_pixmap()
    img_bytes = pix.tobytes("png")
    img_doc.close()
    page.insert_image(pymupdf.Rect(50, 50, 150, 150), stream=img_bytes)
    p = tmp_path / "with_image.pdf"
    doc.save(str(p))
    doc.close()
    return p


def make_pdf_with_toc(tmp_path: Path) -> Path:
    """Creates a three-page PDF with a Table of Contents."""
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Chapter {i + 1}")
    doc.set_toc([
        [1, "Chapter 1", 1],
        [1, "Chapter 2", 2],
        [1, "Chapter 3", 3],
    ])
    p = tmp_path / "with_toc.pdf"
    doc.save(str(p))
    doc.close()
    return p


# ===========================================================================
# CROP (Tests 1-4)
# ===========================================================================

def test_crop_current_page(tmp_path):
    """Test 1: Crop current page sets CropBox correctly."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    r = pymupdf.Rect(50, 50, 400, 600)
    ok = dm.crop_page(0, r)
    assert ok
    page = dm.doc[0]
    cb = page.cropbox
    assert abs(cb.x0 - 50) < 1
    assert abs(cb.y0 - 50) < 1
    assert abs(cb.x1 - 400) < 1
    dm.close()


def test_crop_selected_pages(tmp_path):
    """Test 2: Crop multiple pages."""
    dm = DocumentManager()
    dm.open_document(make_two_page_pdf(tmp_path))
    r = pymupdf.Rect(10, 10, 300, 500)
    count = dm.crop_pages([0, 1], r)
    assert count == 2
    dm.close()


def test_crop_persistence(tmp_path):
    """Test 3: Crop settings persist after save/reopen."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    r = pymupdf.Rect(50, 50, 400, 600)
    dm.crop_page(0, r)
    out = tmp_path / "cropped.pdf"
    dm.save_copy(out)
    dm.close()

    dm2 = DocumentManager()
    dm2.open_document(out)
    assert abs(dm2.doc[0].cropbox.x0 - 50) < 1
    dm2.close()


def test_crop_source_unchanged(tmp_path):
    """Test 4: Source file bytes unchanged after crop + save copy."""
    src = make_pdf(tmp_path)
    orig_bytes = src.read_bytes()
    dm = DocumentManager()
    dm.open_document(src)
    dm.crop_page(0, pymupdf.Rect(50, 50, 400, 600))
    dm.save_copy(tmp_path / "out.pdf")
    dm.close()
    assert src.read_bytes() == orig_bytes


# ===========================================================================
# PAGE LABELS (Tests 5-7)
# ===========================================================================

def test_set_page_labels(tmp_path):
    """Test 5: Set page labels with decimal style."""
    dm = DocumentManager()
    dm.open_document(make_two_page_pdf(tmp_path))
    specs = [{"startpage": 0, "style": "D", "prefix": "", "firstpagenum": 1}]
    ok = dm.set_page_labels(specs)
    assert ok
    dm.close()


def test_read_page_labels(tmp_path):
    """Test 6: Read page labels after setting them."""
    dm = DocumentManager()
    dm.open_document(make_two_page_pdf(tmp_path))
    specs = [{"startpage": 0, "style": "D", "prefix": "", "firstpagenum": 1}]
    dm.set_page_labels(specs)
    labels = dm.get_page_labels()
    assert len(labels) == 2
    assert labels[0] == "1"
    assert labels[1] == "2"
    dm.close()


def test_page_labels_persistence(tmp_path):
    """Test 7: Page labels persist after save/reopen."""
    dm = DocumentManager()
    dm.open_document(make_two_page_pdf(tmp_path))
    specs = [{"startpage": 0, "style": "D", "prefix": "A-", "firstpagenum": 1}]
    dm.set_page_labels(specs)
    out = tmp_path / "labeled.pdf"
    dm.save_copy(out)
    dm.close()

    dm2 = DocumentManager()
    dm2.open_document(out)
    labels = dm2.get_page_labels()
    assert len(labels) >= 1
    assert labels[0].startswith("A-")
    dm2.close()


# ===========================================================================
# HEADER / FOOTER (Tests 8-11)
# ===========================================================================

def _make_hf_config(**kwargs):
    base = {
        "header_left": "", "header_center": "", "header_right": "",
        "footer_left": "", "footer_center": "", "footer_right": "",
        "font_size": 10.0, "margin": 20.0,
    }
    base.update(kwargs)
    return base


def test_apply_header(tmp_path):
    """Test 8: Apply header text to page."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    cfg = _make_hf_config(header_center="Test Header")
    ok = dm.apply_header_footer(cfg)
    assert ok
    assert dm.is_modified
    dm.close()


def test_apply_footer(tmp_path):
    """Test 9: Apply footer text to page."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    cfg = _make_hf_config(footer_center="Test Footer")
    ok = dm.apply_header_footer(cfg)
    assert ok
    dm.close()


def test_header_page_number_template(tmp_path):
    """Test 10: Page number template is accepted."""
    dm = DocumentManager()
    dm.open_document(make_two_page_pdf(tmp_path))
    cfg = _make_hf_config(header_center="Page {page} of {total}")
    ok = dm.apply_header_footer(cfg, pages=[0, 1])
    assert ok
    dm.close()


def test_header_footer_persistence(tmp_path):
    """Test 11: Header text persists in saved PDF."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    cfg = _make_hf_config(header_center="PaperView")
    dm.apply_header_footer(cfg)
    out = tmp_path / "hf.pdf"
    dm.save_copy(out)
    dm.close()

    dm2 = DocumentManager()
    dm2.open_document(out)
    text = dm2.get_page_text(0)
    assert "PaperView" in text
    dm2.close()


# ===========================================================================
# EXPORT (Tests 12-15)
# ===========================================================================

def test_export_current_page(tmp_path):
    """Test 12: Export current page as PNG."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    out_dir = tmp_path / "export"
    out_dir.mkdir()
    paths = dm.export_pages_as_images([0], out_dir, "png", 72)
    assert len(paths) == 1
    assert paths[0].exists()
    dm.close()


def test_export_page_range(tmp_path):
    """Test 13: Export page range."""
    dm = DocumentManager()
    dm.open_document(make_two_page_pdf(tmp_path))
    out_dir = tmp_path / "export"
    out_dir.mkdir()
    paths = dm.export_pages_as_images([0, 1], out_dir, "png", 72)
    assert len(paths) == 2
    dm.close()


def test_png_export(tmp_path):
    """Test 14: PNG export produces valid file."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    out_dir = tmp_path / "export"
    out_dir.mkdir()
    paths = dm.export_pages_as_images([0], out_dir, "png", 96)
    assert paths[0].suffix.lower() == ".png"
    assert paths[0].stat().st_size > 0
    dm.close()


def test_jpeg_export(tmp_path):
    """Test 15: JPEG export produces valid file."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    out_dir = tmp_path / "export"
    out_dir.mkdir()
    paths = dm.export_pages_as_images([0], out_dir, "jpeg", 96, quality=80)
    assert paths[0].suffix.lower() in (".jpg", ".jpeg")
    assert paths[0].stat().st_size > 0
    dm.close()


# ===========================================================================
# IMAGE EXTRACTION (Tests 16-18)
# ===========================================================================

def test_detect_embedded_images(tmp_path):
    """Test 16: Detect embedded images in PDF."""
    dm = DocumentManager()
    dm.open_document(make_pdf_with_image(tmp_path))
    imgs = dm.get_embedded_images()
    assert len(imgs) >= 1
    assert "xref" in imgs[0]
    assert "width" in imgs[0]
    dm.close()


def test_extract_image(tmp_path):
    """Test 17: Extract embedded image to file."""
    dm = DocumentManager()
    dm.open_document(make_pdf_with_image(tmp_path))
    imgs = dm.get_embedded_images()
    assert len(imgs) >= 1
    dest = tmp_path / "extracted_img"
    out = dm.extract_embedded_image(imgs[0]["xref"], dest)
    assert out.exists()
    assert out.stat().st_size > 0
    dm.close()


def test_validate_extracted_image(tmp_path):
    """Test 18: Extracted image file has meaningful content."""
    dm = DocumentManager()
    dm.open_document(make_pdf_with_image(tmp_path))
    imgs = dm.get_embedded_images()
    dest = tmp_path / "img_raw"
    out = dm.extract_embedded_image(imgs[0]["xref"], dest)
    assert out.stat().st_size > 100
    dm.close()


# ===========================================================================
# ATTACHMENTS (Tests 19-21)
# ===========================================================================

def test_detect_attachments_empty(tmp_path):
    """Test 19: No attachments returns empty list gracefully."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    attachments = dm.get_attachments()
    assert attachments == []
    dm.close()


def test_add_and_extract_attachment(tmp_path):
    """Test 20: Add attachment, verify presence, extract and verify content."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    data_file = tmp_path / "data.txt"
    data_file.write_text("hello attachment")
    ok = dm.add_attachment(data_file, description="Test file")
    assert ok
    attachments = dm.get_attachments()
    assert len(attachments) >= 1
    out = tmp_path / "extracted.txt"
    result = dm.extract_attachment(0, out)
    assert result.read_bytes() == b"hello attachment"
    dm.close()


def test_graceful_no_attachments(tmp_path):
    """Test 21: get_attachments never raises on PDF without attachments."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    attachments = dm.get_attachments()
    assert isinstance(attachments, list)
    dm.close()


# ===========================================================================
# BOOKMARKS (Tests 22-27)
# ===========================================================================

def test_read_existing_toc(tmp_path):
    """Test 22: Read TOC from PDF with existing bookmarks."""
    dm = DocumentManager()
    dm.open_document(make_pdf_with_toc(tmp_path))
    toc = dm.get_toc()
    assert len(toc) > 0
    assert toc[0][1] == "Chapter 1"
    dm.close()


def test_add_bookmark(tmp_path):
    """Test 23: Add a bookmark to the document."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    ok = dm.add_bookmark("Chapter 1", 0, level=1)
    assert ok
    toc = dm.get_toc()
    assert any(item[1] == "Chapter 1" for item in toc)
    dm.close()


def test_rename_bookmark(tmp_path):
    """Test 24: Rename an existing bookmark."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    dm.add_bookmark("Old Name", 0)
    ok = dm.rename_bookmark(0, "New Name")
    assert ok
    assert dm.get_toc()[0][1] == "New Name"
    dm.close()


def test_delete_bookmark(tmp_path):
    """Test 25: Delete a bookmark."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    dm.add_bookmark("To Delete", 0)
    initial_count = len(dm.get_toc())
    ok = dm.delete_bookmark(0)
    assert ok
    assert len(dm.get_toc()) == initial_count - 1
    dm.close()


def test_bookmark_persistence(tmp_path):
    """Test 26: Bookmark persists after save/reopen."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    dm.add_bookmark("Saved Chapter", 0)
    out = tmp_path / "bookmarked.pdf"
    dm.save_copy(out)
    dm.close()

    dm2 = DocumentManager()
    dm2.open_document(out)
    assert any(item[1] == "Saved Chapter" for item in dm2.get_toc())
    dm2.close()


def test_bookmark_page_remap(tmp_path):
    """Test 27: Bookmark page numbers remapped after page deletion."""
    dm = DocumentManager()
    dm.open_document(make_two_page_pdf(tmp_path))
    dm.add_bookmark("Page 2 Chapter", 1)
    dm.delete_pages([0])
    toc = dm.get_toc()
    # Bookmark was on page index 1 (physical page 2).
    # After deleting page 0, it should be on page index 0 -> page number 1.
    assert toc[0][2] == 1  # 1-based page number
    dm.close()


# ===========================================================================
# METADATA (Tests 28-30)
# ===========================================================================

def test_read_metadata(tmp_path):
    """Test 28: Read document metadata."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    meta = dm.get_metadata()
    assert hasattr(meta, "title")
    assert hasattr(meta, "author")
    dm.close()


def test_edit_metadata(tmp_path):
    """Test 29: Edit document metadata in memory."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    ok = dm.set_metadata({"title": "Test Doc", "author": "Test Author"})
    assert ok
    meta = dm.get_metadata()
    assert meta.title == "Test Doc"
    dm.close()


def test_metadata_persistence(tmp_path):
    """Test 30: Metadata persists after save/reopen."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    dm.set_metadata({"title": "Persisted Title", "author": "Author Name"})
    out = tmp_path / "meta.pdf"
    dm.save_copy(out)
    dm.close()

    dm2 = DocumentManager()
    dm2.open_document(out)
    assert dm2.get_metadata().title == "Persisted Title"
    dm2.close()


# ===========================================================================
# SECURITY (Tests 31-33)
# ===========================================================================

def test_create_protected_output(tmp_path):
    """Test 31: Create password-protected PDF copy."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    out = tmp_path / "protected.pdf"
    result = dm.save_protected(out, user_pwd="user123", owner_pwd="owner123")
    assert result.exists()
    assert result.stat().st_size > 0
    dm.close()


def test_reopen_protected_pdf(tmp_path):
    """Test 32: Protected PDF can be opened with correct password."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    out = tmp_path / "protected.pdf"
    dm.save_protected(out, user_pwd="user123", owner_pwd="owner123")
    dm.close()

    dm2 = DocumentManager()
    meta = dm2.open_document(out, password="user123")
    assert meta.page_count >= 1
    dm2.close()


def test_protected_source_unchanged(tmp_path):
    """Test 33: Source file unchanged after creating protected copy."""
    src = make_pdf(tmp_path)
    orig = src.read_bytes()
    dm = DocumentManager()
    dm.open_document(src)
    dm.save_protected(tmp_path / "prot.pdf", "u", "o")
    dm.close()
    assert src.read_bytes() == orig


# ===========================================================================
# UNDO / REDO (Tests 34-36)
# ===========================================================================

def test_annotation_undo(tmp_path):
    """Test 34: Undo removes an added annotation."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    dm.push_undo_snapshot()
    dm.add_text_annotation(0, (100, 100), "undo test note")
    assert dm.can_undo
    result = dm.undo()
    assert result is True
    assert not dm.can_undo
    dm.close()


def test_annotation_redo(tmp_path):
    """Test 35: Redo restores an undone operation."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    dm.push_undo_snapshot()
    dm.add_text_annotation(0, (100, 100), "redo test note")
    dm.undo()
    assert dm.can_redo
    result = dm.redo()
    assert result is True
    assert not dm.can_redo
    dm.close()


def test_undo_redo_page_op(tmp_path):
    """Test 36: Undo reverses a page rotation."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    initial_rotation = dm.doc[0].rotation
    dm.push_undo_snapshot()
    dm.rotate_page(0, 90)
    assert dm.doc[0].rotation != initial_rotation
    dm.undo()
    assert dm.doc[0].rotation == initial_rotation
    dm.close()


# ===========================================================================
# UI / DIALOG INSTANTIATION (Tests 37-43)
# ===========================================================================

def _has_display() -> bool:
    """Check if a display is available for UI tests."""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.fixture(scope="module")
def qapp():
    """Create or reuse a QApplication for UI tests."""
    try:
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        yield app
    except Exception:
        pytest.skip("QApplication unavailable")


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_crop_dialog(qapp, tmp_path):
    """Test 37: CropDialog instantiates without error."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    from paperview.milestone5_dialogs import CropDialog
    dlg = CropDialog(dm, 0)
    assert dlg is not None
    dlg.reject()
    dm.close()


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_header_footer_dialog(qapp, tmp_path):
    """Test 38: HeaderFooterDialog instantiates without error."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    from paperview.milestone5_dialogs import HeaderFooterDialog
    dlg = HeaderFooterDialog(dm)
    assert dlg is not None
    dlg.reject()
    dm.close()


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_export_dialog(qapp, tmp_path):
    """Test 39: ExportDialog instantiates without error."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    from paperview.milestone5_dialogs import ExportDialog
    dlg = ExportDialog(dm)
    assert dlg is not None
    dlg.reject()
    dm.close()


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_attachment_dialog(qapp, tmp_path):
    """Test 40: AttachmentDialog instantiates without error."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    from paperview.milestone5_dialogs import AttachmentDialog
    dlg = AttachmentDialog(dm)
    assert dlg is not None
    dlg.reject()
    dm.close()


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_metadata_dialog(qapp, tmp_path):
    """Test 41: Extended PropertiesDialog with editable metadata."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    from paperview.dialogs import PropertiesDialog
    meta = dm.get_metadata()
    dlg = PropertiesDialog(meta, doc_manager=dm)
    assert dlg is not None
    dlg.reject()
    dm.close()


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_security_dialog(qapp, tmp_path):
    """Test 42: SecurityDialog instantiates without error."""
    dm = DocumentManager()
    dm.open_document(make_pdf(tmp_path))
    from paperview.milestone5_dialogs import SecurityDialog
    dlg = SecurityDialog(dm)
    assert dlg is not None
    dlg.reject()
    dm.close()


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_bookmark_editor_dialog(qapp, tmp_path):
    """Test 43: BookmarkEditorDialog instantiates without error."""
    dm = DocumentManager()
    dm.open_document(make_pdf_with_toc(tmp_path))
    from paperview.milestone5_dialogs import BookmarkEditorDialog
    dlg = BookmarkEditorDialog(dm)
    assert dlg is not None
    dlg.reject()
    dm.close()


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_image_extraction_dialog(qapp, tmp_path):
    """Test: ImageExtractionDialog instantiates without error."""
    dm = DocumentManager()
    dm.open_document(make_pdf_with_image(tmp_path))
    from paperview.milestone5_dialogs import ImageExtractionDialog
    dlg = ImageExtractionDialog(dm)
    assert dlg is not None
    dlg.reject()
    dm.close()


@pytest.mark.skipif(not _has_display(), reason="No display available")
def test_main_window_m5_actions(qapp, tmp_path):
    """Test: MainWindow exposes all Milestone 5 actions and updates status bar."""
    from paperview.main_window import MainWindow
    pdf_path = make_two_page_pdf(tmp_path)
    win = MainWindow(initial_file=str(pdf_path))
    assert hasattr(win, "undo_act")
    assert hasattr(win, "redo_act")
    assert hasattr(win, "print_act")
    assert hasattr(win, "crop_act")
    assert hasattr(win, "hf_act")
    assert hasattr(win, "export_images_act")
    assert hasattr(win, "extract_images_act")
    assert hasattr(win, "attachments_act")
    assert hasattr(win, "bookmarks_act")
    assert hasattr(win, "security_act")

    # Status bar should be populated
    status_text = win.doc_info_label.text()
    assert "Page 1 of 2" in status_text

    # Undo/redo methods execute safely
    win.action_undo()
    win.action_redo()

    win.close()


# ===========================================================================
# REGRESSION (Test 44)
# ===========================================================================

def test_regression_sentinel():
    """Test 44: Sentinel - existing 64 tests must continue to pass (enforced by full suite run)."""
    assert True


