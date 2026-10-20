"""
Search Worker and Search Manager for PaperView.
Supports full-document async search, hit snippets, coordinates, and navigation.
"""

from dataclasses import dataclass
from typing import List, Optional
import pymupdf
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


@dataclass
class SearchHit:
    page_index: int  # 0-indexed
    rect: pymupdf.Rect
    snippet: str
    hit_number_on_page: int


class SearchWorkerSignals(QObject):
    progress = Signal(int, int)  # current_page, total_pages
    hit_found = Signal(object)   # SearchHit
    finished = Signal(list)      # List[SearchHit]
    error = Signal(str)


class SearchWorker(QRunnable):
    """
    QRunnable for background search across document pages.
    """

    def __init__(
        self,
        doc_path: Optional[str],
        password: Optional[str],
        query: str,
        case_sensitive: bool = False,
        doc_bytes: Optional[bytes] = None,
    ) -> None:
        super().__init__()
        self.doc_path = doc_path
        self.password = password
        self.query = query
        self.case_sensitive = case_sensitive
        self.doc_bytes = doc_bytes
        self.signals = SearchWorkerSignals()
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    @Slot()
    def run(self) -> None:
        if not self.query.strip():
            self.signals.finished.emit([])
            return

        doc = None
        hits: List[SearchHit] = []
        try:
            if self.doc_bytes:
                doc = pymupdf.open("pdf", self.doc_bytes)
            else:
                doc = pymupdf.open(self.doc_path)
            if doc.is_encrypted and self.password:
                doc.authenticate(self.password)

            total_pages = doc.page_count
            flags = pymupdf.TEXT_DEHYPHENATE
            if not self.case_sensitive:
                # default search in PyMuPDF is case-insensitive
                pass

            for page_idx in range(total_pages):
                if self._is_cancelled:
                    break

                page = doc[page_idx]
                page_rects = page.search_for(self.query, flags=flags)

                if page_rects:
                    # Extract page text to get context snippets
                    page_text = page.get_text("text")
                    for hit_idx, rect in enumerate(page_rects):
                        snippet = self._extract_snippet(page_text, self.query)
                        hit = SearchHit(
                            page_index=page_idx,
                            rect=rect,
                            snippet=snippet,
                            hit_number_on_page=hit_idx + 1,
                        )
                        hits.append(hit)
                        self.signals.hit_found.emit(hit)

                if page_idx % 5 == 0 or page_idx == total_pages - 1:
                    self.signals.progress.emit(page_idx + 1, total_pages)

            self.signals.finished.emit(hits)

        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    def _extract_snippet(self, full_text: str, query: str, context_len: int = 40) -> str:
        """Finds query in text and extracts surrounding words."""
        lower_text = full_text.lower()
        lower_q = query.lower()
        idx = lower_text.find(lower_q)
        if idx == -1:
            return query

        start = max(0, idx - context_len)
        end = min(len(full_text), idx + len(query) + context_len)
        snippet = full_text[start:end].replace("\n", " ").strip()
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(full_text) else ""
        return f"{prefix}{snippet}{suffix}"


class SearchManager(QObject):
    """
    Coordinates asynchronous searches and keeps track of active hits and navigation.
    """
    search_started = Signal(str)
    search_progress = Signal(int, int)
    hit_added = Signal(object)
    search_completed = Signal(list)
    current_hit_changed = Signal(int, object)  # index, SearchHit

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.thread_pool = QThreadPool()
        self.doc_path: Optional[str] = None
        self.password: Optional[str] = None
        self.doc_bytes: Optional[bytes] = None
        self.current_worker: Optional[SearchWorker] = None
        self.hits: List[SearchHit] = []
        self.current_hit_index: int = -1

    def set_document(self, doc_path: str, password: Optional[str] = None, doc_bytes: Optional[bytes] = None) -> None:
        self.cancel_search()
        self.doc_path = doc_path
        self.password = password
        self.doc_bytes = doc_bytes
        self.hits.clear()
        self.current_hit_index = -1

    def set_doc_bytes(self, doc_bytes: Optional[bytes]) -> None:
        self.cancel_search()
        self.doc_bytes = doc_bytes
        self.hits.clear()
        self.current_hit_index = -1

    def cancel_search(self) -> None:
        if self.current_worker:
            self.current_worker.cancel()
            self.current_worker = None

    def start_search(self, query: str, case_sensitive: bool = False) -> None:
        self.cancel_search()
        self.hits.clear()
        self.current_hit_index = -1

        if (not self.doc_path and not self.doc_bytes) or not query.strip():
            self.search_completed.emit([])
            return

        self.search_started.emit(query)
        worker = SearchWorker(self.doc_path, self.password, query, case_sensitive, doc_bytes=self.doc_bytes)
        self.current_worker = worker

        worker.signals.progress.connect(self._on_progress)
        worker.signals.hit_found.connect(self._on_hit_found)
        worker.signals.finished.connect(self._on_finished)
        self.thread_pool.start(worker)

    @Slot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        self.search_progress.emit(current, total)

    @Slot(object)
    def _on_hit_found(self, hit: SearchHit) -> None:
        self.hits.append(hit)
        self.hit_added.emit(hit)

    @Slot(list)
    def _on_finished(self, hits: List[SearchHit]) -> None:
        self.current_worker = None
        self.hits = hits
        if self.hits:
            self.current_hit_index = 0
            self.current_hit_changed.emit(0, self.hits[0])
        self.search_completed.emit(hits)

    def next_hit(self) -> Optional[SearchHit]:
        if not self.hits:
            return None
        self.current_hit_index = (self.current_hit_index + 1) % len(self.hits)
        hit = self.hits[self.current_hit_index]
        self.current_hit_changed.emit(self.current_hit_index, hit)
        return hit

    def prev_hit(self) -> Optional[SearchHit]:
        if not self.hits:
            return None
        self.current_hit_index = (self.current_hit_index - 1 + len(self.hits)) % len(self.hits)
        hit = self.hits[self.current_hit_index]
        self.current_hit_changed.emit(self.current_hit_index, hit)
        return hit

    def get_hits_for_page(self, page_index: int) -> List[pymupdf.Rect]:
        """Returns rects of all search hits on the specified page."""
        return [h.rect for h in self.hits if h.page_index == page_index]
