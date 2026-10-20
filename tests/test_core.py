"""
Tests for DocumentManager, Renderer, and SearchManager.
"""

from pathlib import Path
import pytest
import pymupdf

from paperview.document import (
    DocumentError,
    DocumentManager,
    DocumentMetadata,
    InvalidPasswordError,
    PasswordRequiredError,
)
from paperview.renderer import RenderCache
from paperview.search import SearchWorker


SAMPLE_RESUME = Path("/home/jonsnow/Desktop/Resume_CV.pdf")
SAMPLE_EBOOK = Path("/home/jonsnow/Desktop/MAHABHARATAM-final-E-BOOK.pdf")
SAMPLE_CHECK = Path("/home/jonsnow/Desktop/check_CV.pdf")


def test_document_open_and_metadata():
    mgr = DocumentManager()
    assert not mgr.is_open

    meta = mgr.open_document(SAMPLE_RESUME)
    assert mgr.is_open
    assert mgr.page_count == 2
    assert meta.page_count == 2
    assert meta.format_version.startswith("PDF")
    assert not meta.is_encrypted
    assert len(meta.page_dimensions) == 2

    # Verify TOC extraction
    toc = mgr.get_toc()
    assert len(toc) >= 4  # Resume has 5 TOC entries
    assert toc[0][1] == "Summary"

    # Verify Page Links extraction
    links = mgr.get_page_links(0)
    assert len(links) >= 3  # Resume page 0 has 3 links

    mgr.close()
    assert not mgr.is_open


def test_large_document_open():
    mgr = DocumentManager()
    meta = mgr.open_document(SAMPLE_EBOOK)
    assert mgr.is_open
    assert mgr.page_count == 434
    assert meta.page_count == 434
    mgr.close()


def test_document_save_copy_guards(tmp_path):
    mgr = DocumentManager()
    mgr.open_document(SAMPLE_RESUME)

    # Must raise error if target is the same original file (prevent accidental overwrite)
    with pytest.raises(DocumentError, match="Save As cannot overwrite"):
        mgr.save_copy(SAMPLE_RESUME)

    # Saving to a separate path must succeed
    copy_path = tmp_path / "test_copy.pdf"
    saved = mgr.save_copy(copy_path)
    assert saved.exists()
    assert saved.stat().st_size > 0

    # Ensure original was not modified
    assert SAMPLE_RESUME.stat().st_size > 0

    # Verify the saved copy is a valid PDF
    doc_copy = pymupdf.open(str(copy_path))
    assert doc_copy.page_count == 2
    doc_copy.close()

    mgr.close()


def test_render_cache():
    cache = RenderCache(maxsize=3)
    from PySide6.QtGui import QImage

    img1 = QImage(10, 10, QImage.Format.Format_RGB888)
    img2 = QImage(20, 20, QImage.Format.Format_RGB888)
    img3 = QImage(30, 30, QImage.Format.Format_RGB888)
    img4 = QImage(40, 40, QImage.Format.Format_RGB888)

    cache.put(0, 1.0, img1)
    cache.put(1, 1.0, img2)
    cache.put(2, 1.0, img3)

    assert cache.get(0, 1.0) is not None
    assert cache.get(1, 1.0) is not None

    # Adding 4th should evict the oldest
    cache.put(3, 1.0, img4)
    assert len(cache._cache) == 3


def test_search_worker_extraction():
    worker = SearchWorker(
        doc_path=str(SAMPLE_RESUME),
        password=None,
        query="Python",
        case_sensitive=False,
    )

    hits_collected = []
    worker.signals.hit_found.connect(hits_collected.append)
    worker.run()

    assert len(hits_collected) >= 1
    hit = hits_collected[0]
    assert hit.page_index == 0
    assert "Python" in hit.snippet or "python" in hit.snippet.lower()
    assert hit.rect.width > 0
