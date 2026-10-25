"""
UI and Component tests for PaperView using PySide6.
"""

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from paperview.dialogs import PropertiesDialog
from paperview.document import DocumentManager
from paperview.main_window import MainWindow
from paperview.search_bar import SearchBar
from paperview.sidebar import Sidebar
from paperview.viewer import DocumentViewer, PageWidget


SAMPLE_RESUME = "/home/jonsnow/Desktop/Resume_CV.pdf"
SAMPLE_EBOOK = "/home/jonsnow/Desktop/MAHABHARATAM-final-E-BOOK.pdf"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_search_bar_widget(qapp):
    sb = SearchBar()
    assert not sb.isVisible()
    sb.show_and_focus()
    assert sb.isVisible()

    sb.input_field.setText("python")
    sb.set_match_status(1, 5)
    assert "1 of 5" in sb.count_label.text()

    sb.hide_bar()
    assert not sb.isVisible()


def test_sidebar_widget(qapp):
    sb = Sidebar()
    sb.set_page_count(5)
    assert sb.thumb_list.count() == 5

    sample_toc = [
        [1, "Chapter 1", 1],
        [2, "Section 1.1", 2],
        [1, "Chapter 2", 3],
    ]
    sb.set_toc(sample_toc)
    assert sb.toc_tree.topLevelItemCount() == 2


def test_page_widget_and_viewer(qapp):
    viewer = DocumentViewer()
    viewer.set_document(page_count=3, page_dimensions=[(595.0, 842.0)] * 3)
    assert len(viewer.page_widgets) == 3

    # Check zoom
    viewer.set_zoom(1.5)
    assert abs(viewer.zoom - 1.5) < 0.01

    # Check visible range
    start, end = viewer.get_visible_page_range()
    assert start >= 0
    assert end >= 0


def test_properties_dialog(qapp):
    doc_mgr = DocumentManager()
    meta = doc_mgr.open_document(SAMPLE_RESUME)
    dlg = PropertiesDialog(meta)
    assert dlg.windowTitle() == "Document Properties"
    doc_mgr.close()


def test_main_window_open_and_navigation(qapp):
    win = MainWindow()
    win.open_file_path(SAMPLE_RESUME)

    assert win.doc_mgr.is_open
    assert win.doc_mgr.page_count == 2
    assert win.viewer.total_pages == 2

    # Navigate
    win.navigate_to_page(1)
    assert win.viewer.current_page == 1

    win.action_prev_page()
    assert win.viewer.current_page == 0

    # Zoom controls
    win.action_zoom_in()
    assert win.viewer.zoom > 1.0
    win.action_fit_width()
    win.action_fit_page()

    win.close()


def test_zoom_reanchors_current_page_after_zoom(qapp):
    """Regression: a zoom reflow must keep the viewed page in the visible range.

    Previously, zooming deep inside a long document shifted the scroll mapping
    so that current_page fell outside the visible range: the viewport rendered
    other pages on fresh requests, while the current page kept its old,
    upscaled image and the page counter/thumbnails stayed on the old page.
    """
    from PySide6.QtTest import QTest

    viewer = DocumentViewer()
    viewer.resize(800, 600)
    viewer.show()
    viewer.set_document(page_count=40, page_dimensions=[(595.0, 842.0)] * 40)
    qapp.processEvents()

    viewer.scroll_to_page(25)
    qapp.processEvents()
    assert viewer.current_page == 25

    for zoom in (2.5, 0.5, 1.5):
        viewer.set_zoom(zoom)
        QTest.qWait(30)
        qapp.processEvents()
        lo, hi = viewer.get_visible_page_range()
        assert lo <= viewer.current_page <= hi, (
            f"zoom {zoom}: current_page={viewer.current_page} outside visible range {(lo, hi)}")

    viewer.close()


def test_icons_provider(qapp):
    from paperview.icons import get_icon
    for name in ["open", "save", "prev", "next", "zoom_in", "zoom_out", "fit_width", "fit_page", "find", "properties", "close"]:
        icon = get_icon(name)
        assert not icon.isNull(), f"Icon {name} is null"


def test_theme_stylesheet():
    from paperview.theme import Theme
    ss = Theme.main_stylesheet()
    assert Theme.BG_WINDOW in ss
    assert Theme.ACCENT in ss
    assert "QToolBar" in ss


def test_link_transparent_behavior(qapp):
    import pymupdf
    pw = PageWidget(0)
    pw.set_links([{"kind": 2, "uri": "https://example.com", "from": pymupdf.Rect(10, 10, 100, 30)}])
    assert pw._hovered_link is None
    # Test link hit detection
    from PySide6.QtCore import QPoint
    link = pw._get_link_at(QPoint(30, 20))
    assert link is not None
    assert link["uri"] == "https://example.com"
    # Outside link rect
    assert pw._get_link_at(QPoint(300, 300)) is None
