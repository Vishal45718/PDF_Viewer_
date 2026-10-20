"""
Page View and Document Scroll Container for PaperView.
Displays crisp PDF pages with soft shadows, responsive zoom, text selection,
annotation authoring (highlight, underline, notes, freehand ink), and view mode toggling.
"""

from typing import Any, Dict, List, Optional, Tuple
import pymupdf
from PySide6.QtCore import QPoint, QRect, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QInputDialog,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from paperview.theme import Theme


class PageWidget(QFrame):
    """
    Renders an individual PDF page with subtle drop shadow, text selection,
    and interactive annotation creation.
    """
    link_clicked = Signal(dict)
    page_clicked = Signal(int)
    text_selected = Signal(int, str)  # page_index, selected_text
    annotation_created = Signal(str, int, object)  # annot_type, page_index, data

    def __init__(self, page_index: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.page_index = page_index
        self.zoom: float = 1.0
        self.qimage: Optional[QImage] = None
        self.links: List[Dict[str, Any]] = []
        self._hovered_link: Optional[Dict[str, Any]] = None
        self.words: List[Tuple] = []  # [(x0, y0, x1, y1, word, block_no, line_no, word_no), ...]
        self.selected_words: List[Tuple] = []
        self.tool_mode: str = "select"  # select | highlight | underline | note | pen
        self.is_loading: bool = True
        self.page_width_pts: float = 595.0
        self.page_height_pts: float = 842.0

        # Mouse interaction state
        self._drag_start_pos: Optional[QPoint] = None
        self._current_stroke: List[Tuple[float, float]] = []

        self.setMouseTracking(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._update_geometry()

    def set_page_dimensions(self, width_pts: float, height_pts: float) -> None:
        self.page_width_pts = width_pts
        self.page_height_pts = height_pts
        self._update_geometry()

    def set_zoom(self, zoom: float) -> None:
        if abs(self.zoom - zoom) > 0.001:
            self.zoom = zoom
            self._update_geometry()
            self.update()

    def set_tool_mode(self, mode: str) -> None:
        self.tool_mode = mode
        self.selected_words.clear()
        self._current_stroke.clear()
        if mode == "select":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode in ("highlight", "underline", "pen"):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "note":
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def set_words(self, words: List[Tuple]) -> None:
        self.words = words

    def _update_geometry(self) -> None:
        w = int(self.page_width_pts * self.zoom)
        h = int(self.page_height_pts * self.zoom)
        total_w = w + 20
        total_h = h + 20
        self.setFixedSize(total_w, total_h)

    def set_image(self, qimage: QImage, zoom: float) -> None:
        self.qimage = qimage
        self.zoom = zoom
        self.is_loading = False
        self._update_geometry()
        self.update()

    def set_links(self, links: List[Dict[str, Any]]) -> None:
        self.links = links
        self._hovered_link = None

    def _get_link_at(self, pos: QPoint) -> Optional[Dict[str, Any]]:
        page_x = (pos.x() - 8) / self.zoom
        page_y = (pos.y() - 8) / self.zoom
        for link in self.links:
            rect = link.get("from")
            if rect and isinstance(rect, pymupdf.Rect):
                if rect.contains(pymupdf.Point(page_x, page_y)):
                    return link
        return None

    def _find_word_index_at(self, px: float, py: float) -> Optional[int]:
        """Finds closest word index to given page coordinates."""
        if not self.words:
            return None
        # Exact inside check
        for i, w in enumerate(self.words):
            if w[0] <= px <= w[2] and w[1] <= py <= w[3]:
                return i

        # Nearest word (penalizing vertical distance more to preserve line affinity)
        best_i = None
        best_dist = float("inf")
        for i, w in enumerate(self.words):
            cx = (w[0] + w[2]) / 2.0
            cy = (w[1] + w[3]) / 2.0
            dist = ((cx - px) ** 2 + 5.0 * ((cy - py) ** 2)) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_i = i
        return best_i

    def get_selected_text(self) -> str:
        """Assembles selected words preserving lines and spaces."""
        if not self.selected_words:
            return ""
        lines: List[str] = []
        current_line: List[str] = []
        last_line_id = (self.selected_words[0][5], self.selected_words[0][6])

        for w in self.selected_words:
            line_id = (w[5], w[6])
            if line_id != last_line_id:
                lines.append(" ".join(current_line))
                current_line = [w[4]]
                last_line_id = line_id
            else:
                current_line.append(w[4])

        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)

    def _get_rects_for_selected_words(self) -> List[pymupdf.Rect]:
        """Combines adjacent words on the same line into unified line rectangles."""
        if not self.selected_words:
            return []
        rects: List[pymupdf.Rect] = []
        current_line_words: List[Tuple] = []
        last_line_id = (self.selected_words[0][5], self.selected_words[0][6])

        for w in self.selected_words:
            line_id = (w[5], w[6])
            if line_id != last_line_id:
                if current_line_words:
                    x0 = min(cw[0] for cw in current_line_words)
                    y0 = min(cw[1] for cw in current_line_words)
                    x1 = max(cw[2] for cw in current_line_words)
                    y1 = max(cw[3] for cw in current_line_words)
                    rects.append(pymupdf.Rect(x0, y0, x1, y1))
                current_line_words = [w]
                last_line_id = line_id
            else:
                current_line_words.append(w)

        if current_line_words:
            x0 = min(cw[0] for cw in current_line_words)
            y0 = min(cw[1] for cw in current_line_words)
            x1 = max(cw[2] for cw in current_line_words)
            y1 = max(cw[3] for cw in current_line_words)
            rects.append(pymupdf.Rect(x0, y0, x1, y1))

        return rects

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.page_clicked.emit(self.page_index)
            pos = event.position().toPoint()
            self._drag_start_pos = pos
            page_x = (pos.x() - 8) / self.zoom
            page_y = (pos.y() - 8) / self.zoom

            if self.tool_mode == "select":
                # Clear previous selection on fresh click
                if self.selected_words:
                    self.selected_words = []
                    self.text_selected.emit(self.page_index, "")
                    self.update()

            elif self.tool_mode in ("highlight", "underline"):
                self.selected_words = []
                self.update()

            elif self.tool_mode == "pen":
                self._current_stroke = [(page_x, page_y)]
                self.update()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        page_x = (pos.x() - 8) / self.zoom
        page_y = (pos.y() - 8) / self.zoom

        # Dragging with LeftButton
        if (event.buttons() & Qt.MouseButton.LeftButton) and self._drag_start_pos:
            start_x = (self._drag_start_pos.x() - 8) / self.zoom
            start_y = (self._drag_start_pos.y() - 8) / self.zoom

            if self.tool_mode in ("select", "highlight", "underline"):
                w1 = self._find_word_index_at(start_x, start_y)
                w2 = self._find_word_index_at(page_x, page_y)
                if w1 is not None and w2 is not None:
                    first = min(w1, w2)
                    last = max(w1, w2)
                    new_sel = self.words[first : last + 1]
                    if new_sel != self.selected_words:
                        self.selected_words = new_sel
                        if self.tool_mode == "select":
                            self.text_selected.emit(self.page_index, self.get_selected_text())
                        self.update()

            elif self.tool_mode == "pen":
                self._current_stroke.append((page_x, page_y))
                self.update()

        else:
            # Hover cursor tracking
            if self.tool_mode == "select":
                link = self._get_link_at(pos)
                if link != self._hovered_link:
                    self._hovered_link = link
                    if link:
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                    else:
                        self.setCursor(Qt.CursorShape.ArrowCursor)
                    self.update()
            elif self.tool_mode in ("highlight", "underline", "pen"):
                self.setCursor(Qt.CursorShape.CrossCursor)
            elif self.tool_mode == "note":
                self.setCursor(Qt.CursorShape.PointingHandCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            pos = event.position().toPoint()
            page_x = (pos.x() - 8) / self.zoom
            page_y = (pos.y() - 8) / self.zoom
            is_drag = (
                abs(pos.x() - self._drag_start_pos.x()) > 5
                or abs(pos.y() - self._drag_start_pos.y()) > 5
            )

            if not is_drag and self.tool_mode == "select":
                # Check for link click
                link = self._get_link_at(pos)
                if link:
                    self.link_clicked.emit(link)
                    self._drag_start_pos = None
                    return

            if self.tool_mode == "highlight" and self.selected_words:
                rects = self._get_rects_for_selected_words()
                self.annotation_created.emit("highlight", self.page_index, rects)
                self.selected_words = []
                self.update()

            elif self.tool_mode == "underline" and self.selected_words:
                rects = self._get_rects_for_selected_words()
                self.annotation_created.emit("underline", self.page_index, rects)
                self.selected_words = []
                self.update()

            elif self.tool_mode == "note" and not is_drag:
                text, ok = QInputDialog.getMultiLineText(
                    self, "Add Sticky Note", f"Enter note text for page {self.page_index + 1}:"
                )
                if ok and text.strip():
                    self.annotation_created.emit(
                        "note", self.page_index, {"point": (page_x, page_y), "text": text.strip()}
                    )

            elif self.tool_mode == "pen" and len(self._current_stroke) >= 2:
                stroke_copy = list(self._current_stroke)
                self.annotation_created.emit("ink", self.page_index, stroke_copy)
                self._current_stroke = []
                self.update()

            self._drag_start_pos = None

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: Any) -> None:
        if self._hovered_link is not None:
            self._hovered_link = None
            if self.tool_mode == "select":
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = int(self.page_width_pts * self.zoom)
        h = int(self.page_height_pts * self.zoom)
        page_rect = QRect(8, 8, w, h)

        # 1. Multi-layered soft drop shadow
        shadow_rect_1 = QRect(10, 11, w + 2, h + 2)
        painter.fillRect(shadow_rect_1, QColor(0, 0, 0, 18))
        shadow_rect_2 = QRect(9, 10, w, h)
        painter.fillRect(shadow_rect_2, QColor(0, 0, 0, 24))

        # 2. Crisp white page background
        painter.fillRect(page_rect, Qt.GlobalColor.white)

        # 3. Render page content
        if self.qimage and not self.qimage.isNull():
            painter.drawImage(page_rect, self.qimage)
        else:
            painter.setPen(QColor(160, 165, 172))
            painter.setFont(QFont("sans-serif", 10))
            painter.drawText(page_rect, Qt.AlignmentFlag.AlignCenter, f"Page {self.page_index + 1}")

        # 4. Text selection & annotation drag highlights
        if self.selected_words:
            if self.tool_mode == "select":
                fill_color = QColor(53, 116, 240, 85)
                for w_item in self.selected_words:
                    wx = int(8 + w_item[0] * self.zoom)
                    wy = int(8 + w_item[1] * self.zoom)
                    ww = max(2, int((w_item[2] - w_item[0]) * self.zoom))
                    wh = max(2, int((w_item[3] - w_item[1]) * self.zoom))
                    painter.fillRect(QRect(wx, wy, ww, wh), fill_color)

            elif self.tool_mode == "highlight":
                fill_color = QColor(255, 235, 59, 130)
                for w_item in self.selected_words:
                    wx = int(8 + w_item[0] * self.zoom)
                    wy = int(8 + w_item[1] * self.zoom)
                    ww = max(2, int((w_item[2] - w_item[0]) * self.zoom))
                    wh = max(2, int((w_item[3] - w_item[1]) * self.zoom))
                    painter.fillRect(QRect(wx, wy, ww, wh), fill_color)

            elif self.tool_mode == "underline":
                painter.setPen(QPen(QColor(53, 116, 240, 200), max(1, int(2 * self.zoom))))
                for w_item in self.selected_words:
                    wx = int(8 + w_item[0] * self.zoom)
                    wy_bottom = int(8 + w_item[3] * self.zoom)
                    ww = max(2, int((w_item[2] - w_item[0]) * self.zoom))
                    painter.drawLine(wx, wy_bottom, wx + ww, wy_bottom)

        # 5. In-progress freehand ink drawing
        if self._current_stroke and len(self._current_stroke) >= 2:
            pen = QPen(
                QColor(230, 50, 50),
                max(2, int(2.5 * self.zoom)),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(pen)
            screen_pts = [
                QPoint(int(8 + pt[0] * self.zoom), int(8 + pt[1] * self.zoom))
                for pt in self._current_stroke
            ]
            painter.drawPolyline(screen_pts)

        # 6. Crisp page outline
        painter.setPen(QPen(QColor(Theme.PAGE_BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(page_rect)

        # 7. Hover indicator over links
        if self._hovered_link and self.tool_mode == "select":
            r = self._hovered_link.get("from")
            if r and isinstance(r, pymupdf.Rect):
                lx = int(8 + r.x0 * self.zoom)
                ly = int(8 + r.y0 * self.zoom)
                lw = int((r.x1 - r.x0) * self.zoom)
                lh = int((r.y1 - r.y0) * self.zoom)
                link_rect = QRect(lx, ly, lw, lh)
                painter.fillRect(link_rect, QColor(53, 116, 240, 28))
                painter.setPen(QPen(QColor(53, 116, 240, 90), 1))
                painter.drawRoundedRect(link_rect, 2, 2)

        painter.end()


class DocumentViewer(QScrollArea):
    """
    Scrollable document workspace with smooth scrolling, centered pages,
    zoom controls, view mode toggles, and annotation events.
    """
    page_changed = Signal(int)  # 0-indexed page in viewport
    link_triggered = Signal(dict)
    zoom_changed = Signal(float)
    text_selected = Signal(int, str)
    annotation_created = Signal(str, int, object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.zoom: float = 1.0
        self.page_widgets: List[PageWidget] = []
        self.current_page: int = 0
        self.total_pages: int = 0
        self.view_mode: str = "continuous"  # continuous | single
        self.tool_mode: str = "select"

        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {Theme.BG_CANVAS};
                border: none;
            }}
        """)

        # Container widget for stacked pages
        self.container = QWidget()
        self.container.setStyleSheet(f"background-color: {Theme.BG_CANVAS};")
        self.layout = QVBoxLayout(self.container)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.layout.setSpacing(16)
        self.layout.setContentsMargins(16, 16, 16, 16)

        self.setWidget(self.container)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_document(self, page_count: int, page_dimensions: List[tuple]) -> None:
        """Configures viewer for a new document with given page count and sizes."""
        for pw in self.page_widgets:
            self.layout.removeWidget(pw)
            pw.deleteLater()
        self.page_widgets.clear()

        self.total_pages = page_count
        self.current_page = 0

        for idx in range(page_count):
            pw = PageWidget(idx, self.container)
            if idx < len(page_dimensions):
                pw.set_page_dimensions(page_dimensions[idx][0], page_dimensions[idx][1])
            pw.set_zoom(self.zoom)
            pw.set_tool_mode(self.tool_mode)
            pw.link_clicked.connect(self.link_triggered.emit)
            pw.page_clicked.connect(self._on_page_clicked)
            pw.text_selected.connect(self._on_text_selected)
            pw.annotation_created.connect(self.annotation_created.emit)
            self.layout.addWidget(pw)
            self.page_widgets.append(pw)

        self.apply_view_mode()
        self.verticalScrollBar().setValue(0)
        self._update_container_width()

    def set_view_mode(self, mode: str) -> None:
        """Switches between continuous scroll and single-page presentation view."""
        if mode in ("continuous", "single") and self.view_mode != mode:
            self.view_mode = mode
            self.apply_view_mode()

    def apply_view_mode(self) -> None:
        """Updates visibility of page widgets depending on active view mode."""
        if not self.page_widgets:
            return
        if self.view_mode == "single":
            for i, pw in enumerate(self.page_widgets):
                pw.setVisible(i == self.current_page)
            self.verticalScrollBar().setValue(0)
        else:
            for pw in self.page_widgets:
                pw.setVisible(True)
        self._update_container_width()

    def set_tool_mode(self, mode: str) -> None:
        """Propagates active annotation / cursor tool to all page widgets."""
        self.tool_mode = mode
        for pw in self.page_widgets:
            pw.set_tool_mode(mode)

    def set_page_words(self, page_index: int, words: List[Tuple]) -> None:
        """Assigns word bounding boxes to the specified page widget."""
        if 0 <= page_index < len(self.page_widgets):
            self.page_widgets[page_index].set_words(words)

    def get_selected_text(self) -> str:
        """Retrieves selected text across any page with an active selection."""
        for pw in self.page_widgets:
            txt = pw.get_selected_text()
            if txt:
                return txt
        return ""

    def copy_selection(self) -> bool:
        """Copies the active selection to system clipboard."""
        txt = self.get_selected_text()
        if txt:
            QApplication.clipboard().setText(txt)
            return True
        return False

    def clear_selection(self) -> None:
        """Clears text selection across all page widgets."""
        for pw in self.page_widgets:
            if pw.selected_words:
                pw.selected_words.clear()
                pw.update()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self._update_container_width()

    def _update_container_width(self) -> None:
        """Ensures container centers pages when narrower than viewport, and scrolls when wider."""
        if not self.page_widgets:
            return
        if self.view_mode == "single":
            visible_pws = [self.page_widgets[self.current_page]] if 0 <= self.current_page < len(self.page_widgets) else []
        else:
            visible_pws = self.page_widgets

        max_page_w = max((pw.width() for pw in visible_pws), default=600)
        viewport_w = self.viewport().width()
        target_w = max(viewport_w, max_page_w + 32)
        self.container.setMinimumWidth(target_w)

    def update_page_image(self, page_index: int, zoom: float, qimage: QImage) -> None:
        if 0 <= page_index < len(self.page_widgets):
            self.page_widgets[page_index].set_image(qimage, zoom)

    def update_page_links(self, page_index: int, links: List[Dict[str, Any]]) -> None:
        if 0 <= page_index < len(self.page_widgets):
            self.page_widgets[page_index].set_links(links)

    def set_zoom(self, zoom: float) -> None:
        zoom = max(0.2, min(5.0, zoom))
        if abs(self.zoom - zoom) > 0.001:
            self.zoom = zoom
            for pw in self.page_widgets:
                pw.set_zoom(self.zoom)
            self._update_container_width()
            self.zoom_changed.emit(self.zoom)

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom / 1.25)

    def fit_width(self) -> None:
        """Adjusts zoom so page width matches viewer viewport width."""
        if not self.page_widgets:
            return
        pw = self.page_widgets[self.current_page] if 0 <= self.current_page < len(self.page_widgets) else self.page_widgets[0]
        viewport_w = self.viewport().width() - 44
        if viewport_w > 100 and pw.page_width_pts > 0:
            new_zoom = viewport_w / pw.page_width_pts
            self.set_zoom(new_zoom)

    def fit_page(self) -> None:
        """Adjusts zoom so page height matches viewer viewport height."""
        if not self.page_widgets:
            return
        pw = self.page_widgets[self.current_page] if 0 <= self.current_page < len(self.page_widgets) else self.page_widgets[0]
        viewport_h = self.viewport().height() - 44
        if viewport_h > 100 and pw.page_height_pts > 0:
            new_zoom = viewport_h / pw.page_height_pts
            self.set_zoom(new_zoom)

    def scroll_to_page(self, page_index: int) -> None:
        """Smoothly navigates to the requested page in continuous or single mode."""
        if 0 <= page_index < len(self.page_widgets):
            self.current_page = page_index
            if self.view_mode == "single":
                for i, pw in enumerate(self.page_widgets):
                    pw.setVisible(i == page_index)
                self.verticalScrollBar().setValue(0)
            else:
                self.container.layout().activate()
                pw = self.page_widgets[page_index]
                y = pw.y()
                if y == 0 and page_index > 0:
                    spacing = self.layout.spacing()
                    margin = self.layout.contentsMargins().top()
                    y = margin + sum(self.page_widgets[i].height() + spacing for i in range(page_index))
                self.verticalScrollBar().setValue(max(0, y - 8))

            self.page_changed.emit(page_index)
            self._update_container_width()

    def get_visible_page_range(self) -> Tuple[int, int]:
        """Calculates which page indices are currently visible."""
        if not self.page_widgets:
            return (0, 0)

        if self.view_mode == "single":
            return (self.current_page, self.current_page)

        self.container.layout().activate()
        viewport_top = self.verticalScrollBar().value()
        viewport_bottom = viewport_top + self.viewport().height()

        start_page = -1
        end_page = -1

        for i, pw in enumerate(self.page_widgets):
            y_top = pw.y()
            if y_top == 0 and i > 0:
                spacing = self.layout.spacing()
                margin = self.layout.contentsMargins().top()
                y_top = margin + sum(self.page_widgets[j].height() + spacing for j in range(i))
            y_bottom = y_top + pw.height()

            if y_bottom >= viewport_top and y_top <= viewport_bottom:
                if start_page == -1:
                    start_page = i
                end_page = i

        if start_page == -1:
            start_page = self.current_page
            end_page = self.current_page

        buf_start = max(0, start_page - 1)
        buf_end = min(len(self.page_widgets) - 1, end_page + 1)
        return (buf_start, buf_end)

    @Slot(int)
    def _on_scroll(self, value: int) -> None:
        """Detects current dominant page in viewport when user scrolls."""
        if not self.page_widgets or self.view_mode == "single":
            return
        viewport_center = value + self.viewport().height() // 3
        for i, pw in enumerate(self.page_widgets):
            if pw.y() <= viewport_center <= (pw.y() + pw.height()):
                if self.current_page != i:
                    self.current_page = i
                    self.page_changed.emit(i)
                break

    @Slot(int)
    def _on_page_clicked(self, page_index: int) -> None:
        if self.current_page != page_index:
            self.current_page = page_index
            self.page_changed.emit(page_index)

    @Slot(int, str)
    def _on_text_selected(self, page_index: int, text: str) -> None:
        # Clear selection on other pages to ensure a single active selection
        for i, pw in enumerate(self.page_widgets):
            if i != page_index and pw.selected_words:
                pw.selected_words.clear()
                pw.update()
        self.text_selected.emit(page_index, text)
