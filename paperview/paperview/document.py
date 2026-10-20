"""
Document Management Module for PaperView.
Handles safe opening, password verification, metadata retrieval, TOC extraction,
and document lifecycle using PyMuPDF.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
import pymupdf


@dataclass
class SearchResult:
    """Represents a text search match in a document."""
    page_index: int
    rect: pymupdf.Rect
    quad: Optional[Any] = None
    snippet: str = ""


@dataclass
class DocumentMetadata:
    """Document metadata details."""
    title: str = "Unknown"
    author: str = "Unknown"
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: str = ""
    modification_date: str = ""
    format_version: str = ""
    page_count: int = 0
    is_encrypted: bool = False
    permissions: int = 0
    file_size_bytes: int = 0
    file_path: str = ""
    page_dimensions: List[Tuple[float, float]] = field(default_factory=list)


class DocumentError(Exception):
    """Base exception for document operations."""
    pass


class PasswordRequiredError(DocumentError):
    """Raised when a document requires a password to open."""
    pass


class InvalidPasswordError(DocumentError):
    """Raised when an incorrect password was provided."""
    pass


def remap_toc_after_reorder(toc: List[List[Any]], old_to_new: Dict[int, int]) -> List[List[Any]]:
    """Remaps TOC 1-based page numbers after page reordering."""
    new_toc = []
    for item in toc:
        pno = item[2]
        old_idx = pno - 1
        if old_idx in old_to_new:
            new_item = list(item)
            new_item[2] = old_to_new[old_idx] + 1
            new_toc.append(new_item)
    return new_toc


def remap_toc_after_deletion(toc: List[List[Any]], deleted_indices: Set[int], total_old_pages: int) -> List[List[Any]]:
    """Remaps TOC 1-based page numbers after page deletions, pruning deleted pages."""
    old_to_new = {}
    current_new = 0
    for idx in range(total_old_pages):
        if idx not in deleted_indices:
            old_to_new[idx] = current_new
            current_new += 1
    return remap_toc_after_reorder(toc, old_to_new)


def remap_toc_after_duplication(toc: List[List[Any]], dup_idx: int) -> List[List[Any]]:
    """Remaps TOC 1-based page numbers after a page duplication."""
    new_toc = []
    for item in toc:
        pno = item[2]
        old_idx = pno - 1
        new_item = list(item)
        if old_idx > dup_idx:
            new_item[2] = pno + 1
        new_toc.append(new_item)
    return new_toc


def _atomic_save(
    doc: pymupdf.Document,
    dest: Path,
    garbage: int = 4,
    deflate: bool = True,
    clean: bool = False,
) -> Path:
    """Saves a document to destination safely using a temporary file and atomic replace."""
    dest = Path(dest).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_file = dest.with_name(f".tmp_{dest.stem}_{uuid.uuid4().hex[:8]}.pdf")
    try:
        doc.save(str(temp_file), garbage=garbage, deflate=deflate, clean=clean)
        temp_file.replace(dest)
        return dest
    except Exception as e:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
        raise DocumentError(f"Failed to save document to {dest}: {e}") from e


class DocumentManager:
    """
    Manages opening, inspecting, saving, and querying PDF documents.
    Ensures safe operations without modifying source files.
    """

    def __init__(self) -> None:
        self._doc: Optional[pymupdf.Document] = None
        self._file_path: Optional[Path] = None
        self._page_count: int = 0

    @property
    def is_open(self) -> bool:
        return self._doc is not None and not self._doc.is_closed

    @property
    def file_path(self) -> Optional[Path]:
        return self._file_path

    @property
    def page_count(self) -> int:
        return self._page_count

    @property
    def doc(self) -> Optional[pymupdf.Document]:
        return self._doc

    def open_document(self, path: str | Path, password: Optional[str] = None) -> DocumentMetadata:
        """
        Opens a PDF file safely.
        Raises PasswordRequiredError if password is required and none provided.
        Raises InvalidPasswordError if password authentication fails.
        """
        p = Path(path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"File not found: {p}")

        self.close()

        try:
            doc = pymupdf.open(str(p))
        except Exception as e:
            raise DocumentError(f"Failed to open document: {e}") from e

        if doc.is_encrypted:
            if doc.needs_pass:
                if password is None:
                    doc.close()
                    raise PasswordRequiredError("Document is encrypted and requires a password.")
                success = doc.authenticate(password)
                if not success:
                    doc.close()
                    raise InvalidPasswordError("Invalid password for encrypted PDF.")

        self._doc = doc
        self._file_path = p
        self._page_count = doc.page_count
        self._words_cache: Dict[int, List[Tuple]] = {}
        self._is_modified: bool = False

        return self.get_metadata()

    def close(self) -> None:
        """Closes the current document if open."""
        if self._doc is not None:
            try:
                if not self._doc.is_closed:
                    self._doc.close()
            except Exception:
                pass
            self._doc = None
            self._file_path = None
            self._page_count = 0
            self._words_cache.clear()
            self._is_modified = False

    def get_metadata(self) -> DocumentMetadata:
        """Extracts comprehensive metadata and page dimensions."""
        if not self.is_open or self._doc is None:
            return DocumentMetadata()

        md = self._doc.metadata or {}
        dims: List[Tuple[float, float]] = []
        for i in range(self._page_count):
            try:
                page = self._doc[i]
                dims.append((float(page.rect.width), float(page.rect.height)))
            except Exception:
                dims.append((595.0, 842.0))

        file_size = 0
        if self._file_path and self._file_path.exists():
            try:
                file_size = self._file_path.stat().st_size
            except Exception:
                pass

        fmt = md.get("format") or "PDF 1.7"
        if not fmt.startswith("PDF"):
            fmt = f"PDF {fmt}"

        return DocumentMetadata(
            title=md.get("title") or (self._file_path.name if self._file_path else "Untitled"),
            author=md.get("author") or "Unknown",
            subject=md.get("subject") or "",
            keywords=md.get("keywords") or "",
            creator=md.get("creator") or "",
            producer=md.get("producer") or "",
            creation_date=md.get("creationDate") or "",
            modification_date=md.get("modDate") or "",
            format_version=fmt,
            page_count=self._page_count,
            is_encrypted=self._doc.is_encrypted,
            permissions=self._doc.permissions,
            file_size_bytes=file_size,
            file_path=str(self._file_path) if self._file_path else "",
            page_dimensions=dims,
        )

    def get_toc(self) -> List[List[Any]]:
        """Returns the Table of Contents hierarchy [lvl, title, page_no, ...]."""
        if not self.is_open or self._doc is None:
            return []
        try:
            return self._doc.get_toc()
        except Exception:
            return []

    def get_page_links(self, page_index: int) -> List[Dict[str, Any]]:
        """Returns interactive links on the given page."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return []
        try:
            return self._doc[page_index].get_links()
        except Exception:
            return []

    def get_page_text(self, page_index: int) -> str:
        """Returns full text extracted from the given page."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return ""
        try:
            return self._doc[page_index].get_text("text")
        except Exception:
            return ""

    @property
    def is_modified(self) -> bool:
        return self._is_modified

    def get_page_words(self, page_index: int) -> List[Tuple]:
        """Returns word bounding boxes [(x0, y0, x1, y1, word, block_no, line_no, word_no), ...] cached."""
        if not self.is_open or self._doc is None:
            return []
        if 0 <= page_index < self._page_count:
            if page_index not in self._words_cache:
                try:
                    self._words_cache[page_index] = self._doc[page_index].get_text("words")
                except Exception:
                    self._words_cache[page_index] = []
            return self._words_cache[page_index]
        return []

    def add_highlight_annotation(
        self,
        page_index: int,
        rects: List[pymupdf.Rect],
        color: Tuple[float, float, float] = (1.0, 0.92, 0.23),
    ) -> bool:
        """Adds a highlight annotation across one or more rects."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            page = self._doc[page_index]
            for r in rects:
                annot = page.add_highlight_annot(r)
                annot.set_colors(stroke=color)
                annot.update()
            self._is_modified = True
            return True
        except Exception:
            return False

    def add_underline_annotation(
        self,
        page_index: int,
        rects: List[pymupdf.Rect],
        color: Tuple[float, float, float] = (0.2, 0.5, 0.9),
    ) -> bool:
        """Adds an underline annotation across one or more rects."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            page = self._doc[page_index]
            for r in rects:
                annot = page.add_underline_annot(r)
                annot.set_colors(stroke=color)
                annot.update()
            self._is_modified = True
            return True
        except Exception:
            return False

    def add_text_annotation(
        self,
        page_index: int,
        point: Tuple[float, float],
        text: str,
    ) -> bool:
        """Adds a sticky note annotation at the given point."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            page = self._doc[page_index]
            pt = pymupdf.Point(point[0], point[1])
            annot = page.add_text_annot(pt, text, icon="Comment")
            annot.set_colors(stroke=(1.0, 0.8, 0.2))
            annot.update()
            self._is_modified = True
            return True
        except Exception:
            return False

    def add_ink_annotation(
        self,
        page_index: int,
        stroke: List[Tuple[float, float]],
        color: Tuple[float, float, float] = (0.9, 0.2, 0.2),
        width: float = 2.0,
    ) -> bool:
        """Adds a freehand ink stroke annotation."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count) or len(stroke) < 2:
            return False
        try:
            page = self._doc[page_index]
            annot = page.add_ink_annot([stroke])
            annot.set_colors(stroke=color)
            annot.set_border(width=width)
            annot.update()
            self._is_modified = True
            return True
        except Exception:
            return False

    def get_document_bytes(self) -> bytes:
        """Returns the in-memory document serialized to PDF bytes."""
        if not self.is_open or self._doc is None:
            return b""
        try:
            return self._doc.tobytes()
        except Exception:
            return b""

    def save_copy(self, destination: str | Path, garbage: int = 4, deflate: bool = True) -> Path:
        """
        Saves a copy of the document to a new destination safely.
        Guarantees that it never overwrites the original file unless explicitly requested
        and guards against destination == source.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is currently open.")

        dest = Path(destination).resolve()
        if self._file_path and dest == self._file_path.resolve():
            raise DocumentError("Save As cannot overwrite the active original file directly. Choose a new name.")

        _atomic_save(self._doc, dest, garbage=garbage, deflate=deflate)
        self._is_modified = False
        return dest

    def rotate_page(self, page_index: int, delta_degrees: int = 90) -> int:
        """Rotates a specific page by delta_degrees (clockwise or counter-clockwise)."""
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if not (0 <= page_index < self._page_count):
            raise DocumentError(f"Invalid page index: {page_index}")
        page = self._doc[page_index]
        new_rot = (page.rotation + delta_degrees) % 360
        page.set_rotation(new_rot)
        self._words_cache.pop(page_index, None)
        self._is_modified = True
        return new_rot

    def rotate_pages(self, page_indices: List[int], delta_degrees: int = 90) -> None:
        """Rotates multiple pages by delta_degrees."""
        for idx in page_indices:
            self.rotate_page(idx, delta_degrees)

    def reorder_pages(self, new_order: List[int]) -> bool:
        """
        Reorders pages according to new_order permutation.
        Remaps Table of Contents (bookmarks) and validates document state.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if sorted(new_order) != list(range(self._page_count)):
            raise DocumentError("Invalid page order permutation.")

        orig_toc = self.get_toc()
        old_to_new = {old_idx: new_idx for new_idx, old_idx in enumerate(new_order)}

        self._doc.select(new_order)
        self._words_cache.clear()
        self._is_modified = True

        if orig_toc:
            new_toc = remap_toc_after_reorder(orig_toc, old_to_new)
            try:
                self._doc.set_toc(new_toc)
            except Exception:
                pass

        return True

    def delete_pages(self, page_indices: List[int]) -> bool:
        """
        Deletes specified pages. Requires at least 1 page to remain.
        Remaps bookmarks and internal structures.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if not page_indices:
            return False

        del_set = set(page_indices)
        for idx in del_set:
            if not (0 <= idx < self._page_count):
                raise DocumentError(f"Page index {idx} out of range.")

        if len(del_set) >= self._page_count:
            raise DocumentError("Cannot delete all pages in the document. At least one page must remain.")

        orig_toc = self.get_toc()
        old_count = self._page_count

        # Delete from highest to lowest index
        for idx in sorted(del_set, reverse=True):
            self._doc.delete_page(idx)

        self._page_count = self._doc.page_count
        self._words_cache.clear()
        self._is_modified = True

        if orig_toc:
            new_toc = remap_toc_after_deletion(orig_toc, del_set, old_count)
            try:
                self._doc.set_toc(new_toc)
            except Exception:
                pass

        return True

    def duplicate_page(self, page_index: int) -> int:
        """
        Duplicates a page and places the duplicate immediately after page_index.
        Preserves annotations and updates bookmarks. Returns the new page index.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if not (0 <= page_index < self._page_count):
            raise DocumentError(f"Invalid page index: {page_index}")

        orig_toc = self.get_toc()
        self._doc.fullcopy_page(page_index)
        new_page_pos = page_index + 1
        if new_page_pos < self._doc.page_count - 1:
            self._doc.move_page(self._doc.page_count - 1, new_page_pos)

        self._page_count = self._doc.page_count
        self._words_cache.clear()
        self._is_modified = True

        if orig_toc:
            new_toc = remap_toc_after_duplication(orig_toc, page_index)
            try:
                self._doc.set_toc(new_toc)
            except Exception:
                pass

        return new_page_pos

    def extract_pages(self, page_indices: List[int], destination: str | Path) -> Path:
        """
        Extracts selected pages into a new standalone PDF document.
        Never overwrites the active source document.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if not page_indices:
            raise DocumentError("No pages selected for extraction.")

        dest = Path(destination).resolve()
        if self._file_path and dest == self._file_path.resolve():
            raise DocumentError("Cannot extract into the active source document. Choose a separate destination.")

        for idx in page_indices:
            if not (0 <= idx < self._page_count):
                raise DocumentError(f"Page index {idx} out of range.")

        new_doc = pymupdf.open()
        try:
            for idx in page_indices:
                new_doc.insert_pdf(self._doc, from_page=idx, to_page=idx)
            _atomic_save(new_doc, dest, garbage=4, deflate=True)
        finally:
            new_doc.close()

        return dest

    @staticmethod
    def merge_pdfs(
        file_paths: List[str | Path],
        destination: str | Path,
        passwords: Optional[Dict[str, str]] = None,
    ) -> Path:
        """
        Merges multiple PDF files into one output PDF in the specified order.
        Validates input files, handles encrypted files, preserves TOCs with offsets,
        and saves atomically.
        """
        if not file_paths:
            raise DocumentError("At least one PDF file must be provided for merging.")

        dest = Path(destination).resolve()
        resolved_inputs = [Path(fp).resolve() for fp in file_paths]
        passwords = passwords or {}

        for src in resolved_inputs:
            if dest == src:
                raise DocumentError(f"Merge output path cannot overwrite input file: {src.name}")
            if not src.is_file():
                raise FileNotFoundError(f"Source PDF file not found: {src}")

        merged_doc = pymupdf.open()
        merged_toc: List[List[Any]] = []

        try:
            for src_path in resolved_inputs:
                try:
                    src_doc = pymupdf.open(str(src_path))
                except Exception as e:
                    raise DocumentError(f"Failed to open '{src_path.name}': {e}") from e

                if src_doc.is_encrypted:
                    pwd = passwords.get(str(src_path)) or passwords.get(src_path.name)
                    if pwd is None or not src_doc.authenticate(pwd):
                        src_doc.close()
                        raise PasswordRequiredError(f"Password required or incorrect for encrypted PDF: {src_path.name}")

                offset = merged_doc.page_count
                merged_doc.insert_pdf(src_doc)

                try:
                    src_toc = src_doc.get_toc()
                    for item in src_toc:
                        item_copy = list(item)
                        item_copy[2] = item[2] + offset
                        merged_toc.append(item_copy)
                except Exception:
                    pass

                src_doc.close()

            if merged_toc:
                try:
                    merged_doc.set_toc(merged_toc)
                except Exception:
                    pass

            _atomic_save(merged_doc, dest, garbage=4, deflate=True)
        finally:
            merged_doc.close()

        return dest

    @staticmethod
    def parse_page_ranges(range_str: str, max_pages: int) -> List[List[int]]:
        """
        Parses page range syntax (e.g. '1-3, 5, 7-10' or 'all') into 0-based page index lists.
        Raises ValueError with clear explanation if input is invalid or out of bounds.
        """
        s = range_str.strip()
        if not s:
            raise ValueError("Page range expression cannot be empty.")

        if s.lower() in ("all", "*"):
            return [[i] for i in range(max_pages)]

        parts = [p.strip() for p in s.split(",") if p.strip()]
        if not parts:
            raise ValueError("No valid page numbers found in range expression.")

        results: List[List[int]] = []
        for part in parts:
            if "-" in part:
                tokens = part.split("-")
                if len(tokens) != 2:
                    raise ValueError(f"Invalid range syntax '{part}'. Expected format like '1-3'.")
                try:
                    start = int(tokens[0].strip())
                    end = int(tokens[1].strip())
                except ValueError:
                    raise ValueError(f"Range '{part}' contains non-numeric values.")

                if start < 1:
                    raise ValueError(f"Page number {start} in range '{part}' must be >= 1.")
                if end > max_pages:
                    raise ValueError(f"Page number {end} exceeds total pages ({max_pages}).")
                if start > end:
                    raise ValueError(f"Inverted range '{part}': start ({start}) must be <= end ({end}).")

                results.append(list(range(start - 1, end)))
            else:
                try:
                    val = int(part)
                except ValueError:
                    raise ValueError(f"Invalid page number '{part}'. Must be a valid integer.")

                if val < 1:
                    raise ValueError(f"Page number {val} must be >= 1.")
                if val > max_pages:
                    raise ValueError(f"Page number {val} exceeds total pages ({max_pages}).")

                results.append([val - 1])

        return results

    def split_pdf(
        self,
        ranges: List[List[int]],
        output_dir: str | Path,
        base_name: Optional[str] = None,
    ) -> List[Path]:
        """
        Splits the current document into separate PDFs according to the specified page ranges.
        Never overwrites the active source document. Returns list of created files.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if not ranges:
            raise DocumentError("No page ranges provided for splitting.")

        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        prefix = base_name or (self._file_path.stem if self._file_path else "split_doc")

        created_files: List[Path] = []
        for r_idx, page_list in enumerate(ranges):
            if not page_list:
                continue
            if len(page_list) == 1:
                filename = f"{prefix}_page_{page_list[0] + 1}.pdf"
            else:
                filename = f"{prefix}_part_{r_idx + 1}_pages_{page_list[0] + 1}-{page_list[-1] + 1}.pdf"

            dest = out_dir / filename
            if self._file_path and dest == self._file_path.resolve():
                raise DocumentError(f"Split destination file would overwrite active source: {filename}")

            part_doc = pymupdf.open()
            try:
                for p_idx in page_list:
                    part_doc.insert_pdf(self._doc, from_page=p_idx, to_page=p_idx)
                _atomic_save(part_doc, dest, garbage=4, deflate=True)
                created_files.append(dest)
            finally:
                part_doc.close()

        return created_files

    def apply_watermark(
        self,
        text: str,
        pages: Optional[List[int]] = None,
        fontsize: float = 48.0,
        color: Tuple[float, float, float] = (0.7, 0.7, 0.7),
        opacity: float = 0.3,
        placement: str = "diagonal",
        overlay: bool = True,
    ) -> bool:
        """
        Embeds a text watermark into the specified pages (or all pages if None).
        Supports configurable placement, font size, color, and opacity.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if not text.strip():
            raise DocumentError("Watermark text cannot be empty.")

        target_pages = pages if pages is not None else list(range(self._page_count))
        fontname = "helv"

        for p_idx in target_pages:
            if not (0 <= p_idx < self._page_count):
                continue
            page = self._doc[p_idx]
            rect = page.rect
            cx, cy = rect.width / 2.0, rect.height / 2.0
            text_len = pymupdf.get_text_length(text, fontname=fontname, fontsize=fontsize)

            if placement == "diagonal":
                anchor = pymupdf.Point(cx - text_len / 2.0, cy)
                morph = (pymupdf.Point(cx, cy), pymupdf.Matrix(45))
                page.insert_text(
                    anchor,
                    text,
                    fontname=fontname,
                    fontsize=fontsize,
                    color=color,
                    fill_opacity=opacity,
                    morph=morph,
                    overlay=overlay,
                )
            elif placement == "horizontal":
                anchor = pymupdf.Point(cx - text_len / 2.0, cy)
                page.insert_text(
                    anchor,
                    text,
                    fontname=fontname,
                    fontsize=fontsize,
                    color=color,
                    fill_opacity=opacity,
                    overlay=overlay,
                )
            elif placement == "header":
                anchor = pymupdf.Point(cx - text_len / 2.0, 45.0)
                page.insert_text(
                    anchor,
                    text,
                    fontname=fontname,
                    fontsize=fontsize,
                    color=color,
                    fill_opacity=opacity,
                    overlay=overlay,
                )
            elif placement == "footer":
                anchor = pymupdf.Point(cx - text_len / 2.0, rect.height - 35.0)
                page.insert_text(
                    anchor,
                    text,
                    fontname=fontname,
                    fontsize=fontsize,
                    color=color,
                    fill_opacity=opacity,
                    overlay=overlay,
                )

        self._words_cache.clear()
        self._is_modified = True
        return True

    def optimize_document(
        self,
        destination: str | Path,
        garbage: int = 4,
        deflate: bool = True,
        clean: bool = True,
        rewrite_images: bool = False,
        dpi_target: int = 150,
        image_quality: int = 75,
    ) -> Tuple[Path, int, int]:
        """
        Optimizes the document structure, stream deflation, and optionally recompresses images.
        Never overwrites the active source file. Returns (destination_path, original_bytes, new_bytes).
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")

        dest = Path(destination).resolve()
        if self._file_path and dest == self._file_path.resolve():
            raise DocumentError("Optimization output cannot overwrite the active original file directly. Choose a separate destination.")

        orig_size = 0
        if self._file_path and self._file_path.exists():
            orig_size = self._file_path.stat().st_size
        else:
            orig_size = len(self.get_document_bytes())

        if rewrite_images:
            opt_doc = pymupdf.open()
            try:
                opt_doc.insert_pdf(self._doc)
                opt_doc.rewrite_images(dpi_target=dpi_target, quality=image_quality)
                _atomic_save(opt_doc, dest, garbage=garbage, deflate=deflate, clean=clean)
            finally:
                opt_doc.close()
        else:
            _atomic_save(self._doc, dest, garbage=garbage, deflate=deflate, clean=clean)

        new_size = dest.stat().st_size if dest.exists() else 0
        return dest, orig_size, new_size

    def apply_page_structure(self, page_specs: List[Dict[str, Any]]) -> bool:
        """
        Applies a complete reorganized page structure (reorder, rotate, duplicate, delete)
        in a single atomic operation while preserving annotations, links, and remapping TOC.
        Each spec dict has: {'source_index': int, 'rotation_delta': int}.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if not page_specs:
            raise DocumentError("Document must have at least one page.")

        for spec in page_specs:
            src = spec.get("source_index", -1)
            if not (0 <= src < self._page_count):
                raise DocumentError(f"Invalid source page index: {src}")

        orig_toc = self.get_toc()
        new_doc = pymupdf.open()
        old_to_new: Dict[int, int] = {}

        try:
            for new_idx, spec in enumerate(page_specs):
                src = spec["source_index"]
                rot_delta = spec.get("rotation_delta", 0)
                new_doc.insert_pdf(self._doc, from_page=src, to_page=src)
                new_page = new_doc[-1]
                new_page.set_rotation((self._doc[src].rotation + rot_delta) % 360)
                if src not in old_to_new:
                    old_to_new[src] = new_idx

            if orig_toc:
                new_toc = remap_toc_after_reorder(orig_toc, old_to_new)
                try:
                    new_doc.set_toc(new_toc)
                except Exception:
                    pass

            old_doc = self._doc
            self._doc = new_doc
            self._page_count = new_doc.page_count
            self._words_cache.clear()
            self._is_modified = True
            try:
                old_doc.close()
            except Exception:
                pass
            return True
        except Exception as e:
            new_doc.close()
            raise DocumentError(f"Failed to apply page structure: {e}") from e


