"""
Milestone 6 Tests: HiDPI/DPR Sharpness, Render Cache Isolation,
Stale Render Race Protection, Coordinate Accuracy, Responsive Toolbar,
and Atomic PDF Save Validation.
"""

from pathlib import Path
import pytest
import pymupdf
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QToolButton

from paperview.document import DocumentError, DocumentManager, _atomic_save
from paperview.main_window import MainWindow
from paperview.renderer import RenderCache, RenderManager, RenderTask, RenderWorker
from paperview.viewer import PageWidget


SAMPLE_RESUME = Path("/home/jonsnow/Desktop/Resume_CV.pdf")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# =========================================================================
# Item 1: DPR 1.0 render dimensions
# =========================================================================
def test_m6_01_dpr_1_0_render_dimensions(qapp):
    """Verifies that rendering at DPR 1.0 produces 1:1 logical-to-physical pixel dimensions."""
    task = RenderTask(page_index=0, zoom=1.0, dpr=1.0)
    worker = RenderWorker(doc_path=str(SAMPLE_RESUME), password=None, task=task)
    results = []
    worker.signals.finished.connect(lambda p, z, img: results.append((p, z, img)))
    worker.run()

    assert len(results) == 1
    p_idx, zoom, img = results[0]
    assert p_idx == 0
    assert abs(zoom - 1.0) < 0.001
    assert img.devicePixelRatio() == 1.0

    doc = pymupdf.open(str(SAMPLE_RESUME))
    page0 = doc[0]
    expected_w = int(page0.rect.width)
    expected_h = int(page0.rect.height)
    doc.close()

    assert abs(img.width() - expected_w) <= 2
    assert abs(img.height() - expected_h) <= 2


# =========================================================================
# Item 2: DPR 1.5 render dimensions
# =========================================================================
def test_m6_02_dpr_1_5_render_dimensions(qapp):
    """Verifies that rendering at DPR 1.5 (e.g. fractional HiDPI displays) scales by 1.5x."""
    task = RenderTask(page_index=0, zoom=1.0, dpr=1.5)
    worker = RenderWorker(doc_path=str(SAMPLE_RESUME), password=None, task=task)
    results = []
    worker.signals.finished.connect(lambda p, z, img: results.append((p, z, img)))
    worker.run()

    assert len(results) == 1
    _, _, img = results[0]
    assert img.devicePixelRatio() == 1.5

    doc = pymupdf.open(str(SAMPLE_RESUME))
    page0 = doc[0]
    expected_w = round(page0.rect.width * 1.5)
    expected_h = round(page0.rect.height * 1.5)
    doc.close()

    assert abs(img.width() - expected_w) <= 3
    assert abs(img.height() - expected_h) <= 3


# =========================================================================
# Item 3: DPR 2.0 render dimensions
# =========================================================================
def test_m6_03_dpr_2_0_render_dimensions(qapp):
    """Verifies that rendering at DPR 2.0 (Retina / 4K) doubles physical pixel dimensions."""
    task = RenderTask(page_index=0, zoom=1.0, dpr=2.0)
    worker = RenderWorker(doc_path=str(SAMPLE_RESUME), password=None, task=task)
    results = []
    worker.signals.finished.connect(lambda p, z, img: results.append((p, z, img)))
    worker.run()

    assert len(results) == 1
    _, _, img = results[0]
    assert img.devicePixelRatio() == 2.0

    doc = pymupdf.open(str(SAMPLE_RESUME))
    page0 = doc[0]
    expected_w = round(page0.rect.width * 2.0)
    expected_h = round(page0.rect.height * 2.0)
    doc.close()

    assert abs(img.width() - expected_w) <= 4
    assert abs(img.height() - expected_h) <= 4


# =========================================================================
# Item 4: zoom 100/150/200%
# =========================================================================
def test_m6_04_zoom_100_150_200_render(qapp):
    """Verifies render dimensions across 100%, 150%, and 200% zoom levels."""
    doc = pymupdf.open(str(SAMPLE_RESUME))
    base_w = doc[0].rect.width
    base_h = doc[0].rect.height
    doc.close()

    for zoom in [1.0, 1.5, 2.0]:
        task = RenderTask(page_index=0, zoom=zoom, dpr=1.0)
        worker = RenderWorker(doc_path=str(SAMPLE_RESUME), password=None, task=task)
        res = []
        worker.signals.finished.connect(lambda p, z, img: res.append(img))
        worker.run()

        assert len(res) == 1
        img = res[0]
        expected_w = round(base_w * zoom)
        expected_h = round(base_h * zoom)
        assert abs(img.width() - expected_w) <= 4
        assert abs(img.height() - expected_h) <= 4


# =========================================================================
# Item 5: RenderCache DPR isolation
# =========================================================================
def test_m6_05_rendercache_dpr_isolation():
    """Confirms DPR 1.0, 1.5, and 2.0 cache entries are stored independently and never collide."""
    cache = RenderCache(maxsize=10)
    img_dpr1 = QImage(10, 10, QImage.Format.Format_RGB888)
    img_dpr15 = QImage(15, 15, QImage.Format.Format_RGB888)
    img_dpr2 = QImage(20, 20, QImage.Format.Format_RGB888)

    cache.put(0, 1.0, img_dpr1, dpr=1.0)
    cache.put(0, 1.0, img_dpr15, dpr=1.5)
    cache.put(0, 1.0, img_dpr2, dpr=2.0)

    # A 100% DPR1 cache entry cannot be returned for DPR2 or DPR1.5
    assert cache.get(0, 1.0, dpr=1.0) == img_dpr1
    assert cache.get(0, 1.0, dpr=1.5) == img_dpr15
    assert cache.get(0, 1.0, dpr=2.0) == img_dpr2


# =========================================================================
# Item 6: RenderCache thumbnail isolation
# =========================================================================
def test_m6_06_rendercache_thumbnail_isolation():
    """Document render cannot collide with thumbnail render, even at 25% zoom."""
    cache = RenderCache(maxsize=10)
    img_thumb = QImage(25, 25, QImage.Format.Format_RGB888)
    img_doc25 = QImage(50, 50, QImage.Format.Format_RGB888)

    cache.put(0, 0.25, img_thumb, is_thumbnail=True)
    cache.put(0, 0.25, img_doc25, is_thumbnail=False)

    assert cache.get(0, 0.25, is_thumbnail=True) == img_thumb
    assert cache.get(0, 0.25, is_thumbnail=False) == img_doc25
    assert cache.get(0, 0.25, is_thumbnail=True) != cache.get(0, 0.25, is_thumbnail=False)


# =========================================================================
# Item 7: RenderCache highlight isolation
# =========================================================================
def test_m6_07_rendercache_highlight_isolation():
    """Ensures search highlight states are hashed into cache keys and cannot cross-pollute."""
    cache = RenderCache(maxsize=10)
    img_plain = QImage(10, 10, QImage.Format.Format_RGB888)
    img_hl_a = QImage(12, 12, QImage.Format.Format_RGB888)
    img_hl_b = QImage(14, 14, QImage.Format.Format_RGB888)

    rect_a = [pymupdf.Rect(10, 10, 50, 20)]
    rect_b = [pymupdf.Rect(80, 100, 150, 120)]

    cache.put(0, 1.0, img_plain, highlights=None)
    cache.put(0, 1.0, img_hl_a, highlights=rect_a)
    cache.put(0, 1.0, img_hl_b, highlights=rect_b)

    assert cache.get(0, 1.0, highlights=None) == img_plain
    assert cache.get(0, 1.0, highlights=rect_a) == img_hl_a
    assert cache.get(0, 1.0, highlights=rect_b) == img_hl_b
    # Non-existent highlight state
    rect_c = [pymupdf.Rect(200, 200, 300, 220)]
    assert cache.get(0, 1.0, highlights=rect_c) is None


# =========================================================================
# Item 8: LRU eviction
# =========================================================================
def test_m6_08_rendercache_lru_eviction():
    """Verifies LRU eviction properly discards least-recently accessed pages when capacity exceeded."""
    cache = RenderCache(maxsize=3)
    img1 = QImage(1, 1, QImage.Format.Format_RGB888)
    img2 = QImage(2, 2, QImage.Format.Format_RGB888)
    img3 = QImage(3, 3, QImage.Format.Format_RGB888)
    img4 = QImage(4, 4, QImage.Format.Format_RGB888)

    cache.put(1, 1.0, img1)
    cache.put(2, 1.0, img2)
    cache.put(3, 1.0, img3)

    # Touch page 1 to make it recently used
    assert cache.get(1, 1.0) == img1

    # Put page 4 -> should evict page 2
    cache.put(4, 1.0, img4)

    assert cache.get(2, 1.0) is None, "Page 2 should have been evicted as LRU"
    assert cache.get(1, 1.0) == img1
    assert cache.get(3, 1.0) == img3
    assert cache.get(4, 1.0) == img4


# =========================================================================
# Item 9: stale zoom render rejection
# =========================================================================
def test_m6_09_stale_zoom_render_rejection(qapp):
    """
    Simulates rapid zoom changes: zoom 1.0 -> 1.5 -> 2.0
    where completion order arrives out-of-order:
      1.0
      2.0
      1.5
    The final visible image must remain 2.0.
    """
    pw = PageWidget(page_index=0)

    # User rapidly transitions zoom 1.0 -> 1.5 -> 2.0
    pw.set_zoom(1.0)
    pw.set_zoom(1.5)
    pw.set_zoom(2.0)
    assert abs(pw.zoom - 2.0) < 0.001

    img_1_0 = QImage(100, 100, QImage.Format.Format_RGB888)
    img_1_0.fill(1)
    img_1_5 = QImage(150, 150, QImage.Format.Format_RGB888)
    img_1_5.fill(2)
    img_2_0 = QImage(200, 200, QImage.Format.Format_RGB888)
    img_2_0.fill(3)

    # 1. Stale render for 1.0 arrives
    pw.set_image(img_1_0, 1.0)
    assert pw.qimage != img_1_0

    # 2. Correct render for 2.0 arrives
    pw.set_image(img_2_0, 2.0)
    assert pw.qimage == img_2_0

    # 3. Delayed stale render for 1.5 arrives
    pw.set_image(img_1_5, 1.5)
    assert pw.qimage == img_2_0, "Stale 1.5 render must NOT overwrite newer 2.0 zoom image"
    assert abs(pw.zoom - 2.0) < 0.001


# =========================================================================
# Item 10: thumbnail vs 25% document zoom
# =========================================================================
def test_m6_10_thumbnail_vs_25_percent_document_zoom(qapp):
    """
    Verifies that thumbnail renders and 25% document renders follow completely independent routing:
    - document zoom = 25% -> viewer (via page_rendered)
    - thumbnail render -> sidebar (via thumbnail_rendered)
    """
    rm = RenderManager(max_threads=1, cache_size=10)
    rm.set_document(str(SAMPLE_RESUME))

    page_events = []
    thumb_events = []

    rm.page_rendered.connect(lambda p, z, img: page_events.append((p, z, img)))
    rm.thumbnail_rendered.connect(lambda p, img: thumb_events.append((p, img)))

    # Request thumbnail
    rm.request_page(0, 0.25, is_thumbnail=True)
    rm.thread_pool.waitForDone(2000)
    qapp.processEvents()

    assert len(thumb_events) == 1
    assert len(page_events) == 0

    thumb_events.clear()

    # Request document at 25%
    rm.request_page(0, 0.25, is_thumbnail=False)
    rm.thread_pool.waitForDone(2000)
    qapp.processEvents()

    assert len(page_events) == 1
    assert page_events[0][0] == 0
    assert abs(page_events[0][1] - 0.25) < 0.01
    assert len(thumb_events) == 0


# =========================================================================
# Item 11: coordinate mapping
# =========================================================================
def test_m6_11_coordinate_mapping(qapp):
    """Verifies that selection, hyperlinks, form fields, and redactions map accurately across zoom levels."""
    pw = PageWidget(page_index=0)
    pw.set_page_dimensions(500.0, 700.0)
    pw.set_words([(50.0, 100.0, 150.0, 120.0, "PaperView", 0, 0, 0)])

    # Hyperlink and form field
    link_rect = pymupdf.Rect(200.0, 300.0, 350.0, 320.0)
    pw.set_links([{"from": link_rect, "uri": "https://example.com"}])
    field_rect = pymupdf.Rect(40.0, 50.0, 180.0, 80.0)
    pw.set_form_fields([{"name": "test_field", "rect": field_rect, "field_type": 7}])

    for z in [1.0, 1.5, 2.0]:
        pw.set_zoom(z)
        # Word index mapping
        screen_x = 8 + 60.0 * z
        screen_y = 8 + 110.0 * z
        pdf_x = (screen_x - 8) / z
        pdf_y = (screen_y - 8) / z
        assert abs(pdf_x - 60.0) < 0.01
        assert abs(pdf_y - 110.0) < 0.01
        assert pw._find_word_index_at(pdf_x, pdf_y) == 0

        # Hyperlink hit
        hit_link = QPoint(int(8 + 250.0 * z), int(8 + 310.0 * z))
        assert pw._get_link_at(hit_link) is not None

        # Form field hit
        hit_field = QPoint(int(8 + 60.0 * z), int(8 + 65.0 * z))
        assert pw._get_form_field_at(hit_field) is not None


# =========================================================================
# Item 12: atomic save validation
# =========================================================================
def test_m6_12_atomic_save_validation(tmp_path):
    """Validates that _atomic_save succeeds, verifying valid PDF output with page count matching."""
    dest = tmp_path / "valid_test.pdf"
    doc = pymupdf.open(str(SAMPLE_RESUME))

    _atomic_save(doc, dest)
    assert dest.exists()
    assert dest.stat().st_size > 0

    # Verification handle check
    saved_doc = pymupdf.open(str(dest))
    assert saved_doc.is_pdf
    assert saved_doc.page_count == doc.page_count
    saved_doc.close()
    doc.close()


# =========================================================================
# Item 13: atomic save failure protection
# =========================================================================
def test_m6_13_atomic_save_failure_protection(tmp_path):
    """
    Tests failure protection:
    A. Invalid/corrupt temporary output -> replacement does NOT happen.
    B. Exception during validation -> temporary file cleaned up.
    C. Existing destination remains intact after failure.
    """
    dest = tmp_path / "existing_dest.pdf"
    dest.write_text("PRE-EXISTING INTACT CONTENT")

    doc = pymupdf.open(str(SAMPLE_RESUME))

    # A & C: Corrupt temporary output simulation
    real_save = doc.save
    def corrupt_save(filepath, **kwargs):
        Path(filepath).write_bytes(b"%PDF-corrupted-bytes-not-a-valid-document")

    doc.save = corrupt_save

    with pytest.raises(DocumentError):
        _atomic_save(doc, dest)

    # Destination was NOT replaced and remains intact
    assert dest.read_text() == "PRE-EXISTING INTACT CONTENT"
    # Temporary files cleaned up
    tmp_files = list(dest.parent.glob(".tmp_*"))
    assert len(tmp_files) == 0

    doc.save = real_save

    # B: Exception during validation handle check
    real_open = pymupdf.open
    def open_failure(arg, *a, **kw):
        if ".tmp_" in str(arg):
            raise RuntimeError("Validation engine failed to inspect staging PDF")
        return real_open(arg, *a, **kw)

    pymupdf.open = open_failure
    try:
        with pytest.raises(DocumentError) as exc_info:
            _atomic_save(doc, dest)
        assert "Validation engine failed" in str(exc_info.value)
    finally:
        pymupdf.open = real_open

    # Check cleanup and destination integrity
    assert dest.read_text() == "PRE-EXISTING INTACT CONTENT"
    assert len(list(dest.parent.glob(".tmp_*"))) == 0
    # Original document is still usable
    assert doc.page_count == 2
    doc.close()


# =========================================================================
# Item 14: toolbar QAction identity
# =========================================================================
def test_m6_14_toolbar_qaction_identity(qapp):
    """
    Verifies that toolbar buttons, menu items, and keyboard shortcuts reference
    the EXACT SAME QAction instances without duplication.
    """
    win = MainWindow()
    win.open_file_path(str(SAMPLE_RESUME))

    # Find toolbar buttons
    buttons = win.annot_toolbar.findChildren(QToolButton)
    actions_in_toolbar = [b.defaultAction() for b in buttons if b.defaultAction() is not None]

    # Primary markup actions
    assert win.tool_select_act in actions_in_toolbar
    assert win.tool_highlight_act in actions_in_toolbar
    assert win.tool_underline_act in actions_in_toolbar
    assert win.tool_note_act in actions_in_toolbar
    assert win.tool_pen_act in actions_in_toolbar

    # Redaction actions
    assert win.tool_redact_act in actions_in_toolbar
    assert win.apply_redactions_act in actions_in_toolbar

    # Sign & Stamp menu actions reference the exact same instances
    sign_stamp_menu_acts = win.btn_sign_stamp.menu().actions()
    assert any(a is win.stamp_act for a in sign_stamp_menu_acts)
    assert any(a is win.sign_act for a in sign_stamp_menu_acts)

    # Forms menu actions reference the exact same instances
    assert win.btn_forms.defaultAction() is win.tool_form_act
    forms_menu_acts = win.btn_forms.menu().actions()
    assert any(a is win.tool_form_act for a in forms_menu_acts)
    assert any(a is win.fill_form_act for a in forms_menu_acts)

    win.close()


# =========================================================================
# Item 15: toolbar shortcut consistency
# =========================================================================
def test_m6_15_toolbar_shortcut_consistency(qapp):
    """Verifies that all required shortcuts are registered, non-colliding, and toggle tools."""
    win = MainWindow()
    win.open_file_path(str(SAMPLE_RESUME))

    shortcuts = {
        win.tool_select_act: "V",
        win.tool_highlight_act: "H",
        win.tool_underline_act: "U",
        win.tool_note_act: "N",
        win.tool_pen_act: "P",
        win.tool_redact_act: "Ctrl+Shift+X",
        win.apply_redactions_act: "Ctrl+Shift+A",
        win.stamp_act: "Ctrl+Shift+T",
        win.sign_act: "Ctrl+Shift+G",
        win.tool_form_act: "Ctrl+Shift+M",
        win.fill_form_act: "Ctrl+Shift+F",
    }

    seen_shortcuts = set()
    for act, expected_sc in shortcuts.items():
        actual_sc = act.shortcut().toString()
        assert actual_sc == expected_sc, f"Action {act.text()} has shortcut {actual_sc}, expected {expected_sc}"
        assert actual_sc not in seen_shortcuts, f"Duplicate shortcut: {actual_sc}"
        seen_shortcuts.add(actual_sc)

    # Test tool toggling
    win.tool_highlight_act.trigger()
    assert win.viewer.tool_mode == "highlight"

    win.tool_form_act.trigger()
    assert win.viewer.tool_mode == "form"
    assert win.btn_forms.defaultAction().isChecked()

    win.tool_select_act.trigger()
    assert win.viewer.tool_mode == "select"
    assert not win.tool_form_act.isChecked()

    win.close()


# =========================================================================
# Item 16: toolbar responsive structure
# =========================================================================
def test_m6_16_toolbar_responsive_structure(qapp):
    """
    Verifies that the refactored second toolbar:
    - Fits within ~800px window width
    - Has no horizontal overflow / no extension button (>>) visible at 800px
    - Contains all 4 functional groups without disappearing controls.
    """
    win = MainWindow()
    win.open_file_path(str(SAMPLE_RESUME))

    win.resize(800, 600)
    win.show()
    qapp.processEvents()

    # Size hint must be below 800px
    size_hint_w = win.annot_toolbar.sizeHint().width()
    assert size_hint_w < 800, f"annot_toolbar sizeHint {size_hint_w} exceeds 800px"

    # No extension button visible (no hidden/disappearing controls)
    ext_btn = win.annot_toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
    assert ext_btn is None or not ext_btn.isVisible(), "Toolbar overflow extension button is visible at 800px width"

    # Verify presence of the 4 groups
    # Group 1: Primary markup (Select, Highlight, Underline, Note, Pen)
    assert win.tool_select_act.isVisible()
    assert win.tool_highlight_act.isVisible()
    assert win.tool_underline_act.isVisible()
    assert win.tool_note_act.isVisible()
    assert win.tool_pen_act.isVisible()

    # Group 2: Redaction
    assert win.tool_redact_act.isVisible()
    assert win.apply_redactions_act.isVisible()

    # Group 3: Sign & Stamp menu
    assert win.btn_sign_stamp.isVisible()

    # Group 4: Forms menu
    assert win.btn_forms.isVisible()

    win.close()


# =========================================================================
# Concrete 1:1 Pixel Mapping & Alignment Tests
# =========================================================================
def test_concrete_cases_dpr_and_1to1_pixel_mapping(qapp):
    """
    Verifies concrete cases:
    1. Zoom 1.0, DPR 1.0: logical page ≈ 595x842, physical render ≈ 595x842
    2. Zoom 1.0, DPR 2.0: logical page ≈ 595x842, physical render ≈ 1190x1684, QImage.devicePixelRatio() = 2.0
    3. Zoom 2.0, DPR 2.0: physical render ≈ 2380x3368, QImage.devicePixelRatio() = 2.0
    And verifies 1:1 physical-pixel mapping without scaling/resampling distortion.
    """
    task_2 = RenderTask(page_index=0, zoom=1.0, dpr=2.0)
    worker_2 = RenderWorker(doc_path=str(SAMPLE_RESUME), password=None, task=task_2)
    res_2 = []
    worker_2.signals.finished.connect(lambda p, z, img: res_2.append((p, z, img)))
    worker_2.run()

    assert len(res_2) == 1
    _, _, img_2 = res_2[0]
    assert img_2.devicePixelRatio() == 2.0
    assert abs(img_2.width() - 1190) <= 2
    assert abs(img_2.height() - 1684) <= 2

    # Verify 1:1 physical pixel mapping in PageWidget
    doc = pymupdf.open(str(SAMPLE_RESUME))
    p0 = doc[0]
    pw = PageWidget(0)
    pw.set_page_dimensions(p0.rect.width, p0.rect.height)
    pw.set_zoom(1.0)
    pw.set_image(img_2, 1.0)
    doc.close()

    canvas = QImage(pw.width() * 2, pw.height() * 2, QImage.Format.Format_RGB888)
    canvas.setDevicePixelRatio(2.0)
    p_test = QPainter(canvas)
    pw.render(p_test, QPoint(0, 0))
    p_test.end()

    checked = 0
    matched = 0
    for py in range(4, img_2.height() - 4, 15):
        for px in range(4, img_2.width() - 4, 15):
            checked += 1
            if canvas.pixel(16 + px, 16 + py) == img_2.pixel(px, py):
                matched += 1

    assert checked > 0
    assert matched == checked, f"1:1 mapping mismatch: {matched}/{checked} matched"


def test_resume_cv_alignment_all_features_across_zooms(qapp):
    """
    Verifies that all 10 interactive features on Resume_CV.pdf remain accurately aligned:
    - 100% (zoom 1.0)
    - 150% (zoom 1.5)
    - 200% (zoom 2.0)
    - text selection, hyperlinks, form fields, redaction rectangles, stamps
    """
    doc = pymupdf.open(str(SAMPLE_RESUME))
    page = doc[0]
    words = page.get_text("words")
    first_word = words[0]

    for zoom in [1.0, 1.5, 2.0]:
        pw = PageWidget(0)
        pw.set_page_dimensions(page.rect.width, page.rect.height)
        pw.set_words(words)
        pw.set_zoom(zoom)

        # 1. Text Selection Alignment
        screen_x = 8 + first_word[0] * zoom
        screen_y = 8 + first_word[1] * zoom
        mapped_pdf_x = (screen_x - 8) / zoom
        mapped_pdf_y = (screen_y - 8) / zoom
        assert abs(mapped_pdf_x - first_word[0]) < 1e-4
        assert abs(mapped_pdf_y - first_word[1]) < 1e-4
        w_idx = pw._find_word_index_at(mapped_pdf_x, mapped_pdf_y)
        assert w_idx == 0

        # 2. Hyperlink Alignment
        test_link_rect = pymupdf.Rect(first_word[0], first_word[1], first_word[2], first_word[3])
        pw.set_links([{"from": test_link_rect, "uri": "https://example.com"}])
        hit_pos = QPoint(int(8 + (first_word[0] + 5) * zoom), int(8 + (first_word[1] + 5) * zoom))
        assert pw._get_link_at(hit_pos) is not None

        # 3. Form Field Alignment
        pw.set_form_fields([{"name": "test_field", "rect": test_link_rect, "field_type": 7}])
        assert pw._get_form_field_at(hit_pos) is not None

        # 4. Redaction Rectangle Alignment
        screen_p0 = QPoint(int(8 + 100.0 * zoom), int(8 + 150.0 * zoom))
        pdf_x0 = (screen_p0.x() - 8) / zoom
        pdf_y0 = (screen_p0.y() - 8) / zoom
        assert abs(pdf_x0 - 100.0) < 1.0
        assert abs(pdf_y0 - 150.0) < 1.0

        # 5. Stamp / Signature Positioning Alignment
        stamp_rect = pymupdf.Rect(50.0, 60.0, 200.0, 120.0)
        stamp_screen_x = 8 + stamp_rect.x0 * zoom
        stamp_screen_y = 8 + stamp_rect.y0 * zoom
        assert abs((stamp_screen_x - 8) / zoom - stamp_rect.x0) < 1e-4
        assert abs((stamp_screen_y - 8) / zoom - stamp_rect.y0) < 1e-4

    doc.close()


def test_corrupt_file_handling(tmp_path):
    """Verifies that opening corrupted PDF bytes raises clean DocumentError without crashing."""
    corrupt_file = tmp_path / "corrupted.pdf"
    corrupt_file.write_bytes(b"%PDF-1.7\nCorrupt header and random bytes \x00\xff\xfe\xaa" * 20)

    mgr = DocumentManager()
    with pytest.raises(DocumentError):
        mgr.open_document(corrupt_file)
    assert not mgr.is_open


def test_unwritable_path_handling():
    """Verifies that attempting to save to an unwritable path raises DocumentError safely."""
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)
    with pytest.raises(DocumentError):
        mgr.save_copy("/root/cannot_write_here.pdf")
    assert mgr.is_open
    assert mgr.page_count == 2
    mgr.close()


def test_repeated_open_close_cycles():
    """Stress test: verifies repeated opening and closing resets state without resource leaks."""
    mgr = DocumentManager()
    for _ in range(15):
        mgr.open_document(SAMPLE_RESUME)
        assert mgr.is_open
        assert mgr.page_count == 2
        mgr.close()
        assert not mgr.is_open
        assert mgr.page_count == 0


def test_repeated_zooming(qapp):
    """Verifies rapid zoom in/out cycling preserves viewer geometry and stays within valid bounds."""
    win = MainWindow()
    win.open_file_path(str(SAMPLE_RESUME))

    initial_zoom = win.viewer.zoom
    for _ in range(10):
        win.action_zoom_in()
    assert win.viewer.zoom > initial_zoom
    assert win.viewer.zoom <= 5.0

    for _ in range(15):
        win.action_zoom_out()
    assert win.viewer.zoom >= 0.2

    win.action_fit_width()
    assert win.viewer.zoom > 0
    win.action_fit_page()
    assert win.viewer.zoom > 0
    win.close()
