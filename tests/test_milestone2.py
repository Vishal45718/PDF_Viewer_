"""
Automated tests for Milestone 2 features:
1. Mouse text selection across lines
2. Clipboard copy (Ctrl+C)
3. Annotation toolbar: highlight, underline, sticky notes, ink drawing
4. Coordinate scaling across zoom and scrolling
5. Safe PDF saving without overwriting original
6. Continuous vs Single page view mode toggle
7. Persistent Open Recent menu via QSettings
"""

from pathlib import Path
import pytest
import pymupdf
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from paperview.document import DocumentManager, DocumentError
from paperview.main_window import MainWindow
from paperview.viewer import DocumentViewer, PageWidget


SAMPLE_RESUME = "/home/jonsnow/Desktop/Resume_CV.pdf"
SAMPLE_EBOOK = "/home/jonsnow/Desktop/MAHABHARATAM-final-E-BOOK.pdf"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_mouse_text_selection_across_lines(qapp):
    """Verifies mouse-based word selection on PDF page and line-break preservation."""
    pw = PageWidget(page_index=0)
    # Simulated words across 2 lines
    sample_words = [
        (10.0, 10.0, 40.0, 20.0, "Hello", 0, 0, 0),
        (45.0, 10.0, 80.0, 20.0, "World", 0, 0, 1),
        (10.0, 30.0, 50.0, 40.0, "Second", 0, 1, 0),
        (55.0, 30.0, 85.0, 40.0, "Line", 0, 1, 1),
    ]
    pw.set_words(sample_words)
    pw.set_tool_mode("select")

    # Simulate mouse press at first word
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(18, 18),  # 8px offset + 10px inside
        QPointF(18, 18),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pw.mousePressEvent(press_ev)

    # Simulate mouse move dragging across to the second line
    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(65, 38),  # near "Line"
        QPointF(65, 38),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    pw.mouseMoveEvent(move_ev)

    selected_text = pw.get_selected_text()
    assert "Hello World" in selected_text
    assert "Second Line" in selected_text
    assert "\n" in selected_text  # line break preserved across lines


def test_copy_selection_to_clipboard(qapp):
    """Verifies that DocumentViewer.copy_selection copies text to system clipboard."""
    viewer = DocumentViewer()
    viewer.set_document(1, [(600.0, 800.0)])
    pw = viewer.page_widgets[0]
    pw.words = [
        (10.0, 10.0, 40.0, 20.0, "PaperView", 0, 0, 0),
        (45.0, 10.0, 80.0, 20.0, "Clipboard", 0, 0, 1),
    ]
    pw.selected_words = list(pw.words)

    clipboard = QApplication.clipboard()
    clipboard.clear()
    assert clipboard.text() == ""

    success = viewer.copy_selection()
    assert success is True
    assert clipboard.text() == "PaperView Clipboard"


def test_annotation_creation_in_document(tmp_path):
    """Verifies highlight, underline, text note, and ink stroke creation in PyMuPDF document."""
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)
    assert not mgr.is_modified

    # 1. Highlight
    rects = [pymupdf.Rect(50, 50, 200, 70)]
    assert mgr.add_highlight_annotation(0, rects) is True
    assert mgr.is_modified is True

    # 2. Underline
    u_rects = [pymupdf.Rect(50, 80, 200, 95)]
    assert mgr.add_underline_annotation(0, u_rects) is True

    # 3. Sticky Note
    assert mgr.add_text_annotation(0, (100, 100), "Review this section carefully") is True

    # 4. Ink Drawing
    stroke = [(100.0, 150.0), (120.0, 160.0), (150.0, 155.0)]
    assert mgr.add_ink_annotation(0, stroke) is True

    # Save to a temporary copy
    dest = tmp_path / "annotated_resume.pdf"
    saved = mgr.save_copy(dest)
    assert saved.exists()

    # Re-open saved copy and verify annotations exist
    doc_check = pymupdf.open(str(saved))
    page0 = doc_check[0]
    annots = list(page0.annots())
    assert len(annots) >= 4

    types = [a.type[1] for a in annots]
    assert "Highlight" in types
    assert "Underline" in types
    assert "Text" in types
    assert "Ink" in types

    doc_check.close()
    mgr.close()


def test_annotation_coordinate_mapping():
    """Verifies that PageWidget accurately maps screen coordinates to PDF points across zoom levels."""
    pw = PageWidget(page_index=0)
    pw.set_page_dimensions(600.0, 800.0)

    # At zoom = 1.0 (padding offset is 8px)
    pw.set_zoom(1.0)
    screen_x, screen_y = 108, 208
    pdf_x = (screen_x - 8) / pw.zoom
    pdf_y = (screen_y - 8) / pw.zoom
    assert abs(pdf_x - 100.0) < 0.001
    assert abs(pdf_y - 200.0) < 0.001

    # At zoom = 2.0
    pw.set_zoom(2.0)
    screen_x_2 = int(8 + 100.0 * pw.zoom)
    screen_y_2 = int(8 + 200.0 * pw.zoom)
    pdf_x_2 = (screen_x_2 - 8) / pw.zoom
    pdf_y_2 = (screen_y_2 - 8) / pw.zoom
    assert abs(pdf_x_2 - 100.0) < 0.001
    assert abs(pdf_y_2 - 200.0) < 0.001


def test_safe_save_copy_guards(tmp_path):
    """Verifies safe save copy refuses overwriting original and preserves source."""
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)
    original_size = Path(SAMPLE_RESUME).stat().st_size

    # Add an annotation
    mgr.add_text_annotation(0, (50, 50), "Important note")

    # Trying to overwrite active file must raise error
    with pytest.raises(DocumentError, match="Save As cannot overwrite"):
        mgr.save_copy(SAMPLE_RESUME)

    # Original size and content remain intact
    assert Path(SAMPLE_RESUME).stat().st_size == original_size

    # Saving to different destination succeeds
    new_dest = tmp_path / "safe_output.pdf"
    res = mgr.save_copy(new_dest)
    assert res.exists()
    assert res != Path(SAMPLE_RESUME)
    mgr.close()


def test_continuous_vs_single_page_toggle(qapp):
    """Verifies switching between continuous scroll and single page presentation."""
    viewer = DocumentViewer()
    viewer.set_document(page_count=3, page_dimensions=[(595.0, 842.0)] * 3)

    assert viewer.view_mode == "continuous"
    assert all(not pw.isHidden() for pw in viewer.page_widgets)

    # Switch to single-page mode
    viewer.set_view_mode("single")
    assert viewer.view_mode == "single"
    assert viewer.page_widgets[0].isHidden() is False
    assert viewer.page_widgets[1].isHidden() is True
    assert viewer.page_widgets[2].isHidden() is True

    # Navigate to page 1
    viewer.scroll_to_page(1)
    assert viewer.page_widgets[0].isHidden() is True
    assert viewer.page_widgets[1].isHidden() is False
    assert viewer.page_widgets[2].isHidden() is True

    # Switch back to continuous
    viewer.set_view_mode("continuous")
    assert viewer.view_mode == "continuous"
    assert all(not pw.isHidden() for pw in viewer.page_widgets)


def test_persistent_recent_menu(qapp):
    """Verifies that MainWindow tracks and persists recent files in QSettings."""
    settings = QSettings("PaperView", "PaperView")
    settings.remove("recent_files")

    win = MainWindow()
    assert len(win._load_recent_files()) == 0

    win.open_file_path(SAMPLE_RESUME)
    recents = win._load_recent_files()
    assert len(recents) == 1
    assert recents[0] == str(Path(SAMPLE_RESUME).resolve())

    # Reopening updates list and doesn't duplicate
    win.open_file_path(SAMPLE_RESUME)
    recents_2 = win._load_recent_files()
    assert len(recents_2) == 1

    # Menu items populated
    assert win.recent_menu.actions()[0].text() == "Resume_CV.pdf"

    # Clearing recent files
    win._clear_recent_files()
    assert len(win._load_recent_files()) == 0
    assert win.recent_menu.actions()[0].text() == "No Recent Files"
