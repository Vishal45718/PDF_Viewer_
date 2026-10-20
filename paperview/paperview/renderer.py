"""
Renderer and Threaded Worker for PaperView.
Handles lazy rendering with LRU cache, zooming, and QImage/QPixmap generation.
"""

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import pymupdf
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap


@dataclass
class RenderTask:
    page_index: int
    zoom: float
    rotation: int = 0
    highlights: Optional[List[pymupdf.Rect]] = None
    is_thumbnail: bool = False


class RenderWorkerSignals(QObject):
    finished = Signal(int, float, QImage)  # page_index, zoom, rendered_qimage
    error = Signal(int, str)


class RenderWorker(QRunnable):
    """
    QRunnable for background rendering of a PDF page.
    """

    def __init__(
        self,
        doc_path: Optional[str],
        password: Optional[str],
        task: RenderTask,
        doc_bytes: Optional[bytes] = None,
    ) -> None:
        super().__init__()
        self.doc_path = doc_path
        self.password = password
        self.task = task
        self.doc_bytes = doc_bytes
        self.signals = RenderWorkerSignals()

    @Slot()
    def run(self) -> None:
        doc = None
        try:
            if self.doc_bytes:
                doc = pymupdf.open("pdf", self.doc_bytes)
            else:
                doc = pymupdf.open(self.doc_path)
            if doc.is_encrypted and self.password:
                doc.authenticate(self.password)

            if self.task.page_index < 0 or self.task.page_index >= doc.page_count:
                self.signals.error.emit(self.task.page_index, "Page index out of bounds")
                return

            page = doc[self.task.page_index]
            mat = pymupdf.Matrix(self.task.zoom, self.task.zoom)
            if self.task.rotation != 0:
                mat.prerotate(self.task.rotation)

            # Render page to Pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert pymupdf pixmap to QImage
            # pix.samples has RGB bytes
            img_format = QImage.Format.Format_RGB888
            qimage = QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                img_format
            ).copy()  # detached copy

            # If there are search highlight rects, draw them onto the image
            if self.task.highlights and not self.task.is_thumbnail:
                painter = QPainter(qimage)
                # Highlight styling: semi-transparent bright yellow with subtle border
                fill_color = QColor(255, 235, 59, 120)  # Material Yellow 500 @ ~47% alpha
                pen_color = QColor(251, 192, 45, 200)   # Darker outline
                painter.setBrush(fill_color)
                painter.setPen(QPen(pen_color, 1.5))

                for r in self.task.highlights:
                    # Scale rect by zoom
                    x = r.x0 * self.task.zoom
                    y = r.y0 * self.task.zoom
                    w = (r.x1 - r.x0) * self.task.zoom
                    h = (r.y1 - r.y0) * self.task.zoom
                    painter.drawRect(int(x), int(y), int(w), int(h))

                painter.end()

            try:
                self.signals.finished.emit(self.task.page_index, self.task.zoom, qimage)
            except Exception:
                pass

        except Exception as e:
            try:
                self.signals.error.emit(self.task.page_index, str(e))
            except Exception:
                pass
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass


class RenderCache:
    """
    LRU Cache for rendered page QImages.
    Key: (page_index, round(zoom, 3), tuple_of_highlights_hash)
    """

    def __init__(self, maxsize: int = 24) -> None:
        self.maxsize = maxsize
        self._cache: OrderedDict[Tuple[int, float, int], QImage] = OrderedDict()

    def _make_key(self, page_index: int, zoom: float, highlights: Optional[List[pymupdf.Rect]]) -> Tuple[int, float, int]:
        hl_hash = 0
        if highlights:
            hl_hash = hash(tuple((round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)) for r in highlights))
        return (page_index, round(zoom, 3), hl_hash)

    def get(self, page_index: int, zoom: float, highlights: Optional[List[pymupdf.Rect]] = None) -> Optional[QImage]:
        key = self._make_key(page_index, zoom, highlights)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, page_index: int, zoom: float, qimage: QImage, highlights: Optional[List[pymupdf.Rect]] = None) -> None:
        key = self._make_key(page_index, zoom, highlights)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = qimage
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()


class RenderManager(QObject):
    """
    Coordinates rendering tasks using a QThreadPool and LRU RenderCache.
    """
    page_rendered = Signal(int, float, QImage)
    render_failed = Signal(int, str)

    def __init__(self, max_threads: int = 4, cache_size: int = 32, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(max_threads)
        self.cache = RenderCache(maxsize=cache_size)
        self.doc_path: Optional[str] = None
        self.password: Optional[str] = None
        self.doc_bytes: Optional[bytes] = None
        self._active_workers: set = set()

    def set_document(self, doc_path: str, password: Optional[str] = None, doc_bytes: Optional[bytes] = None) -> None:
        self.thread_pool.clear()
        self.doc_path = doc_path
        self.password = password
        self.doc_bytes = doc_bytes
        self.cache.clear()

    def set_doc_bytes(self, doc_bytes: Optional[bytes]) -> None:
        self.doc_bytes = doc_bytes
        self.cache.clear()

    def clear_cache(self) -> None:
        self.cache.clear()

    def request_page(
        self,
        page_index: int,
        zoom: float,
        highlights: Optional[List[pymupdf.Rect]] = None,
        is_thumbnail: bool = False,
    ) -> Optional[QImage]:
        """
        Returns cached QImage if available, else dispatches async worker.
        """
        cached = self.cache.get(page_index, zoom, highlights)
        if cached is not None:
            return cached

        if not self.doc_path and not self.doc_bytes:
            return None

        task = RenderTask(
            page_index=page_index,
            zoom=zoom,
            highlights=highlights,
            is_thumbnail=is_thumbnail,
        )
        worker = RenderWorker(self.doc_path, self.password, task, doc_bytes=self.doc_bytes)
        self._active_workers.add(worker)
        worker.signals.finished.connect(lambda p, z, img: self._on_worker_finished(p, z, img, worker))
        worker.signals.error.connect(lambda p, err: self._on_worker_error(p, err, worker))
        self.thread_pool.start(worker)
        return None

    def _on_worker_finished(self, page_index: int, zoom: float, qimage: QImage, worker: RenderWorker) -> None:
        self._active_workers.discard(worker)
        self.cache.put(page_index, zoom, qimage)
        self.page_rendered.emit(page_index, zoom, qimage)

    def _on_worker_error(self, page_index: int, err: str, worker: RenderWorker) -> None:
        self._active_workers.discard(worker)
        self.render_failed.emit(page_index, err)
