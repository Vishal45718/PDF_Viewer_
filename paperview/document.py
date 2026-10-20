"""
Document Management Module for PaperView.
Handles safe opening, password verification, metadata retrieval, TOC extraction,
and document lifecycle using PyMuPDF.
"""

from dataclasses import dataclass, field
import datetime
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
    """
    Saves a document to destination safely using a temporary file and atomic replace.
    Strictly follows 7-step validation:
    1. Write to temporary output.
    2. Close/flush the temporary PDF.
    3. Open the temporary PDF with PyMuPDF.
    4. Verify it opens successfully.
    5. Verify page count is readable.
    6. Close validation handle.
    7. Only then replace destination atomically.
    If validation fails, destination is untouched, temp file is unlinked, and doc is preserved.
    """
    dest = Path(dest).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_file = dest.with_name(f".tmp_{dest.stem}_{uuid.uuid4().hex[:8]}.pdf")
    try:
        # Step 1 & 2: Write to temporary output and close/flush
        doc.save(str(temp_file), garbage=garbage, deflate=deflate, clean=clean)
        if not temp_file.exists() or temp_file.stat().st_size == 0:
            raise DocumentError("Temporary output file was not created or is empty.")

        # Step 3, 4, 5, 6: Open temporary PDF with PyMuPDF, verify, and close handle
        check_doc = None
        try:
            check_doc = pymupdf.open(str(temp_file))
            if check_doc.is_closed or not check_doc.is_pdf:
                raise DocumentError("Saved PDF verification failed: not a valid PDF.")
            # Verify page count is readable
            p_count = check_doc.page_count
            if doc.page_count > 0 and p_count != doc.page_count:
                raise DocumentError(
                    f"Saved PDF verification failed: page count mismatch ({p_count} != {doc.page_count})."
                )
        finally:
            if check_doc is not None:
                try:
                    check_doc.close()
                except Exception:
                    pass

        # Step 7: Only then replace destination atomically
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
        self._words_cache: Dict[int, List[Tuple]] = {}
        self._is_modified: bool = False
        self._is_encrypted: bool = False
        self._undo_stack: List[bytes] = []
        self._redo_stack: List[bytes] = []
        self._undo_max: int = 20

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

        was_encrypted = bool(doc.is_encrypted)
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
        self._is_encrypted: bool = was_encrypted

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
            self._is_encrypted = False
            self._undo_stack.clear()
            self._redo_stack.clear()

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
            is_encrypted=self._is_encrypted,
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
                new_doc.insert_pdf(self._doc, from_page=src, to_page=src, widgets=True, annots=True)
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


    # =========================================================================
    # Milestone 4 – Form Field Support
    # =========================================================================

    def has_form_fields(self) -> bool:
        """Returns True if the document contains any AcroForm fields."""
        if not self.is_open or self._doc is None:
            return False
        try:
            for page in self._doc:
                for _ in page.widgets():
                    return True
        except Exception:
            pass
        return False

    def get_form_fields(self, page_index: int) -> List[Dict[str, Any]]:
        """
        Returns a list of form field descriptors for the specified page.
        Each dict contains: field_name, field_type, field_type_string,
        field_value, rect, xref, choice_values, on_state, is_read_only.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return []
        fields: List[Dict[str, Any]] = []
        try:
            page = self._doc[page_index]
            for widget in page.widgets():
                on_state = widget.on_state() if callable(getattr(widget, "on_state", None)) else getattr(widget, "on_state", "Yes")
                fields.append({
                    "field_name": widget.field_name or "",
                    "name": widget.field_name or "",
                    "field_type": widget.field_type,
                    "field_type_string": widget.field_type_string or "",
                    "type_label": widget.field_type_string or "",
                    "field_value": widget.field_value,
                    "value": widget.field_value,
                    "rect": widget.rect,
                    "xref": widget.xref,
                    "choice_values": widget.choice_values or [],
                    "choices": widget.choice_values or [],
                    "on_state": on_state or "Yes",
                    "is_read_only": bool(getattr(widget, "is_read_only", False)),
                })
        except Exception:
            pass
        return fields

    def get_all_form_fields(self) -> Dict[int, List[Dict[str, Any]]]:
        """Returns form fields for all pages as {page_index: [field_dicts]}."""
        result: Dict[int, List[Dict[str, Any]]] = {}
        if not self.is_open or self._doc is None:
            return result
        for i in range(self._page_count):
            fields = self.get_form_fields(i)
            if fields:
                result[i] = fields
        return result

    def set_form_field_value(self, page_index: int, field_name: str, value: Any) -> bool:
        """
        Sets the value of a named form field on the given page.
        Supports text fields, checkboxes, radio buttons, and choice fields.
        Returns True on success.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            page = self._doc[page_index]
            for widget in page.widgets():
                if widget.field_name == field_name:
                    ft = widget.field_type
                    # Text and choice fields
                    if ft in (pymupdf.PDF_WIDGET_TYPE_TEXT,
                               pymupdf.PDF_WIDGET_TYPE_COMBOBOX,
                               pymupdf.PDF_WIDGET_TYPE_LISTBOX):
                        widget.field_value = str(value)
                    # Checkbox
                    elif ft == pymupdf.PDF_WIDGET_TYPE_CHECKBOX:
                        raw_on = widget.on_state() if callable(getattr(widget, "on_state", None)) else getattr(widget, "on_state", "Yes")
                        on_state = raw_on or "Yes"
                        if isinstance(value, bool):
                            widget.field_value = on_state if value else "Off"
                        elif str(value).lower() in ("yes", "on", "true", "1", on_state.lower()):
                            widget.field_value = on_state
                        else:
                            widget.field_value = "Off"
                    # Radio button
                    elif ft == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                        widget.field_value = str(value)
                    else:
                        widget.field_value = str(value)
                    widget.update()
                    self._is_modified = True
                    return True
        except Exception:
            pass
        return False

    # =========================================================================
    # Milestone 4 – Permanent Redaction
    # =========================================================================

    def add_redaction_region(
        self,
        page_index: int,
        rect: "pymupdf.Rect",
        fill_color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> bool:
        """
        Adds a pending redaction annotation to the given page region.
        This creates a VISIBLE redaction marker (shown as a coloured box with
        a dashed border) but does NOT yet permanently apply the redaction.
        Call apply_redactions() to permanently commit.
        Returns True on success.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            page = self._doc[page_index]
            page.add_redact_annot(rect, fill=fill_color)
            self._is_modified = True
            return True
        except Exception:
            return False

    def get_pending_redactions(self, page_index: int) -> List[Dict[str, Any]]:
        """
        Returns pending (unapplied) redaction annotations on the given page.
        Each dict has: rect, xref.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return []
        result = []
        try:
            page = self._doc[page_index]
            for annot in page.annots(types=[pymupdf.PDF_ANNOT_REDACT]):
                result.append({"rect": annot.rect, "xref": annot.xref})
        except Exception:
            pass
        return result

    def cancel_redaction(self, page_index: int, xref: int) -> bool:
        """Removes a single pending redaction annotation by xref."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            page = self._doc[page_index]
            for annot in page.annots(types=[pymupdf.PDF_ANNOT_REDACT]):
                if annot.xref == xref:
                    page.delete_annot(annot)
                    return True
        except Exception:
            pass
        return False

    def cancel_all_redactions(self, page_index: int) -> int:
        """Removes all pending redactions from the given page. Returns count removed."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return 0
        removed = 0
        try:
            page = self._doc[page_index]
            to_delete = list(page.annots(types=[pymupdf.PDF_ANNOT_REDACT]))
            for annot in to_delete:
                page.delete_annot(annot)
                removed += 1
        except Exception:
            pass
        return removed

    def apply_redactions(self, pages: Optional[List[int]] = None) -> Dict[int, int]:
        """
        Permanently applies all pending redactions on the specified pages (or all
        pages if None).  Uses PyMuPDF's native page.apply_redactions() which
        physically removes the underlying PDF content — the redacted text/images
        can no longer be extracted from the saved PDF.

        Returns a dict {page_index: redactions_applied}.
        WARNING: This operation is DESTRUCTIVE and cannot be undone in memory.
        Always save to a NEW copy; never overwrite the source file.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        target_pages = pages if pages is not None else list(range(self._page_count))
        results: Dict[int, int] = {}
        for p_idx in target_pages:
            if not (0 <= p_idx < self._page_count):
                continue
            try:
                page = self._doc[p_idx]
                # Count pending redactions before applying
                pending_count = sum(1 for _ in page.annots(types=[pymupdf.PDF_ANNOT_REDACT]))
                if pending_count > 0:
                    page.apply_redactions()
                    results[p_idx] = pending_count
                    self._is_modified = True
                    self._words_cache.pop(p_idx, None)
            except Exception as e:
                raise DocumentError(f"Failed to apply redactions on page {p_idx}: {e}") from e
        return results

    # =========================================================================
    # Milestone 4 – Visible Signatures
    # =========================================================================

    def add_visible_signature(
        self,
        page_index: int,
        rect: "pymupdf.Rect",
        signer_name: str,
        signature_text: Optional[str] = None,
        drawn_strokes: Optional[List[List[Tuple[float, float]]]] = None,
        image_bytes: Optional[bytes] = None,
        font_color: Tuple[float, float, float] = (0.08, 0.18, 0.55),
        fill_color: Optional[Tuple[float, float, float]] = (0.96, 0.97, 1.0),
        fontsize: float = 14.0,
        date_str: Optional[str] = None,
    ) -> bool:
        """
        Places a VISIBLE SIGNATURE annotation on the specified page region.

        IMPORTANT DISTINCTION:
        This is a VISIBLE SIGNATURE only — it places styled text or drawn ink that looks like
        a handwritten signature on the page. It does NOT provide:
        - Certificate-based cryptographic signing
        - PKI verification
        - Document authenticity guarantees
        - Tamper-evident digital signatures

        For cryptographic digital signatures, specialized PDF signing software
        with a valid certificate chain is required.

        Returns True on success.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            page = self._doc[page_index]
            display_text = signature_text or signer_name
            if date_str and date_str not in display_text:
                display_text = f"{display_text}\n{date_str}"
            annot_content = f"Signed by: {signer_name}" + (f" on {date_str}" if date_str else "")

            if drawn_strokes:
                # Freehand drawn signature as ink annotation
                annot = page.add_ink_annot(drawn_strokes)
                annot.set_colors(stroke=font_color)
                annot.set_border(width=2)
                annot.set_info(
                    subject="VisibleSignature",
                    content=annot_content,
                    title=signer_name,
                )
                annot.update()
                self._is_modified = True
                return True

            if image_bytes:
                # Embedded image signature
                page.insert_image(rect, stream=image_bytes)
                # Also place tracking annot
                annot = page.add_freetext_annot(
                    rect,
                    "",
                    fontsize=fontsize,
                    text_color=font_color,
                    fill_color=None,
                )
                annot.set_info(
                    subject="VisibleSignature",
                    content=annot_content,
                    title=signer_name,
                )
                annot.update()
                self._is_modified = True
                return True

            # Typed signature as styled freetext annotation
            try:
                annot = page.add_freetext_annot(
                    rect,
                    display_text,
                    fontsize=fontsize,
                    fontname="tiro",  # italic-style for signature feel
                    text_color=font_color,
                    fill_color=fill_color,
                    align=1,  # centered
                    rotate=0,
                )
            except Exception:
                annot = page.add_freetext_annot(
                    rect,
                    display_text,
                    fontsize=fontsize,
                    fontname="helv",
                    text_color=font_color,
                    fill_color=fill_color if fill_color else (1.0, 1.0, 1.0),
                    align=1,
                )
            annot.set_info(
                subject="VisibleSignature",
                content=annot_content,
                title=signer_name,
            )
            annot.update()
            self._is_modified = True
            return True
        except Exception:
            return False

    def get_visible_signatures(self, page_index: int) -> List[Dict[str, Any]]:
        """
        Returns all visible signature annotations on the given page.
        Signatures are identified by subject='VisibleSignature'.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return []
        result = []
        try:
            page = self._doc[page_index]
            for annot in page.annots(types=[pymupdf.PDF_ANNOT_FREE_TEXT, pymupdf.PDF_ANNOT_INK]):
                info = annot.info
                if info.get("subject") == "VisibleSignature":
                    result.append({
                        "rect": annot.rect,
                        "xref": annot.xref,
                        "signer": info.get("title", ""),
                        "signer_name": info.get("title", ""),
                        "content": info.get("content", ""),
                        "type": "VisibleSignature",
                    })
        except Exception:
            pass
        return result

    # =========================================================================
    # Milestone 4 – Stamps
    # =========================================================================

    # Standard predefined stamp names supported by PyMuPDF
    PREDEFINED_STAMPS = [
        "Approved",
        "AsIs",
        "Confidential",
        "Departmental",
        "Draft",
        "Experimental",
        "Expired",
        "Final",
        "ForComment",
        "ForPublicRelease",
        "NotApproved",
        "NotForPublicRelease",
        "Rejected",
        "Sold",
        "TopSecret",
        "Void",
    ]

    # Curated user-facing stamps with display name -> pymupdf name mapping
    USER_STAMPS = {
        "Approved": "Approved",
        "Rejected": "NotApproved",
        "Draft": "Draft",
        "Confidential": "Confidential",
        "Reviewed": "ForComment",
        "Final": "Final",
        "Void": "Void",
        "Top Secret": "TopSecret",
        "Not Approved": "NotApproved",
        "Experimental": "Experimental",
    }

    REVERSE_USER_STAMPS = {
        "Approved": "Approved",
        "NotApproved": "Rejected",
        "Draft": "Draft",
        "Confidential": "Confidential",
        "ForComment": "Reviewed",
        "Final": "Final",
        "Void": "Void",
        "TopSecret": "Top Secret",
        "Experimental": "Experimental",
    }

    def add_stamp(
        self,
        page_index: int,
        rect: "pymupdf.Rect",
        stamp_name: str = "Draft",
    ) -> bool:
        """
        Adds a predefined rubber-stamp annotation to the given page region.
        stamp_name should be a key from USER_STAMPS or a raw PyMuPDF stamp name.
        Returns True on success.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        # Resolve display name -> pymupdf name
        pymupdf_name = self.USER_STAMPS.get(stamp_name, stamp_name)
        try:
            page = self._doc[page_index]
            annot = page.add_stamp_annot(rect)
            annot.set_name(pymupdf_name)
            annot.set_info(title=stamp_name, content=stamp_name)
            annot.update()
            self._is_modified = True
            return True
        except Exception:
            return False

    def get_stamps(self, page_index: int) -> List[Dict[str, Any]]:
        """Returns all stamp annotations on the given page."""
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return []
        result = []
        try:
            page = self._doc[page_index]
            for annot in page.annots(types=[pymupdf.PDF_ANNOT_STAMP]):
                raw_name = annot.info.get("name", "")
                title = annot.info.get("title", "")
                display_name = title if title in self.USER_STAMPS else self.REVERSE_USER_STAMPS.get(raw_name, raw_name)
                result.append({
                    "rect": annot.rect,
                    "xref": annot.xref,
                    "name": display_name or raw_name,
                    "display_name": display_name,
                    "raw_name": raw_name,
                })
        except Exception:
            pass
        return result

    # =========================================================================
    # Milestone 5 — Undo / Redo
    # =========================================================================

    @property
    def can_undo(self) -> bool:
        """True if there is at least one undo snapshot available."""
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """True if there is at least one redo snapshot available."""
        return len(self._redo_stack) > 0

    def push_undo_snapshot(self) -> None:
        """
        Captures the current document state as an undo snapshot.
        Clears the redo stack (new operation invalidates redo history).
        Enforces a maximum stack depth of _undo_max entries.
        """
        if not self.is_open or self._doc is None:
            return
        snapshot = self._doc.tobytes()
        if len(self._undo_stack) >= self._undo_max:
            self._undo_stack.pop(0)
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()

    def snapshot(self) -> bytes:
        """Returns current document bytes without modifying the undo/redo stacks."""
        if not self.is_open or self._doc is None:
            return b""
        return self._doc.tobytes()

    def undo(self) -> bool:
        """
        Restores the document to the previous undo snapshot.
        Pushes the current state to the redo stack.
        Returns True on success, False if no undo snapshot is available.
        """
        if not self._undo_stack:
            return False
        # Save current state for redo
        if self._doc is not None:
            current_bytes = self._doc.tobytes()
            self._redo_stack.append(current_bytes)
        # Restore previous state
        snapshot = self._undo_stack.pop()
        try:
            if self._doc is not None and not self._doc.is_closed:
                self._doc.close()
            self._doc = pymupdf.open(stream=snapshot, filetype="pdf")
            self._page_count = self._doc.page_count
            self._words_cache.clear()
            self._is_modified = True
            return True
        except Exception:
            return False

    def redo(self) -> bool:
        """
        Restores the document to the next redo snapshot.
        Pushes the current state back to the undo stack.
        Returns True on success, False if no redo snapshot is available.
        """
        if not self._redo_stack:
            return False
        # Save current state for undo
        if self._doc is not None:
            current_bytes = self._doc.tobytes()
            self._undo_stack.append(current_bytes)
        # Restore redo state
        snapshot = self._redo_stack.pop()
        try:
            if self._doc is not None and not self._doc.is_closed:
                self._doc.close()
            self._doc = pymupdf.open(stream=snapshot, filetype="pdf")
            self._page_count = self._doc.page_count
            self._words_cache.clear()
            self._is_modified = True
            return True
        except Exception:
            return False

    # =========================================================================
    # Milestone 5 — Page Crop / CropBox
    # =========================================================================

    # Standard page size presets (in PDF points)
    CROP_PRESETS: Dict[str, Any] = {
        "A4": (0, 0, 595, 842),
        "Letter": (0, 0, 612, 792),
    }

    def crop_page(
        self,
        page_index: int,
        rect: "pymupdf.Rect",
        *,
        push_undo: bool = True,
    ) -> bool:
        """
        Sets the CropBox of the specified page to the given rect.

        This changes what is displayed/printed for the page without permanently
        removing any content — the full content is preserved outside the crop
        region until an explicit save. The CropBox is stored in the PDF itself
        and persists after save/reopen.

        The rect must be in PDF page coordinate space (origin at bottom-left,
        y increasing upward — PyMuPDF uses top-left origin, y increasing
        downward, which is what pymupdf.Rect coordinates represent in page space).

        Returns True on success.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            if push_undo:
                self.push_undo_snapshot()
            page = self._doc[page_index]
            page.set_cropbox(rect)
            self._is_modified = True
            self._words_cache.pop(page_index, None)
            return True
        except Exception:
            return False

    def crop_pages(
        self,
        page_indices: List[int],
        rect: "pymupdf.Rect",
        *,
        push_undo: bool = True,
    ) -> int:
        """
        Sets the CropBox on multiple pages.
        A single undo snapshot is taken before the operation.
        Returns the count of pages successfully cropped.
        """
        if not self.is_open or self._doc is None:
            return 0
        if push_undo:
            self.push_undo_snapshot()
        count = 0
        for idx in page_indices:
            if self.crop_page(idx, rect, push_undo=False):
                count += 1
        return count

    def reset_crop(self, page_index: int) -> bool:
        """
        Resets the CropBox to the full MediaBox, restoring the original visible area.
        Returns True on success.
        """
        if not self.is_open or self._doc is None or not (0 <= page_index < self._page_count):
            return False
        try:
            page = self._doc[page_index]
            page.set_cropbox(page.mediabox)
            self._is_modified = True
            self._words_cache.pop(page_index, None)
            return True
        except Exception:
            return False

    # =========================================================================
    # Milestone 5 — Page Labels
    # =========================================================================

    def get_page_labels(self) -> List[str]:
        """
        Returns the page label string for each page.
        Uses page.get_label() which correctly includes prefix and style formatting.
        Falls back to 1-based numeric strings if labels are not set or unavailable.

        Note: In PyMuPDF 1.28.2, doc.get_page_labels() returns the specs list
        (dict format), not per-page label strings. Per-page strings are obtained
        via page.get_label().
        """
        if not self.is_open or self._doc is None:
            return []
        try:
            result = []
            for i in range(self._page_count):
                page = self._doc[i]
                label = page.get_label()
                result.append(label if label else str(i + 1))
            return result
        except Exception:
            return [str(i + 1) for i in range(self._page_count)]

    def set_page_labels(self, specs: List[Dict[str, Any]]) -> bool:
        """
        Sets page label rules on the document.
        specs is a list of dicts with keys: startpage, style, prefix, firstpagenum.
        style values: 'D' (decimal), 'r' (roman lower), 'R' (roman upper),
                      'a' (alpha lower), 'A' (alpha upper), '' (no numbering).
        Returns True on success.
        """
        if not self.is_open or self._doc is None:
            return False
        try:
            self._doc.set_page_labels(specs)
            self._is_modified = True
            return True
        except Exception:
            return False

    # =========================================================================
    # Milestone 5 — Headers & Footers
    # =========================================================================

    def apply_header_footer(
        self,
        config: Dict[str, Any],
        pages: Optional[List[int]] = None,
    ) -> bool:
        """
        Inserts header and footer text into the specified pages.

        config keys:
          header_left, header_center, header_right  — header slot text
          footer_left, footer_center, footer_right  — footer slot text
          font_size: float — default 10.0
          margin: float   — distance from page edge in points, default 20.0

        Template variables substituted in all slot texts:
          {page}     — current page label (1-based fallback)
          {total}    — total page count
          {date}     — today's date (ISO format)
          {filename} — source filename (empty if unsaved)

        Returns True on success.
        """
        if not self.is_open or self._doc is None:
            return False

        target_pages = pages if pages is not None else list(range(self._page_count))
        fs = float(config.get("font_size", 10.0))
        margin = float(config.get("margin", 20.0))
        fontname = "helv"
        total = self._page_count
        today = datetime.date.today().isoformat()
        fname = self._file_path.name if self._file_path else ""

        labels = self.get_page_labels()

        def _substitute(text: str, page_label: str) -> str:
            return (
                text
                .replace("{page}", page_label)
                .replace("{total}", str(total))
                .replace("{date}", today)
                .replace("{filename}", fname)
            )

        def _x_for_slot(slot: str, text: str, page_rect: "pymupdf.Rect") -> float:
            text_width = pymupdf.get_text_length(text, fontname=fontname, fontsize=fs)
            if slot.endswith("_left"):
                return margin
            elif slot.endswith("_center"):
                return (page_rect.width - text_width) / 2.0
            else:  # right
                return max(margin, page_rect.width - text_width - margin)

        header_slots = ["header_left", "header_center", "header_right"]
        footer_slots = ["footer_left", "footer_center", "footer_right"]

        try:
            for p_idx in target_pages:
                if not (0 <= p_idx < self._page_count):
                    continue
                page = self._doc[p_idx]
                rect = page.rect
                page_label = labels[p_idx] if p_idx < len(labels) else str(p_idx + 1)

                # Header: y near top (margin + font size from top edge)
                header_y = margin + fs
                header_y = min(header_y, rect.height - fs)

                for slot in header_slots:
                    raw = config.get(slot, "")
                    if not raw:
                        continue
                    text = _substitute(raw, page_label)
                    x = _x_for_slot(slot, text, rect)
                    x = max(0.0, min(x, rect.width - 1))
                    page.insert_text(
                        pymupdf.Point(x, header_y),
                        text,
                        fontname=fontname,
                        fontsize=fs,
                        overlay=True,
                    )

                # Footer: y near bottom
                footer_y = rect.height - margin
                footer_y = max(fs + 2, footer_y)

                for slot in footer_slots:
                    raw = config.get(slot, "")
                    if not raw:
                        continue
                    text = _substitute(raw, page_label)
                    x = _x_for_slot(slot, text, rect)
                    x = max(0.0, min(x, rect.width - 1))
                    page.insert_text(
                        pymupdf.Point(x, footer_y),
                        text,
                        fontname=fontname,
                        fontsize=fs,
                        overlay=True,
                    )

                self._words_cache.pop(p_idx, None)

            self._is_modified = True
            return True
        except Exception:
            return False

    # =========================================================================
    # Milestone 5 — Export (PDF / PNG / JPEG)
    # =========================================================================

    def export_pages_as_images(
        self,
        page_indices: List[int],
        output_dir: "str | Path",
        fmt: str = "png",
        dpi: int = 150,
        quality: int = 85,
    ) -> List[Path]:
        """
        Exports specified pages as raster images.

        fmt: 'png' or 'jpeg'/'jpg'
        dpi: output resolution (72-600)
        quality: JPEG quality 1-100 (ignored for PNG)

        Returns list of paths to created image files.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        if not page_indices:
            raise DocumentError("No pages specified for export.")

        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        fmt_lower = fmt.lower().lstrip(".")
        if fmt_lower in ("jpg", "jpeg"):
            ext = ".jpg"
            use_jpeg = True
        else:
            ext = ".png"
            use_jpeg = False

        scale = dpi / 72.0
        mat = pymupdf.Matrix(scale, scale)
        created: List[Path] = []

        for idx in page_indices:
            if not (0 <= idx < self._page_count):
                raise DocumentError(f"Page index {idx} out of range.")
            page = self._doc[idx]
            pix = page.get_pixmap(matrix=mat, alpha=False)
            dest = out_dir / f"page_{idx + 1}{ext}"
            if use_jpeg:
                pix.save(str(dest), jpg_quality=quality)
            else:
                pix.save(str(dest))
            created.append(dest)

        return created

    # =========================================================================
    # Milestone 5 — Image Extraction
    # =========================================================================

    def get_embedded_images(
        self, page_index: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns metadata for embedded images in the document.
        If page_index is given, only that page is scanned; otherwise all pages.

        Each dict has: page, xref, width, height, colorspace, ext, name.
        Deduplicates by xref across pages.
        """
        if not self.is_open or self._doc is None:
            return []

        target_pages = [page_index] if page_index is not None else list(range(self._page_count))
        seen_xrefs: set = set()
        result: List[Dict[str, Any]] = []

        for p_idx in target_pages:
            if not (0 <= p_idx < self._page_count):
                continue
            try:
                page = self._doc[p_idx]
                for img_info in page.get_images(full=True):
                    # img_info: (xref, smask, width, height, bpc, colorspace, alt_colorspace, name, filter, referencer)
                    xref = img_info[0]
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)
                    result.append({
                        "page": p_idx,
                        "xref": xref,
                        "width": img_info[2],
                        "height": img_info[3],
                        "colorspace": img_info[5] or "unknown",
                        "name": img_info[7] or f"img_{xref}",
                        "ext": "png",  # resolved on extraction
                    })
            except Exception:
                pass

        return result

    def extract_embedded_image(self, xref: int, dest: "str | Path") -> Path:
        """
        Extracts the raw image data for the given xref from the PDF.
        Writes it to dest (suffix is set to the image's native extension).
        Returns the actual path written.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        try:
            img_info = self._doc.extract_image(xref)
        except Exception as e:
            raise DocumentError(f"Failed to extract image xref={xref}: {e}") from e

        raw_ext = img_info.get("ext", "png")
        dest_path = Path(dest).with_suffix(f".{raw_ext}")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(img_info["image"])
        return dest_path

    # =========================================================================
    # Milestone 5 — PDF Attachments / Embedded Files
    # =========================================================================

    def get_attachments(self) -> List[Dict[str, Any]]:
        """
        Returns metadata for embedded files (attachments) in the document.
        Each dict has: index, name, size, description.
        Returns an empty list if there are no attachments.
        """
        if not self.is_open or self._doc is None:
            return []
        result: List[Dict[str, Any]] = []
        try:
            count = self._doc.embfile_count()
            for i in range(count):
                info = self._doc.embfile_info(i)
                result.append({
                    "index": i,
                    "name": info.get("filename") or info.get("name") or f"attachment_{i}",
                    "size": info.get("size", 0),
                    "description": info.get("desc") or "",
                })
        except Exception:
            pass
        return result

    def extract_attachment(self, index: int, dest: "str | Path") -> Path:
        """
        Extracts the embedded file at the given index to the destination path.
        Returns the path written.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")
        try:
            data = self._doc.embfile_get(index)
        except Exception as e:
            raise DocumentError(f"Failed to extract attachment index={index}: {e}") from e

        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(data)
        return dest_path

    def add_attachment(self, file_path: "str | Path", description: str = "") -> bool:
        """
        Adds a file as an embedded attachment to the document.
        Returns True on success.
        """
        if not self.is_open or self._doc is None:
            return False
        try:
            src = Path(file_path)
            data = src.read_bytes()
            name = src.name
            self._doc.embfile_add(name, data, desc=description, filename=name)
            self._is_modified = True
            return True
        except Exception:
            return False

    # =========================================================================
    # Milestone 5 — Bookmark / TOC Editing
    # =========================================================================

    def add_bookmark(self, title: str, page_index: int, level: int = 1) -> bool:
        """
        Adds a new bookmark entry to the document's Table of Contents.
        level: 1 = top-level, 2 = sub-level, etc.
        page_index: 0-based page index.
        Returns True on success.
        """
        if not self.is_open or self._doc is None:
            return False
        if not (0 <= page_index < self._page_count):
            return False
        try:
            toc = self.get_toc()
            toc.append([level, title, page_index + 1])  # PyMuPDF uses 1-based page numbers
            self._doc.set_toc(toc)
            self._is_modified = True
            return True
        except Exception:
            return False

    def delete_bookmark(self, index: int) -> bool:
        """
        Deletes the bookmark at the given position in the TOC list.
        Returns True on success.
        """
        if not self.is_open or self._doc is None:
            return False
        try:
            toc = self.get_toc()
            if not (0 <= index < len(toc)):
                return False
            del toc[index]
            self._doc.set_toc(toc)
            self._is_modified = True
            return True
        except Exception:
            return False

    def rename_bookmark(self, index: int, new_title: str) -> bool:
        """
        Renames the bookmark at the given TOC index.
        Returns True on success.
        """
        if not self.is_open or self._doc is None:
            return False
        try:
            toc = self.get_toc()
            if not (0 <= index < len(toc)):
                return False
            toc[index][1] = new_title
            self._doc.set_toc(toc)
            self._is_modified = True
            return True
        except Exception:
            return False

    def set_bookmark_page(self, index: int, new_page_index: int) -> bool:
        """
        Changes the target page of the bookmark at the given TOC index.
        new_page_index: 0-based page index.
        Returns True on success.
        """
        if not self.is_open or self._doc is None:
            return False
        if not (0 <= new_page_index < self._page_count):
            return False
        try:
            toc = self.get_toc()
            if not (0 <= index < len(toc)):
                return False
            toc[index][2] = new_page_index + 1  # 1-based
            self._doc.set_toc(toc)
            self._is_modified = True
            return True
        except Exception:
            return False

    # =========================================================================
    # Milestone 5 — Metadata Editing
    # =========================================================================

    def set_metadata(self, meta: Dict[str, str]) -> bool:
        """
        Sets editable document metadata fields.
        Supported keys: title, author, subject, keywords, creator, producer.
        Saves through the document's in-memory state; call save_copy() to persist.
        Returns True on success.
        """
        if not self.is_open or self._doc is None:
            return False
        try:
            self._doc.set_metadata(meta)
            self._is_modified = True
            return True
        except Exception:
            return False

    # =========================================================================
    # Milestone 5 — Security / Password Protection
    # =========================================================================

    def save_protected(
        self,
        dest: "str | Path",
        user_pwd: str,
        owner_pwd: str,
        permissions: int = 0xFFFFFC,
    ) -> Path:
        """
        Saves an AES-256 encrypted copy of the document to the given destination.

        IMPORTANT:
        - This saves a NEW copy; the active source document is never modified.
        - The encryption is applied by PyMuPDF using the PDF standard encryption mechanism.
        - user_pwd: password needed to open/view the document.
        - owner_pwd: password needed to change security settings.
        - permissions: bitmask of allowed operations (see PDF spec).

        Documented limitation:
        PyMuPDF 1.28.2 uses PDF standard AES-256 encryption. The exact cipher
        negotiation depends on the PDF viewer. No certificate-based or PKI
        signing is performed.

        Returns the path of the saved protected file.
        """
        if not self.is_open or self._doc is None:
            raise DocumentError("No document is open.")

        dest_path = Path(dest).resolve()
        if self._file_path and dest_path == self._file_path.resolve():
            raise DocumentError(
                "Cannot overwrite the active source file with the protected copy. "
                "Choose a different destination."
            )

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = dest_path.with_name(
            f".tmp_{dest_path.stem}_{uuid.uuid4().hex[:8]}.pdf"
        )
        try:
            self._doc.save(
                str(temp_file),
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                user_pw=user_pwd,
                owner_pw=owner_pwd,
                permissions=permissions,
                garbage=4,
                deflate=True,
            )

            # Output-PDF validation: verify the saved protected file is encrypted and valid
            check_doc = None
            try:
                check_doc = pymupdf.open(str(temp_file))
                if check_doc.is_closed or not check_doc.is_encrypted:
                    raise DocumentError("Protected PDF verification failed: file is corrupted or unencrypted.")
            finally:
                if check_doc is not None:
                    check_doc.close()

            temp_file.replace(dest_path)
            return dest_path
        except Exception as e:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise DocumentError(f"Failed to save protected PDF: {e}") from e

