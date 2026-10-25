"""
Main Window and UI Orchestrator for PaperView.
Assembles the grouped modern Toolbar, Sidebar, DocumentViewer, SearchBar, and Status Bar.
Handles drag-and-drop, native file pickers, keyboard shortcuts, annotations, view modes, and state.
"""

import sys
from pathlib import Path
from typing import Any, List, Optional
import pymupdf
from PySide6.QtCore import QEvent, QPoint, QSettings, QSize, Qt, QTimer, Slot
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

from paperview.dialogs import AboutDialog, PasswordDialog, PropertiesDialog
from paperview.document import (
    DocumentError,
    DocumentManager,
    InvalidPasswordError,
    PasswordRequiredError,
)
from paperview.icons import get_app_icon, get_icon
from paperview.milestone4_dialogs import (
    FormViewerDialog,
    RedactionDialog,
    SignatureDialog,
    StampDialog,
)
from paperview.milestone5_dialogs import (
    AttachmentDialog,
    BookmarkEditorDialog,
    CropDialog,
    ExportDialog,
    HeaderFooterDialog,
    ImageExtractionDialog,
    SecurityDialog,
)
from paperview.operations_dialogs import (
    MergePDFsDialog,
    OptimizePDFDialog,
    SplitPDFDialog,
    WatermarkDialog,
)
from paperview.organize_dialog import OrganizePagesDialog
from paperview.renderer import RenderManager
from paperview.search import SearchHit, SearchManager
from paperview.search_bar import SearchBar
from paperview.sidebar import Sidebar
from paperview.theme import Theme
from paperview.viewer import DocumentViewer


class MainWindow(QMainWindow):
    """
    PaperView Desktop Application Main Window.
    """

    def __init__(self, initial_file: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle("PaperView — PDF Reader")
        self.setWindowIcon(get_app_icon())
        self.resize(1220, 860)
        self.setMinimumSize(800, 500)
        self.setAcceptDrops(True)

        # Core Managers
        self.doc_mgr = DocumentManager()
        self.render_mgr = RenderManager(max_threads=4, cache_size=32)
        self.search_mgr = SearchManager()

        # Connect renderer and search signals
        self.render_mgr.page_rendered.connect(self._on_page_rendered)
        self.render_mgr.thumbnail_rendered.connect(self._on_thumbnail_rendered)
        self.render_mgr.render_failed.connect(self._on_render_failed)
        self.search_mgr.search_started.connect(self._on_search_started)
        self.search_mgr.search_progress.connect(self._on_search_progress)
        self.search_mgr.search_completed.connect(self._on_search_completed)
        self.search_mgr.current_hit_changed.connect(self._on_current_hit_changed)

        # Apply Global Cohesive Theme
        self.setStyleSheet(Theme.main_stylesheet())

        # Render throttle timer for smooth viewport rendering
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(60)  # ms
        self.render_timer.timeout.connect(self._request_visible_pages)

        # UI Components Assembly
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()
        self._create_central_widget()

        self._rebuild_recent_menu()

        # Open file if supplied
        if initial_file:
            self.open_file_path(initial_file)

    def _create_divider(self) -> QWidget:
        """Creates a subtle, compact vertical divider between toolbar groups."""
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Plain)
        divider.setStyleSheet(f"color: {Theme.BORDER_SUBTLE}; margin: 2px 6px;")
        divider.setFixedHeight(22)
        return divider

    def _create_actions(self) -> None:
        # --- Group A: Document Actions ---
        self.open_act = QAction(get_icon("open"), "Open", self)
        self.open_act.setShortcut(QKeySequence.StandardKey.Open)
        self.open_act.setToolTip("Open PDF Document (Ctrl+O)")
        self.open_act.triggered.connect(self.action_open_file)
        self.addAction(self.open_act)

        self.save_act = QAction(get_icon("save"), "Save", self)
        self.save_act.setShortcut(QKeySequence.StandardKey.Save)
        self.save_act.setToolTip("Save Document (Ctrl+S)")
        self.save_act.triggered.connect(self.action_save)
        self.addAction(self.save_act)

        self.save_as_act = QAction(get_icon("save"), "Save Copy As...", self)
        self.save_as_act.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_act.setToolTip("Save a Separate Copy (Ctrl+Shift+S)")
        self.save_as_act.triggered.connect(self.action_save_as)
        self.addAction(self.save_as_act)

        self.sidebar_act = QAction(get_icon("sidebar"), "Sidebar", self)
        self.sidebar_act.setCheckable(True)
        self.sidebar_act.setChecked(True)
        self.sidebar_act.setToolTip("Toggle Thumbnails & Outline Sidebar")
        self.sidebar_act.triggered.connect(self.action_toggle_sidebar)
        self.addAction(self.sidebar_act)

        # --- Group B: Navigation Actions ---
        self.prev_act = QAction(get_icon("prev"), "Previous", self)
        self.prev_act.setShortcut(QKeySequence("Left"))
        self.prev_act.setToolTip("Previous Page (Left Arrow or PageUp)")
        self.prev_act.triggered.connect(self.action_prev_page)
        self.addAction(self.prev_act)

        self.next_act = QAction(get_icon("next"), "Next", self)
        self.next_act.setShortcut(QKeySequence("Right"))
        self.next_act.setToolTip("Next Page (Right Arrow or PageDown)")
        self.next_act.triggered.connect(self.action_next_page)
        self.addAction(self.next_act)

        # --- Group C: View & Zoom Controls ---
        self.view_mode_act = QAction(get_icon("view_single"), "Single Page", self)
        self.view_mode_act.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.view_mode_act.setToolTip("Toggle Continuous / Single Page View (Ctrl+Shift+P)")
        self.view_mode_act.triggered.connect(self.action_toggle_view_mode)
        self.addAction(self.view_mode_act)

        self.zoom_out_act = QAction(get_icon("zoom_out"), "Zoom Out", self)
        self.zoom_out_act.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.zoom_out_act.setToolTip("Zoom Out (Ctrl+-)")
        self.zoom_out_act.triggered.connect(self.action_zoom_out)
        self.addAction(self.zoom_out_act)

        self.zoom_in_act = QAction(get_icon("zoom_in"), "Zoom In", self)
        self.zoom_in_act.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.zoom_in_act.setToolTip("Zoom In (Ctrl++)")
        self.zoom_in_act.triggered.connect(self.action_zoom_in)
        self.addAction(self.zoom_in_act)

        self.fit_width_act = QAction(get_icon("fit_width"), "Fit Width", self)
        self.fit_width_act.setShortcut(QKeySequence("Ctrl+W"))
        self.fit_width_act.setToolTip("Fit to Window Width (Ctrl+W)")
        self.fit_width_act.triggered.connect(self.action_fit_width)
        self.addAction(self.fit_width_act)

        self.fit_page_act = QAction(get_icon("fit_page"), "Fit Page", self)
        self.fit_page_act.setShortcut(QKeySequence("Ctrl+0"))
        self.fit_page_act.setToolTip("Fit Entire Page in View (Ctrl+0)")
        self.fit_page_act.triggered.connect(self.action_fit_page)
        self.addAction(self.fit_page_act)

        # --- Group D: Edit & Utilities ---
        self.copy_act = QAction("Copy", self)
        self.copy_act.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_act.setToolTip("Copy Selected Text (Ctrl+C)")
        self.copy_act.triggered.connect(self.action_copy_selection)
        self.addAction(self.copy_act)

        self.search_act = QAction(get_icon("find"), "Find", self)
        self.search_act.setShortcut(QKeySequence.StandardKey.Find)
        self.search_act.setToolTip("Find in Document (Ctrl+F)")
        self.search_act.triggered.connect(self.action_toggle_search)
        self.addAction(self.search_act)

        self.properties_act = QAction(get_icon("properties"), "Properties", self)
        self.properties_act.setToolTip("Document Properties & Metadata")
        self.properties_act.triggered.connect(self.action_show_properties)
        self.addAction(self.properties_act)

        # --- Group E: Annotation Tools (Mutually Exclusive) ---
        self.annot_action_group = QActionGroup(self)
        self.annot_action_group.setExclusive(True)

        self.tool_select_act = QAction(get_icon("select"), "Select", self)
        self.tool_select_act.setCheckable(True)
        self.tool_select_act.setChecked(True)
        self.tool_select_act.setShortcut(QKeySequence("V"))
        self.tool_select_act.setToolTip("Text Selection Tool (V)")
        self.tool_select_act.triggered.connect(lambda: self.set_tool_mode("select"))
        self.annot_action_group.addAction(self.tool_select_act)
        self.addAction(self.tool_select_act)

        self.tool_highlight_act = QAction(get_icon("highlight"), "Highlight", self)
        self.tool_highlight_act.setCheckable(True)
        self.tool_highlight_act.setShortcut(QKeySequence("H"))
        self.tool_highlight_act.setToolTip("Highlight Tool (H)")
        self.tool_highlight_act.triggered.connect(lambda: self.set_tool_mode("highlight"))
        self.annot_action_group.addAction(self.tool_highlight_act)
        self.addAction(self.tool_highlight_act)

        self.tool_underline_act = QAction(get_icon("underline"), "Underline", self)
        self.tool_underline_act.setCheckable(True)
        self.tool_underline_act.setShortcut(QKeySequence("U"))
        self.tool_underline_act.setToolTip("Underline Tool (U)")
        self.tool_underline_act.triggered.connect(lambda: self.set_tool_mode("underline"))
        self.annot_action_group.addAction(self.tool_underline_act)
        self.addAction(self.tool_underline_act)

        self.tool_note_act = QAction(get_icon("note"), "Note", self)
        self.tool_note_act.setCheckable(True)
        self.tool_note_act.setShortcut(QKeySequence("N"))
        self.tool_note_act.setToolTip("Sticky Note Tool (N)")
        self.tool_note_act.triggered.connect(lambda: self.set_tool_mode("note"))
        self.annot_action_group.addAction(self.tool_note_act)
        self.addAction(self.tool_note_act)

        self.tool_pen_act = QAction(get_icon("pen"), "Pen", self)
        self.tool_pen_act.setCheckable(True)
        self.tool_pen_act.setShortcut(QKeySequence("P"))
        self.tool_pen_act.setToolTip("Freehand Drawing Pen (P)")
        self.tool_pen_act.triggered.connect(lambda: self.set_tool_mode("pen"))
        self.annot_action_group.addAction(self.tool_pen_act)
        self.addAction(self.tool_pen_act)

        self.tool_redact_act = QAction(get_icon("redact"), "Redact", self)
        self.tool_redact_act.setCheckable(True)
        self.tool_redact_act.setShortcut(QKeySequence("Ctrl+Shift+X"))
        self.tool_redact_act.setToolTip("Redact (Ctrl+Shift+X)")
        self.tool_redact_act.triggered.connect(lambda: self.set_tool_mode("redact"))
        self.annot_action_group.addAction(self.tool_redact_act)
        self.addAction(self.tool_redact_act)

        self.tool_form_act = QAction(get_icon("form"), "Interactive Form Mode", self)
        self.tool_form_act.setCheckable(True)
        self.tool_form_act.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.tool_form_act.setToolTip("Interactive Form Mode (Ctrl+Shift+M)")
        self.tool_form_act.triggered.connect(lambda: self.set_tool_mode("form"))
        self.annot_action_group.addAction(self.tool_form_act)
        self.addAction(self.tool_form_act)

        # --- Group G: Milestone 4 Actions (non-tool-mode) ---
        self.apply_redactions_act = QAction(get_icon("apply_redact"), "Apply Redactions...", self)
        self.apply_redactions_act.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.apply_redactions_act.setToolTip("Apply Redactions... (Ctrl+Shift+A)")
        self.apply_redactions_act.triggered.connect(self.action_manage_redactions)
        self.addAction(self.apply_redactions_act)

        self.stamp_act = QAction(get_icon("stamp"), "Add Stamp...", self)
        self.stamp_act.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.stamp_act.setToolTip("Add Stamp... (Ctrl+Shift+T)")
        self.stamp_act.triggered.connect(self.action_add_stamp)
        self.addAction(self.stamp_act)

        self.sign_act = QAction(get_icon("sign"), "Sign / Fill & Sign...", self)
        self.sign_act.setShortcut(QKeySequence("Ctrl+Shift+G"))
        self.sign_act.setToolTip("Sign / Fill & Sign... (Ctrl+Shift+G)")
        self.sign_act.triggered.connect(self.action_sign_document)
        self.addAction(self.sign_act)

        self.fill_form_act = QAction(get_icon("form"), "Fill Form Dialog...", self)
        self.fill_form_act.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.fill_form_act.setToolTip("Fill Form Dialog... (Ctrl+Shift+F)")
        self.fill_form_act.triggered.connect(self.action_fill_form)
        self.addAction(self.fill_form_act)

        # --- Group F: Page Organization & Document Operations (Milestone 3) ---
        self.organize_act = QAction(get_icon("organize"), "Organize Pages...", self)
        self.organize_act.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.organize_act.setToolTip("Organize, Reorder, Rotate, Delete, Duplicate Pages (Ctrl+Shift+O)")
        self.organize_act.triggered.connect(self.action_organize_pages)
        self.addAction(self.organize_act)

        self.rotate_cw_act = QAction(get_icon("rotate_cw"), "Rotate Clockwise", self)
        self.rotate_cw_act.setShortcut(QKeySequence("Ctrl+R"))
        self.rotate_cw_act.setToolTip("Rotate Current Page 90° Clockwise (Ctrl+R)")
        self.rotate_cw_act.triggered.connect(self.action_rotate_current_page_cw)
        self.addAction(self.rotate_cw_act)

        self.rotate_ccw_act = QAction(get_icon("rotate_ccw"), "Rotate Counterclockwise", self)
        self.rotate_ccw_act.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.rotate_ccw_act.setToolTip("Rotate Current Page 90° Counterclockwise (Ctrl+Shift+R)")
        self.rotate_ccw_act.triggered.connect(self.action_rotate_current_page_ccw)
        self.addAction(self.rotate_ccw_act)

        self.merge_act = QAction(get_icon("merge"), "Merge PDFs...", self)
        self.merge_act.setToolTip("Merge Multiple PDF Files into One Document")
        self.merge_act.triggered.connect(self.action_merge_pdfs)
        self.addAction(self.merge_act)

        self.split_act = QAction(get_icon("split"), "Split PDF...", self)
        self.split_act.setToolTip("Split Document by Page Ranges or Extract Pages")
        self.split_act.triggered.connect(self.action_split_pdf)
        self.addAction(self.split_act)

        self.watermark_act = QAction(get_icon("watermark"), "Add Watermark...", self)
        self.watermark_act.setToolTip("Embed Configurable Watermark Text into Pages")
        self.watermark_act.triggered.connect(self.action_add_watermark)
        self.addAction(self.watermark_act)

        self.optimize_act = QAction(get_icon("optimize"), "Optimize PDF...", self)
        self.optimize_act.setToolTip("Compress Streams, Remove Unused Objects & Reduce File Size")
        self.optimize_act.triggered.connect(self.action_optimize_pdf)
        self.addAction(self.optimize_act)

        # --- Group H: Milestone 5 Actions ---
        self.undo_act = QAction("Undo", self)
        self.undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_act.setToolTip("Undo Last Document Change (Ctrl+Z)")
        self.undo_act.setEnabled(False)
        self.undo_act.triggered.connect(self.action_undo)
        self.addAction(self.undo_act)

        self.redo_act = QAction("Redo", self)
        self.redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_act.setToolTip("Redo Last Undone Change (Ctrl+Y)")
        self.redo_act.setEnabled(False)
        self.redo_act.triggered.connect(self.action_redo)
        self.addAction(self.redo_act)

        self.print_act = QAction("Print...", self)
        self.print_act.setShortcut(QKeySequence.StandardKey.Print)
        self.print_act.setToolTip("Print Document (Ctrl+P)")
        self.print_act.triggered.connect(self.action_print)
        self.addAction(self.print_act)

        self.export_images_act = QAction("Export Pages as Images...", self)
        self.export_images_act.setToolTip("Export Pages as PNG or JPEG Images")
        self.export_images_act.triggered.connect(self.action_export_images)
        self.addAction(self.export_images_act)

        self.crop_act = QAction("Crop Pages...", self)
        self.crop_act.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.crop_act.setToolTip("Set CropBox for One or More Pages (Ctrl+Shift+C)")
        self.crop_act.triggered.connect(self.action_crop_pages)
        self.addAction(self.crop_act)

        self.hf_act = QAction("Header & Footer...", self)
        self.hf_act.setToolTip("Insert Header and Footer Text with Page Number Templates")
        self.hf_act.triggered.connect(self.action_header_footer)
        self.addAction(self.hf_act)

        self.extract_images_act = QAction("Extract Images...", self)
        self.extract_images_act.setToolTip("Inspect and Extract Embedded Images")
        self.extract_images_act.triggered.connect(self.action_extract_images)
        self.addAction(self.extract_images_act)

        self.attachments_act = QAction("Attachments...", self)
        self.attachments_act.setToolTip("View, Add, and Extract Embedded File Attachments")
        self.attachments_act.triggered.connect(self.action_manage_attachments)
        self.addAction(self.attachments_act)

        self.bookmarks_act = QAction("Manage Bookmarks...", self)
        self.bookmarks_act.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.bookmarks_act.setToolTip("Add, Rename, Delete, and Reorganize Bookmarks (Ctrl+Shift+B)")
        self.bookmarks_act.triggered.connect(self.action_manage_bookmarks)
        self.addAction(self.bookmarks_act)

        self.security_act = QAction("Protect with Password...", self)
        self.security_act.setToolTip("Save AES-256 Password-Protected and Permission-Restricted PDF Copy")
        self.security_act.triggered.connect(self.action_security)
        self.addAction(self.security_act)

        # --- Help / About Action ---
        self.about_act = QAction("About PaperView", self)
        self.about_act.setToolTip("Show application information, dependencies, and license")
        self.about_act.triggered.connect(self.action_about)
        self.addAction(self.about_act)

    def _create_menus(self) -> None:
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.open_act)
        self.recent_menu = file_menu.addMenu("Open &Recent")
        file_menu.addSeparator()
        file_menu.addAction(self.save_act)
        file_menu.addAction(self.save_as_act)
        file_menu.addSeparator()
        file_menu.addAction(self.print_act)
        file_menu.addSeparator()
        export_menu = file_menu.addMenu("&Export")
        export_menu.addAction(self.export_images_act)
        file_menu.addSeparator()
        file_menu.addAction(self.properties_act)
        file_menu.addSeparator()

        exit_act = QAction("E&xit", self)
        exit_act.setShortcut(QKeySequence.StandardKey.Quit)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(self.undo_act)
        edit_menu.addAction(self.redo_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.copy_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.search_act)

        # View Menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.view_mode_act)
        view_menu.addSeparator()
        view_menu.addAction(self.zoom_in_act)
        view_menu.addAction(self.zoom_out_act)
        view_menu.addAction(self.fit_width_act)
        view_menu.addAction(self.fit_page_act)
        view_menu.addSeparator()
        view_menu.addAction(self.sidebar_act)

        # Document / Pages Menu (Milestone 3 & 5)
        doc_menu = menubar.addMenu("&Document")
        doc_menu.addAction(self.organize_act)
        doc_menu.addSeparator()
        doc_menu.addAction(self.rotate_cw_act)
        doc_menu.addAction(self.rotate_ccw_act)
        doc_menu.addSeparator()
        doc_menu.addAction(self.crop_act)
        doc_menu.addAction(self.hf_act)
        doc_menu.addSeparator()
        doc_menu.addAction(self.merge_act)
        doc_menu.addAction(self.split_act)
        doc_menu.addSeparator()
        doc_menu.addAction(self.watermark_act)
        doc_menu.addAction(self.optimize_act)
        doc_menu.addSeparator()
        doc_menu.addAction(self.bookmarks_act)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction(self.tool_select_act)
        tools_menu.addAction(self.tool_highlight_act)
        tools_menu.addAction(self.tool_underline_act)
        tools_menu.addAction(self.tool_note_act)
        tools_menu.addAction(self.tool_pen_act)
        tools_menu.addSeparator()
        tools_menu.addAction(self.tool_redact_act)
        tools_menu.addAction(self.apply_redactions_act)
        tools_menu.addSeparator()
        tools_menu.addAction(self.stamp_act)
        tools_menu.addAction(self.sign_act)
        tools_menu.addSeparator()
        tools_menu.addAction(self.tool_form_act)
        tools_menu.addAction(self.fill_form_act)
        tools_menu.addSeparator()
        tools_menu.addAction(self.crop_act)
        tools_menu.addAction(self.hf_act)
        tools_menu.addSeparator()
        tools_menu.addAction(self.extract_images_act)
        tools_menu.addAction(self.attachments_act)
        tools_menu.addSeparator()
        tools_menu.addAction(self.security_act)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self.about_act)

    def _load_recent_files(self) -> List[str]:
        settings = QSettings("PaperView", "PaperView")
        val = settings.value("recent_files", [])
        if isinstance(val, list):
            return [str(item) for item in val if str(item).strip()]
        return []

    def _save_recent_file(self, file_path: str) -> None:
        p_str = str(Path(file_path).resolve())
        files = self._load_recent_files()
        if p_str in files:
            files.remove(p_str)
        files.insert(0, p_str)
        files = files[:10]
        settings = QSettings("PaperView", "PaperView")
        settings.setValue("recent_files", files)
        self._rebuild_recent_menu()

    def _clear_recent_files(self) -> None:
        settings = QSettings("PaperView", "PaperView")
        settings.remove("recent_files")
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        files = self._load_recent_files()
        if not files:
            empty_act = QAction("No Recent Files", self)
            empty_act.setEnabled(False)
            self.recent_menu.addAction(empty_act)
            return

        for f_path in files:
            p = Path(f_path)
            act = QAction(f"{p.name}", self)
            act.setToolTip(f_path)
            act.triggered.connect(lambda checked=False, path=f_path: self.open_file_path(path))
            self.recent_menu.addAction(act)

        self.recent_menu.addSeparator()
        clear_act = QAction("Clear Recent Files", self)
        clear_act.triggered.connect(self._clear_recent_files)
        self.recent_menu.addAction(clear_act)

    def _create_toolbar(self) -> None:
        self.toolbar = QToolBar("Main Controls", self)
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        # --- Group A: Document Actions ---
        btn_open = QToolButton()
        btn_open.setDefaultAction(self.open_act)
        btn_open.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addWidget(btn_open)

        btn_save = QToolButton()
        btn_save.setDefaultAction(self.save_as_act)
        btn_save.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addWidget(btn_save)

        btn_organize = QToolButton()
        btn_organize.setDefaultAction(self.organize_act)
        btn_organize.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addWidget(btn_organize)

        btn_sidebar = QToolButton()
        btn_sidebar.setDefaultAction(self.sidebar_act)
        btn_sidebar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_sidebar)

        btn_undo = QToolButton()
        btn_undo.setDefaultAction(self.undo_act)
        btn_undo.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addWidget(btn_undo)

        btn_redo = QToolButton()
        btn_redo.setDefaultAction(self.redo_act)
        btn_redo.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addWidget(btn_redo)

        self.toolbar.addWidget(self._create_divider())

        # --- Group B: Navigation Controls ---
        btn_prev = QToolButton()
        btn_prev.setDefaultAction(self.prev_act)
        btn_prev.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_prev)

        # Direct page number entry
        self.page_spin = QLineEdit("1")
        self.page_spin.setFixedWidth(44)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_spin.setToolTip("Current Page (Enter to navigate)")
        self.page_spin.returnPressed.connect(self._on_page_entered)
        self.toolbar.addWidget(self.page_spin)

        self.page_total_label = QLabel("/ 0")
        self.page_total_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; margin-right: 4px;")
        self.toolbar.addWidget(self.page_total_label)

        btn_next = QToolButton()
        btn_next.setDefaultAction(self.next_act)
        btn_next.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_next)

        self.toolbar.addWidget(self._create_divider())

        # --- Group C: View & Zoom Controls ---
        btn_view_mode = QToolButton()
        btn_view_mode.setDefaultAction(self.view_mode_act)
        btn_view_mode.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_view_mode)

        btn_zoom_out = QToolButton()
        btn_zoom_out.setDefaultAction(self.zoom_out_act)
        btn_zoom_out.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_zoom_out)

        # Zoom level dropdown
        self.zoom_combo = QComboBox()
        for z in ["50%", "75%", "100%", "125%", "150%", "200%", "300%"]:
            self.zoom_combo.addItem(z)
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setToolTip("Zoom Level")
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_combo_changed)
        self.toolbar.addWidget(self.zoom_combo)

        btn_zoom_in = QToolButton()
        btn_zoom_in.setDefaultAction(self.zoom_in_act)
        btn_zoom_in.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_zoom_in)

        btn_fit_w = QToolButton()
        btn_fit_w.setDefaultAction(self.fit_width_act)
        btn_fit_w.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_fit_w)

        btn_fit_p = QToolButton()
        btn_fit_p.setDefaultAction(self.fit_page_act)
        btn_fit_p.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_fit_p)

        btn_rotate_cw = QToolButton()
        btn_rotate_cw.setDefaultAction(self.rotate_cw_act)
        btn_rotate_cw.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_rotate_cw)

        btn_rotate_ccw = QToolButton()
        btn_rotate_ccw.setDefaultAction(self.rotate_ccw_act)
        btn_rotate_ccw.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_rotate_ccw)

        self.toolbar.addWidget(self._create_divider())

        # --- Group D: Utilities ---
        btn_search = QToolButton()
        btn_search.setDefaultAction(self.search_act)
        btn_search.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addWidget(btn_search)

        btn_props = QToolButton()
        btn_props.setDefaultAction(self.properties_act)
        btn_props.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.toolbar.addWidget(btn_props)

        btn_print = QToolButton()
        btn_print.setDefaultAction(self.print_act)
        btn_print.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toolbar.addWidget(btn_print)

        # =========================================================================
        # Dedicated Annotation & Markup Toolbar (Row 2)
        # =========================================================================
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.annot_toolbar = QToolBar("Annotation Toolbar", self)
        self.annot_toolbar.setMovable(False)
        self.annot_toolbar.setIconSize(QSize(18, 18))
        self.annot_toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {Theme.BG_WINDOW};
                border-bottom: 1px solid {Theme.BORDER_SUBTLE};
                spacing: 2px;
                padding: 2px 4px;
            }}
            QToolButton {{
                padding: 2px 5px;
            }}
        """)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.annot_toolbar)

        # Primary Markup Tools: Select (V), Highlight (H), Underline (U), Note (N), Pen (P)
        btn_select = QToolButton()
        btn_select.setDefaultAction(self.tool_select_act)
        btn_select.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.annot_toolbar.addWidget(btn_select)

        btn_highlight = QToolButton()
        btn_highlight.setDefaultAction(self.tool_highlight_act)
        btn_highlight.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.annot_toolbar.addWidget(btn_highlight)

        btn_underline = QToolButton()
        btn_underline.setDefaultAction(self.tool_underline_act)
        btn_underline.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.annot_toolbar.addWidget(btn_underline)

        btn_note = QToolButton()
        btn_note.setDefaultAction(self.tool_note_act)
        btn_note.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.annot_toolbar.addWidget(btn_note)

        btn_pen = QToolButton()
        btn_pen.setDefaultAction(self.tool_pen_act)
        btn_pen.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.annot_toolbar.addWidget(btn_pen)

        self.annot_toolbar.addWidget(self._create_divider())

        # REDaction group: Redact (Ctrl+Shift+X) & Apply Redactions... (Ctrl+Shift+A)
        btn_redact = QToolButton()
        btn_redact.setDefaultAction(self.tool_redact_act)
        btn_redact.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.annot_toolbar.addWidget(btn_redact)

        btn_apply_redact = QToolButton()
        btn_apply_redact.setDefaultAction(self.apply_redactions_act)
        btn_apply_redact.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.annot_toolbar.addWidget(btn_apply_redact)

        self.annot_toolbar.addWidget(self._create_divider())

        # SIGN & STAMP menu: Add Stamp... (Ctrl+Shift+T) & Sign / Fill & Sign... (Ctrl+Shift+G)
        self.btn_sign_stamp = QToolButton()
        self.btn_sign_stamp.setText("Sign & Stamp")
        self.btn_sign_stamp.setIcon(get_icon("stamp"))
        self.btn_sign_stamp.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_sign_stamp.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_sign_stamp = QMenu(self.btn_sign_stamp)
        menu_sign_stamp.addAction(self.stamp_act)
        menu_sign_stamp.addAction(self.sign_act)
        self.btn_sign_stamp.setMenu(menu_sign_stamp)
        self.btn_sign_stamp.setToolTip("Sign & Stamp — Add Stamp (Ctrl+Shift+T) / Sign Document (Ctrl+Shift+G)")
        self.annot_toolbar.addWidget(self.btn_sign_stamp)

        self.annot_toolbar.addWidget(self._create_divider())

        # FORMS menu: Interactive Form Mode (Ctrl+Shift+M) & Fill Form Dialog... (Ctrl+Shift+F)
        self.btn_forms = QToolButton()
        self.btn_forms.setDefaultAction(self.tool_form_act)
        self.btn_forms.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_forms.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        menu_forms = QMenu(self.btn_forms)
        menu_forms.addAction(self.tool_form_act)
        menu_forms.addAction(self.fill_form_act)
        self.btn_forms.setMenu(menu_forms)
        self.btn_forms.setToolTip("Forms — Interactive Form Mode (Ctrl+Shift+M) / Fill Form Dialog (Ctrl+Shift+F)")
        self.annot_toolbar.addWidget(self.btn_forms)

    def _create_statusbar(self) -> None:
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; padding-left: 4px;")
        self.status_bar.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(130)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {Theme.BORDER_INPUT};
                border-radius: 2px;
                background-color: {Theme.BG_INPUT};
            }}
            QProgressBar::chunk {{
                background-color: {Theme.ACCENT};
            }}
        """)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.doc_info_label = QLabel("")
        self.doc_info_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px; padding-right: 8px;")
        self.status_bar.addPermanentWidget(self.doc_info_label)

    def _create_central_widget(self) -> None:
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Search bar (docked above document workspace)
        self.search_bar = SearchBar(self)
        self.search_bar.hide()
        self.search_bar.search_requested.connect(self._on_search_bar_query)
        self.search_bar.next_match_requested.connect(self._on_search_next)
        self.search_bar.prev_match_requested.connect(self._on_search_prev)
        self.search_bar.closed.connect(self._on_search_closed)
        central_layout.addWidget(self.search_bar)

        # Splitter: Sidebar | DocumentViewer
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.sidebar = Sidebar()
        self.sidebar.page_selected.connect(self.navigate_to_page)
        self.splitter.addWidget(self.sidebar)

        self.viewer = DocumentViewer()
        self.viewer.page_changed.connect(self._on_viewer_page_changed)
        self.viewer.link_triggered.connect(self._on_link_triggered)
        self.viewer.zoom_changed.connect(self._on_viewer_zoom_changed)
        self.viewer.text_selected.connect(self._on_text_selected)
        self.viewer.annotation_created.connect(self._on_annotation_created)
        self.viewer.form_field_interacted.connect(self._on_form_field_interacted)
        self.viewer.scrolled.connect(self.render_timer.start)
        self.splitter.addWidget(self.viewer)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        central_layout.addWidget(self.splitter, 1)

        self.setCentralWidget(central)

    # Drag and Drop Support
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(".pdf") for u in urls):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        for u in urls:
            path = u.toLocalFile()
            if path.lower().endswith(".pdf"):
                self.open_file_path(path)
                break

    # Document Opening & Password Handling
    def action_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF Document",
            str(Path.home() / "Desktop"),
            "PDF Files (*.pdf);;All Files (*)",
        )
        if file_path:
            self.open_file_path(file_path)

    def action_about(self) -> None:
        """Opens the About dialog displaying application metadata, environment, and licensing."""
        dlg = AboutDialog(self)
        dlg.exec()

    def open_file_path(self, path_str: str) -> None:
        """Opens and initializes the document, requesting password if protected."""
        if path_str.startswith("file://"):
            from PySide6.QtCore import QUrl
            path_str = QUrl(path_str).toLocalFile()
        p = Path(path_str).expanduser().resolve()
        if not p.is_file():
            sys.stderr.write(f"[PaperView Error] File not found: {p}\n")
            QMessageBox.critical(self, "Error", f"File not found:\n{p}")
            return

        password = None
        while True:
            try:
                self.status_label.setText(f"Opening {p.name}...")
                metadata = self.doc_mgr.open_document(p, password=password)
                break  # Successfully opened
            except PasswordRequiredError:
                dlg = PasswordDialog(p.name, self)
                if dlg.exec():
                    password = dlg.get_password()
                else:
                    self.status_label.setText("Open cancelled (password required).")
                    return
            except InvalidPasswordError:
                dlg = PasswordDialog(p.name, self)
                dlg.show_error("Incorrect password. Please try again.")
                if dlg.exec():
                    password = dlg.get_password()
                else:
                    self.status_label.setText("Open cancelled.")
                    return
            except Exception as e:
                sys.stderr.write(f"[PaperView Error] Failed to open document {p}: {e}\n")
                QMessageBox.critical(self, "Failed to Open PDF", f"Error opening document:\n{e}")
                self.status_label.setText("Failed to open document.")
                return

        # Document successfully opened!
        self.setWindowTitle(f"{p.name} — PaperView")
        self.page_total_label.setText(f"/ {metadata.page_count}")
        self._update_status_bar()

        # Update render and search managers
        self.render_mgr.set_document(str(p), password=password)
        self.search_mgr.set_document(str(p), password=password)

        # Configure viewer
        self.viewer.set_document(metadata.page_count, metadata.page_dimensions)
        for i in range(metadata.page_count):
            links = self.doc_mgr.get_page_links(i)
            self.viewer.update_page_links(i, links)
            fields = self.doc_mgr.get_form_fields(i)
            self.viewer.set_page_form_fields(i, fields)
            redactions = self.doc_mgr.get_pending_redactions(i)
            self.viewer.set_page_pending_redactions(i, redactions)

        # Configure sidebar
        self.sidebar.set_page_count(metadata.page_count)
        toc = self.doc_mgr.get_toc()
        self.sidebar.set_toc(toc)

        # Remember in recent files list
        self._save_recent_file(str(p))

        # Initial render of visible pages + thumbnails
        self.navigate_to_page(0)
        self._request_visible_pages()
        self._start_thumbnail_generation()

        if self.doc_mgr.has_form_fields():
            self.status_label.setText(f"Opened {p.name} — Interactive form fields detected (Use Form Mode to edit)")
        else:
            self.status_label.setText(f"Opened {p.name}")

    def _start_thumbnail_generation(self) -> None:
        """Kicks off thumbnail requests for the first batch of pages."""
        if not self.doc_mgr.is_open:
            return
        dpr = float(self.devicePixelRatioF()) if hasattr(self, "devicePixelRatioF") else float(self.devicePixelRatio())
        limit = min(self.doc_mgr.page_count, 25)
        for i in range(limit):
            img = self.render_mgr.request_page(i, 0.25, is_thumbnail=True, dpr=dpr)
            if img is not None:
                self.sidebar.set_thumbnail_image(i, img)

    # Save and Save Copy As
    def action_save(self) -> None:
        """Saves current document. If not yet a designated copy, prompts Save Copy As."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        if not self.doc_mgr.is_modified:
            self.status_label.setText("Document has no unsaved changes.")
            return
        self.action_save_as()

    def action_save_as(self) -> bool:
        """
        Saves a copy safely to a new file without modifying or overwriting the original.
        """
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return False

        curr_path = self.doc_mgr.file_path
        default_name = f"{curr_path.stem}_edited.pdf" if curr_path else "document_edited.pdf"
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF Copy As",
            str(Path.home() / "Desktop" / default_name),
            "PDF Files (*.pdf)",
        )
        if not dest:
            return False

        dest_path = Path(dest).resolve()
        if curr_path and dest_path == curr_path.resolve():
            QMessageBox.warning(
                self,
                "Invalid Destination",
                "To protect your original document, Save As cannot overwrite the active file directly.\nPlease specify a different filename.",
            )
            return False

        try:
            saved = self.doc_mgr.save_copy(dest_path)
            self.status_label.setText(f"Saved copy to {saved.name}")
            if self.doc_mgr.file_path:
                self.setWindowTitle(f"{self.doc_mgr.file_path.name} — PaperView")
            self._save_recent_file(str(saved))
            QMessageBox.information(self, "Saved", f"A separate copy was safely saved to:\n{saved}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save document:\n{e}")
            return False

    def _reload_after_modification(self) -> None:
        """
        Synchronizes all UI components after document modifications
        (page rotation, reordering, deletion, duplication, watermarking).
        """
        if not self.doc_mgr.is_open:
            return

        metadata = self.doc_mgr.get_metadata()
        curr_page = min(self.viewer.current_page, max(0, metadata.page_count - 1))
        curr_page = max(0, curr_page)

        # Update labels & window title with modified indicator
        p_name = self.doc_mgr.file_path.name if self.doc_mgr.file_path else "Untitled"
        self.setWindowTitle(f"*{p_name} — PaperView (Unsaved Changes)")
        self.page_total_label.setText(f"/ {metadata.page_count}")
        self._update_status_bar()

        # Update in-memory document state in render and search managers
        doc_bytes = self.doc_mgr.get_document_bytes()
        self.render_mgr.set_doc_bytes(doc_bytes)
        self.search_mgr.set_doc_bytes(doc_bytes)

        # Reconfigure viewer pages & dimensions
        self.viewer.set_document(metadata.page_count, metadata.page_dimensions)
        for i in range(metadata.page_count):
            links = self.doc_mgr.get_page_links(i)
            self.viewer.update_page_links(i, links)

        # Reconfigure sidebar
        self.sidebar.set_page_count(metadata.page_count)
        toc = self.doc_mgr.get_toc()
        self.sidebar.set_toc(toc)

        # Re-render visible pages and thumbnails
        self.navigate_to_page(curr_page)
        self._request_visible_pages()
        self._start_thumbnail_generation()
        self.status_label.setText("Document updated with unsaved changes. (Use Save Copy As to persist)")

    def action_organize_pages(self) -> None:
        """Opens the Organize Pages workspace dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = OrganizePagesDialog(self.doc_mgr, self)
        dlg.pages_applied.connect(self._reload_after_modification)
        dlg.exec()

    def action_rotate_current_page_cw(self) -> None:
        """Rotates the current page 90 degrees clockwise."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        p_idx = self.viewer.current_page
        self.doc_mgr.push_undo_snapshot()
        self.doc_mgr.rotate_page(p_idx, 90)
        self._reload_after_modification()
        self.status_label.setText(f"Rotated page {p_idx + 1} 90° clockwise.")

    def action_rotate_current_page_ccw(self) -> None:
        """Rotates the current page 90 degrees counter-clockwise."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        p_idx = self.viewer.current_page
        self.doc_mgr.push_undo_snapshot()
        self.doc_mgr.rotate_page(p_idx, -90)
        self._reload_after_modification()
        self.status_label.setText(f"Rotated page {p_idx + 1} 90° counterclockwise.")

    def action_merge_pdfs(self) -> None:
        """Opens the Merge PDFs dialog."""
        dlg = MergePDFsDialog(self)
        dlg.merged_file_ready.connect(self.open_file_path)
        dlg.exec()

    def action_split_pdf(self) -> None:
        """Opens the Split PDF dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = SplitPDFDialog(self.doc_mgr, self)
        dlg.exec()

    def action_add_watermark(self) -> None:
        """Opens the Add Watermark dialog with interactive live preview."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = WatermarkDialog(self.doc_mgr, self.viewer.current_page, self)
        dlg.watermark_applied.connect(self._reload_after_modification)
        dlg.exec()

    def action_optimize_pdf(self) -> None:
        """Opens the Optimize PDF dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = OptimizePDFDialog(self.doc_mgr, self)
        dlg.optimized_file_ready.connect(
            lambda saved: QMessageBox.information(
                self,
                "Optimization Complete",
                f"Optimized copy successfully saved to:\n{saved}",
            )
        )
        dlg.exec()

    # Tool Mode Selection
    def set_tool_mode(self, mode: str) -> None:
        self.viewer.set_tool_mode(mode)
        mode_actions = {
            "select": self.tool_select_act,
            "highlight": self.tool_highlight_act,
            "underline": self.tool_underline_act,
            "note": self.tool_note_act,
            "pen": self.tool_pen_act,
            "redact": self.tool_redact_act,
            "form": self.tool_form_act,
        }
        act = mode_actions.get(mode)
        if act and not act.isChecked():
            act.setChecked(True)

        tool_names = {
            "select": "Text Selection",
            "highlight": "Highlight Annotation",
            "underline": "Underline Annotation",
            "note": "Sticky Note",
            "pen": "Freehand Pen",
            "redact": "Redact — Draw region to mark for permanent redaction",
            "form": "Form Mode — Click interactive fields on page to edit",
        }
        name = tool_names.get(mode, mode.title())
        self.status_label.setText(f"Active Tool: {name}")

    # View Mode Toggle (Continuous vs Single Page)
    def action_toggle_view_mode(self) -> None:
        if self.viewer.view_mode == "continuous":
            self.viewer.set_view_mode("single")
            self.view_mode_act.setIcon(get_icon("view_continuous"))
            self.view_mode_act.setText("Continuous View")
            self.view_mode_act.setToolTip("Switch to Continuous Scroll View (Ctrl+Shift+P)")
            self.status_label.setText("Switched to Single Page View")
        else:
            self.viewer.set_view_mode("continuous")
            self.view_mode_act.setIcon(get_icon("view_single"))
            self.view_mode_act.setText("Single Page")
            self.view_mode_act.setToolTip("Switch to Single Page View (Ctrl+Shift+P)")
            self.status_label.setText("Switched to Continuous Scroll View")
        self.render_timer.start()

    # Text Selection and Clipboard
    def _on_text_selected(self, page_index: int, text: str) -> None:
        if text:
            word_count = len(text.split())
            char_count = len(text)
            self.status_label.setText(
                f"Selected {word_count} word(s), {char_count} char(s) on page {page_index + 1} — Press Ctrl+C to copy"
            )

    def action_copy_selection(self) -> None:
        copied = self.viewer.copy_selection()
        if copied:
            self.status_label.setText("Copied selected text to system clipboard.")
        else:
            self.status_label.setText("No text selected to copy.")

    # Annotation Handling
    def _on_annotation_created(self, annot_type: str, page_index: int, data: Any) -> None:
        if not self.doc_mgr.is_open:
            return

        if annot_type != "redact":
            self.doc_mgr.push_undo_snapshot()

        success = False
        if annot_type == "highlight":
            success = self.doc_mgr.add_highlight_annotation(page_index, data)
        elif annot_type == "underline":
            success = self.doc_mgr.add_underline_annotation(page_index, data)
        elif annot_type == "note":
            success = self.doc_mgr.add_text_annotation(page_index, data["point"], data["text"])
        elif annot_type == "ink":
            success = self.doc_mgr.add_ink_annotation(page_index, data)
        elif annot_type == "redact":
            # data is a pymupdf.Rect (page-space coordinates)
            r = pymupdf.Rect(data[0], data[1], data[2], data[3])
            success = self.doc_mgr.add_redaction_region(page_index, r)
            if success:
                self.viewer.set_page_pending_redactions(
                    page_index, self.doc_mgr.get_pending_redactions(page_index)
                )
                pending = sum(
                    len(self.doc_mgr.get_pending_redactions(i))
                    for i in range(self.doc_mgr.page_count)
                )
                self.status_label.setText(
                    f"Redaction region added on page {page_index + 1} — "
                    f"{pending} pending. Use 'Apply Redactions' to commit permanently."
                )

        if success:
            # Update background render manager with serialized modified document bytes
            self.render_mgr.set_doc_bytes(self.doc_mgr.get_document_bytes())
            self._request_visible_pages()
            self._update_status_bar()
            if self.doc_mgr.file_path:
                self.setWindowTitle(f"*{self.doc_mgr.file_path.name} — PaperView")
            if annot_type != "redact":
                self.status_label.setText(
                    f"Created {annot_type} annotation on page {page_index + 1} (Unsaved changes)"
                )

    # --- Milestone 4 Action Handlers ---

    def action_manage_redactions(self) -> None:
        """Opens the Redaction Manager dialog to review and apply permanent redactions."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = RedactionDialog(self.doc_mgr, self)
        dlg.redactions_applied.connect(self._on_redactions_applied)
        dlg.exec()

    def _on_redactions_applied(self) -> None:
        """Called after permanent redaction application — refreshes viewer."""
        for i in range(self.doc_mgr.page_count):
            self.viewer.set_page_pending_redactions(i, [])
        self.render_mgr.set_doc_bytes(self.doc_mgr.get_document_bytes())
        self.render_mgr.clear_cache()
        self._request_visible_pages()
        if self.doc_mgr.file_path:
            self.setWindowTitle(f"*{self.doc_mgr.file_path.name} — PaperView (Redacted, Unsaved)")
        self.status_label.setText(
            "Redactions applied — underlying content permanently removed. "
            "Use Save Copy As to persist."
        )

    def action_add_stamp(self) -> None:
        """Opens the Stamp dialog to place a rubber stamp on the current page."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = StampDialog(self.doc_mgr, self.viewer.current_page, self)
        dlg.stamp_placed.connect(self._on_stamp_or_signature_placed)
        dlg.exec()

    def action_sign_document(self) -> None:
        """Opens the Signature dialog to place a visible signature."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = SignatureDialog(self.doc_mgr, self.viewer.current_page, self)
        dlg.signature_ready.connect(self._on_stamp_or_signature_placed)
        dlg.exec()

    def _on_stamp_or_signature_placed(self, *args: Any) -> None:
        """Refreshes the viewer after a stamp or visible signature is placed."""
        self.render_mgr.set_doc_bytes(self.doc_mgr.get_document_bytes())
        self.render_mgr.clear_cache()
        self._request_visible_pages()
        if self.doc_mgr.file_path:
            self.setWindowTitle(f"*{self.doc_mgr.file_path.name} — PaperView")
        self.status_label.setText("Stamp/Signature placed. Use Save Copy As to persist.")

    def action_fill_form(self) -> None:
        """Opens the Form Viewer/Filler dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = FormViewerDialog(self.doc_mgr, self)
        dlg.fields_applied.connect(self._on_form_fields_applied)
        dlg.exec()

    def _on_form_fields_applied(self) -> None:
        """Refreshes viewer after form fields are filled."""
        for i in range(self.doc_mgr.page_count):
            self.viewer.set_page_form_fields(i, self.doc_mgr.get_form_fields(i))
        self.render_mgr.set_doc_bytes(self.doc_mgr.get_document_bytes())
        self.render_mgr.clear_cache()
        self._request_visible_pages()
        if self.doc_mgr.file_path:
            self.setWindowTitle(f"*{self.doc_mgr.file_path.name} — PaperView")
        self.status_label.setText("Form fields updated. Use Save Copy As to persist.")

    def _on_form_field_interacted(self, page_index: int, field_name: str, value: Any) -> None:
        """Called when user clicks or fills a form field directly on a page in the viewer."""
        if not self.doc_mgr.is_open:
            return
        ok = self.doc_mgr.set_form_field_value(page_index, field_name, value)
        if ok:
            self._on_form_fields_applied()
            self.status_label.setText(f"Updated form field '{field_name}' on page {page_index + 1}")

    # Properties Dialog
    def action_show_properties(self) -> None:
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        meta = self.doc_mgr.get_metadata()
        dlg = PropertiesDialog(meta, parent=self, doc_manager=self.doc_mgr)
        dlg.exec()
        if self.doc_mgr.is_modified:
            self._reload_after_modification()

    # --- Milestone 5 Action Handlers ---

    def action_undo(self) -> None:
        """Undoes the last mutating document operation."""
        if not self.doc_mgr.is_open:
            return
        if self.doc_mgr.undo():
            self._reload_after_modification()
            self.status_label.setText("Undo successful.")
        else:
            self.status_label.setText("Nothing to undo.")
        self._update_undo_redo_actions()

    def action_redo(self) -> None:
        """Redoes the last undone document operation."""
        if not self.doc_mgr.is_open:
            return
        if self.doc_mgr.redo():
            self._reload_after_modification()
            self.status_label.setText("Redo successful.")
        else:
            self.status_label.setText("Nothing to redo.")
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self) -> None:
        if hasattr(self, "undo_act"):
            self.undo_act.setEnabled(self.doc_mgr.can_undo)
        if hasattr(self, "redo_act"):
            self.redo_act.setEnabled(self.doc_mgr.can_redo)

    def action_print(self) -> None:
        """Prints the document using Qt Print Support."""
        if not self.doc_mgr.is_open or self.doc_mgr.page_count == 0:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setDocName(self.doc_mgr.file_path.name if self.doc_mgr.file_path else "PaperView Document")

        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Document")
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return

        from_page = printer.fromPage()
        to_page = printer.toPage()
        total_pages = self.doc_mgr.page_count

        if from_page == 0 and to_page == 0:
            page_range = range(total_pages)
        else:
            start_idx = max(0, from_page - 1)
            end_idx = min(total_pages, to_page)
            page_range = range(start_idx, end_idx)

        painter = QPainter(printer)
        try:
            first = True
            for p_idx in page_range:
                if not first:
                    printer.newPage()
                first = False

                page = self.doc_mgr.doc[p_idx]
                mat = pymupdf.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()

                rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                scaled_size = qimg.size().scaled(rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
                x = (rect.width() - scaled_size.width()) / 2
                y = (rect.height() - scaled_size.height()) / 2
                painter.drawImage(
                    int(x), int(y),
                    qimg.scaled(scaled_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
        finally:
            painter.end()

        self.status_label.setText("Print job sent successfully.")

    def action_crop_pages(self) -> None:
        """Opens the Crop Pages dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = CropDialog(self.doc_mgr, self.viewer.current_page, self)
        dlg.crop_applied.connect(self._reload_after_modification)
        dlg.exec()

    def action_header_footer(self) -> None:
        """Opens the Header & Footer dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = HeaderFooterDialog(self.doc_mgr, self)
        dlg.hf_applied.connect(self._reload_after_modification)
        dlg.exec()

    def action_export_images(self) -> None:
        """Opens the Export Pages as Images dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = ExportDialog(self.doc_mgr, self)
        dlg.exec()

    def action_extract_images(self) -> None:
        """Opens the Extract Embedded Images dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = ImageExtractionDialog(self.doc_mgr, self)
        dlg.exec()

    def action_manage_attachments(self) -> None:
        """Opens the Attachments dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = AttachmentDialog(self.doc_mgr, self)
        dlg.exec()

    def action_manage_bookmarks(self) -> None:
        """Opens the Bookmark Editor dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = BookmarkEditorDialog(self.doc_mgr, self)
        dlg.bookmarks_changed.connect(self._reload_after_modification)
        dlg.exec()

    def action_security(self) -> None:
        """Opens the Security & Password Protection dialog."""
        if not self.doc_mgr.is_open:
            QMessageBox.information(self, "No Document", "Please open a document first.")
            return
        dlg = SecurityDialog(self.doc_mgr, self)
        dlg.exec()

    def _update_status_bar(self) -> None:
        """Updates status bar with professional document information."""
        if not self.doc_mgr.is_open or self.doc_mgr.page_count == 0:
            self.doc_info_label.setText("")
            self._update_undo_redo_actions()
            return

        curr_idx = self.viewer.current_page
        total = self.doc_mgr.page_count
        curr_num = curr_idx + 1

        label_str = ""
        try:
            labels = self.doc_mgr.get_page_labels()
            if curr_idx < len(labels):
                lbl = labels[curr_idx]
                if lbl and lbl != str(curr_num):
                    label_str = f" [{lbl}]"
        except Exception:
            pass

        page_part = f"Page {curr_num} of {total}{label_str}"

        zoom_val = int(round(self.viewer.zoom * 100))
        zoom_part = f"{zoom_val}%"

        meta = self.doc_mgr.get_metadata()
        ver_part = meta.format_version if meta.format_version else "PDF"

        size_part = ""
        if self.doc_mgr.file_path and self.doc_mgr.file_path.exists():
            mb = self.doc_mgr.file_path.stat().st_size / (1024 * 1024)
            size_part = f"{mb:.1f} MB"
        else:
            try:
                b = len(self.doc_mgr.get_document_bytes())
                size_part = f"{b / (1024 * 1024):.1f} MB"
            except Exception:
                pass

        parts = [page_part, zoom_part, ver_part]
        if size_part:
            parts.append(size_part)
        if self.doc_mgr.is_modified:
            parts.append("*Modified")

        self.doc_info_label.setText("  |  ".join(parts))
        self._update_undo_redo_actions()

    # Navigation Actions
    def action_prev_page(self) -> None:
        if self.viewer.current_page > 0:
            self.navigate_to_page(self.viewer.current_page - 1)

    def action_next_page(self) -> None:
        if self.viewer.current_page < self.doc_mgr.page_count - 1:
            self.navigate_to_page(self.viewer.current_page + 1)

    def navigate_to_page(self, page_index: int) -> None:
        if not self.doc_mgr.is_open or self.doc_mgr.page_count == 0:
            return
        target = max(0, min(page_index, self.doc_mgr.page_count - 1))
        self.viewer.scroll_to_page(target)
        self.sidebar.select_thumbnail(target)
        self.page_spin.setText(str(target + 1))
        self._update_status_bar()
        self.render_timer.start()

    def _on_page_entered(self) -> None:
        try:
            num = int(self.page_spin.text().strip())
            self.navigate_to_page(num - 1)
        except ValueError:
            self.page_spin.setText(str(self.viewer.current_page + 1))

    # Zoom Actions
    def action_zoom_in(self) -> None:
        self.viewer.zoom_in()
        self.render_timer.start()

    def action_zoom_out(self) -> None:
        self.viewer.zoom_out()
        self.render_timer.start()

    def action_fit_width(self) -> None:
        self.viewer.fit_width()
        self.render_timer.start()

    def action_fit_page(self) -> None:
        self.viewer.fit_page()
        self.render_timer.start()

    def _on_zoom_combo_changed(self, text: str) -> None:
        if "%" in text:
            try:
                val = float(text.replace("%", "").strip()) / 100.0
                self.viewer.set_zoom(val)
                self.render_timer.start()
            except ValueError:
                pass

    @Slot(float)
    def _on_viewer_zoom_changed(self, zoom: float) -> None:
        pct = f"{int(round(zoom * 100))}%"
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(pct)
        self.zoom_combo.blockSignals(False)
        self._update_status_bar()
        self.render_timer.start()

    # Sidebar Toggle
    def action_toggle_sidebar(self) -> None:
        self.sidebar.setVisible(self.sidebar_act.isChecked())

    # Search Actions
    def action_toggle_search(self) -> None:
        if self.search_bar.isVisible():
            self.search_bar.hide_bar()
        else:
            self.search_bar.show_and_focus()

    def _on_search_bar_query(self, query: str, case_sensitive: bool) -> None:
        self.search_bar.set_searching_status()
        self.search_mgr.start_search(query, case_sensitive)

    def _on_search_started(self, query: str) -> None:
        self.status_label.setText(f"Searching for '{query}'...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

    def _on_search_progress(self, current: int, total: int) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_search_completed(self, hits: list) -> None:
        self.progress_bar.hide()
        total = len(hits)
        curr = 1 if total > 0 else 0
        self.search_bar.set_match_status(curr, total)
        self.status_label.setText(f"Search complete: {total} match(es) found")
        self.render_mgr.clear_cache()
        self._request_visible_pages()

    def _on_search_next(self) -> None:
        self.search_mgr.next_hit()

    def _on_search_prev(self) -> None:
        self.search_mgr.prev_hit()

    def _on_current_hit_changed(self, index: int, hit: SearchHit) -> None:
        self.search_bar.set_match_status(index + 1, len(self.search_mgr.hits))
        self.navigate_to_page(hit.page_index)
        self.status_label.setText(f"Match {index + 1}/{len(self.search_mgr.hits)}: {hit.snippet}")

    def _on_search_closed(self) -> None:
        self.search_mgr.cancel_search()
        self.search_mgr.hits.clear()
        self.render_mgr.clear_cache()
        self._request_visible_pages()

    # Viewer & Renderer Signals
    @Slot(int)
    def _on_viewer_page_changed(self, page_index: int) -> None:
        self.page_spin.setText(str(page_index + 1))
        self.sidebar.select_thumbnail(page_index)
        self._update_status_bar()
        self.render_timer.start()

    @Slot(dict)
    def _on_link_triggered(self, link: dict) -> None:
        # Safe link dispatch
        kind = link.get("kind")
        if kind == 1:  # LINK_GOTO (internal page)
            target = link.get("page")
            if target is not None:
                self.navigate_to_page(target)
                self.status_label.setText(f"Jumped to page {target + 1}")
        elif kind == 2:  # LINK_URI
            uri = link.get("uri", "")
            self.status_label.setText(f"Document Link: {uri}")
            res = QMessageBox.question(
                self,
                "Follow Link",
                f"The document wants to open this URL:\n\n{uri}\n\nDo you want to open it in your browser?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if res == QMessageBox.StandardButton.Yes:
                import webbrowser
                webbrowser.open(uri)

    def _request_visible_pages(self) -> None:
        """Determines visible pages in viewport and dispatches render workers."""
        if not self.doc_mgr.is_open:
            return

        # Before the window is first shown, page geometry is not laid out yet:
        # widget y() values are meaningless, so get_visible_page_range() can
        # report almost every page as visible and trigger hundreds of renders
        # (huge memory spike and slow open on large documents). The show and
        # resize events request the correct range once layout is valid.
        if not self.viewer.isVisible():
            return

        start_page, end_page = self.viewer.get_visible_page_range()
        zoom = self.viewer.zoom
        dpr = float(self.devicePixelRatioF()) if hasattr(self, "devicePixelRatioF") else float(self.devicePixelRatio())

        for p_idx in range(start_page, end_page + 1):
            words = self.doc_mgr.get_page_words(p_idx)
            self.viewer.set_page_words(p_idx, words)
            hits = self.search_mgr.get_hits_for_page(p_idx)
            img = self.render_mgr.request_page(p_idx, zoom, highlights=hits, dpr=dpr)
            if img is not None:
                self.viewer.update_page_image(p_idx, zoom, img)

        # On-demand thumbnails around current viewport
        if self.sidebar.isVisible():
            thumb_needed = self.sidebar.request_thumbnail_range(start_page - 2, end_page + 5)
            for t_idx in thumb_needed:
                t_img = self.render_mgr.request_page(t_idx, 0.25, is_thumbnail=True, dpr=dpr)
                if t_img is not None:
                    self.sidebar.set_thumbnail_image(t_idx, t_img)

    @Slot(int, float, QImage)
    def _on_page_rendered(self, page_index: int, zoom: float, qimage: QImage) -> None:
        self.viewer.update_page_image(page_index, zoom, qimage)

    @Slot(int, QImage)
    def _on_thumbnail_rendered(self, page_index: int, qimage: QImage) -> None:
        self.sidebar.set_thumbnail_image(page_index, qimage)

    @Slot(int, str)
    def _on_render_failed(self, page_index: int, error: str) -> None:
        self.status_label.setText(f"Failed to render page {page_index + 1}: {error}")

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self.render_timer.start()

    def changeEvent(self, event: Any) -> None:
        super().changeEvent(event)
        if hasattr(event, "type") and event.type() in (
            QEvent.Type.ScreenChangeInternal,
            QEvent.Type.PaletteChange,
        ):
            self.render_timer.start()

    def closeEvent(self, event: Any) -> None:
        if self.doc_mgr.is_open and self.doc_mgr.is_modified:
            ret = QMessageBox.question(
                self,
                "Unsaved Changes",
                "This document has unsaved edits or annotations.\nWould you like to save a separate copy before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if ret == QMessageBox.StandardButton.Save:
                saved = self.action_save_as()
                if not saved:
                    event.ignore()
                    return
            elif ret == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        self.search_mgr.cancel_search()
        self.render_mgr.thread_pool.clear()
        self.render_mgr.thread_pool.waitForDone(300)
        self.search_mgr.thread_pool.waitForDone(300)
        super().closeEvent(event)
