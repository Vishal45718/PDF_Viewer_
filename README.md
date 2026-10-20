# PaperView — Desktop PDF Reader

A modern, responsive desktop PDF reader built with Python, PySide6 (Qt), and PyMuPDF (`pymupdf`).

---

## Features

### Milestone 1: Core Viewing & Navigation
1. **Document Viewing**:
   - Smooth vertical scrolling of multi-page PDF documents.
   - Zoom controls: Zoom In (`Ctrl++`), Zoom Out (`Ctrl+-`), Fit Width (`Ctrl+W`), Fit Page (`Ctrl+0`), and preset percentage dropdown (50% to 300%).
   - Drop shadows, crisp page boundaries, and interactive link rendering.
2. **Navigation**:
   - Previous (`Left` / `PageUp`) and Next (`Right` / `PageDown`) page navigation.
   - Direct page-number jump via header toolbar text box.
   - Dual-tab left sidebar: Page thumbnails and hierarchical Outline (Table of Contents / Bookmarks).
   - Safe in-document link jumping (internal goto pages and prompted external web URLs).
3. **Full-Document Search**:
   - Asynchronous background search (`Ctrl+F`) that does not block the UI.
   - Case-sensitivity toggle and real-time match counter (`Match X of Y`).
   - Prev/Next match navigation jumping directly to target page with visible yellow highlight rectangles.
4. **Metadata & Properties**:
   - Comprehensive document properties inspector displaying Title, Author, Subject, Creator, Producer, Dates, Dimensions, Encryption status, and Permissions bitmask.
5. **Security & Password Protection**:
   - Automatic detection of encrypted documents with native password prompt and error feedback.
6. **Performance & Architecture**:
   - Threaded background rendering via `QThreadPool`.
   - Bounded LRU cache (`RenderCache`) for rendered page pixmaps.
   - Lazy on-demand rendering of visible viewport pages and nearby thumbnails.
   - Dark modern appearance inspired by professional document applications.

### Milestone 2: Text Selection, Annotations & Layout
1. **Text Selection & Clipboard**:
   - High-precision mouse drag selection across lines, words, and columns.
   - Copy selected text to system clipboard (`Ctrl+C`).
2. **Standard PDF Annotations**:
   - Native highlight (`Ctrl+H`), underline (`Ctrl+U`), and strikeout (`Ctrl+K`) applied to text selections.
   - Sticky Notes (`Ctrl+N`): Click anywhere on a page to insert sticky notes with custom comment text.
   - Delete annotations with confirmation dialog.
3. **Viewing Layout Modes**:
   - Toggle between Continuous scroll and Single-page viewing modes.
4. **Persistent History**:
   - Persistent Recent Files menu stored in user settings.

### Milestone 3: PDF Organization & Document Operations
1. **Organize Pages Dialog (`Ctrl+Shift+O`)**:
   - Dedicated interactive visual grid displaying rendered page thumbnails.
   - Rotate selected pages clockwise (`Ctrl+R`) and counter-clockwise (`Ctrl+Shift+R`).
   - Reorder pages using visual move controls or smooth drag-and-drop.
   - Duplicate selected pages with annotation and structure preservation.
   - Delete selected pages with confirmation (with guards against deleting all pages).
   - Extract selected pages directly into a standalone PDF.
   - Full live synchronization with main viewer, sidebar thumbnails, TOC bookmarks, and page indicators.
2. **Merge PDFs**:
   - Multi-file selection with reorderable list.
   - Password authentication support for protected documents.
   - Automatic TOC bookmark offset integration and collision-safe atomic writing.
   - Optional immediate opening of merged output in PaperView.
3. **Split PDFs**:
   - Flexible syntax: page ranges (e.g., `1-3, 5, 7-10`), single page extraction, or fixed chunk size.
   - Real-time output filename explanation and validation prior to execution.
4. **Watermarking**:
   - Embed vector/text watermarks into PDF pages.
   - Configurable text, font size, color, opacity, and positioning presets (Diagonal Center, Horizontal Center, Top Header, Bottom Footer).
   - Behind content or foreground overlay options.
   - Interactive live thumbnail preview updating in real-time.
5. **PDF Optimization**:
   - Structural cleanup and unused xref garbage collection (Level 4).
   - Stream deflation and compression.
   - Explicit raster image downsampling (DPI target) and JPEG recompression (quality balance).
   - Transparent byte savings comparison and reporting.
6. **Document Integrity & Unsaved State**:
   - Safe atomic writing (`_atomic_save`) using temporary staging files preventing file corruption.
   - Active source-file overwrite protection.
   - Bookmark / TOC remapping on reordering, deletion, and duplication.
   - Annotation preservation across document manipulations.
   - Unsaved modification warnings on exit and reload.

### Milestone 4: Forms, Redaction & Signatures
1. **Interactive PDF Forms (AcroForms)**:
   - Automatic detection of interactive AcroForm fields upon document loading.
   - Interactive in-viewer Form Mode (`Ctrl+Shift+M`): Click directly on text fields (popup input), checkboxes (instant toggle), or dropdowns to fill values directly on the page without disrupting text selection.
   - Dedicated "Fill & Inspect Form Fields" dialog (`Ctrl+Shift+F`) for systematic form overview and bulk editing.
   - Preserves form fields, widget definitions, and values during page operations (rotation, reordering, duplication).
   - Form field changes write to in-memory state and persist reliably on `File → Save Copy As`.
2. **Permanent Redaction Engine**:
   - In-viewer Redact Tool (`R`): Click and drag to create pending redaction regions with live preview.
   - Distinctive visual styling: Pending redactions display with semi-transparent red fills, dashed red borders, and a `"REDACTION"` badge to prevent confusion with permanently applied redactions.
   - Redaction Manager dialog (`Ctrl+Shift+X`): Review all pending redaction regions across pages, cancel individual regions, or remove all pending redactions.
   - Permanent Destructive Application: Double-confirmation prompt before irreversible content stripping via PyMuPDF's native `apply_redactions()`. Underlying character streams, vector shapes, and raster content are physically purged from the PDF stream — text cannot be extracted or recovered via `get_text()`, clipboard, or search.
   - Multi-region and multi-page batch application support.
   - Active source-file immutability: Original document on disk is never altered.
3. **Visible Signatures**:
   - Dedicated Visible Signature dialog (`Ctrl+Shift+S`).
   - Two signature modes:
     - **Typed Signature**: Custom cursive typography with configurable signer name, subtitle, and font sizing.
     - **Drawn Signature**: Interactive canvas allowing freehand stylus or mouse drawing, converted and embedded as vector ink annotation strokes.
   - Positioning presets (Bottom Right, Bottom Left, Bottom Center, Top Right, Custom coordinates) with automatic page-dimension calculation.
   - Persists in the PDF as recognized annotation elements.
   - **Crucial Distinction**: This feature places a *visible signature* on the page. It does *not* provide cryptographic digital signatures, PKI certificate validation, or tamper-evident document authenticity.
4. **Predefined Rubber Stamps**:
   - Add Stamp dialog (`Ctrl+Shift+T`) supporting standard document stamps: *Approved*, *Rejected*, *Draft*, *Confidential*, *Reviewed*, *Final*, *Void*, and *Top Secret*.
   - Positioning presets (Top Right, Center, Bottom Right, Top Left, Custom coordinates).
   - Embeds standard PDF stamp annotations that persist across file saving.

### Milestone 5: Advanced PDF Editing & Professional Workflow
1. **Undo / Redo Command Stack (`Ctrl+Z` / `Ctrl+Y`)**:
   - Snapshot-based command history on `DocumentManager` (up to 20 states).
   - Supports undo and redo for annotations, page rotations, crops, headers/footers, and page manipulations.
   - Reactive toolbar buttons and Edit menu actions enabled/disabled based on stack state.
2. **Page Crop / CropBox Editing (`Ctrl+Shift+C`)**:
   - Crop dialog with exact dimension inputs (`x0`, `y0`, `x1`, `y1`) and standard presets (A4, Letter).
   - Apply to current page, selected page indices, or all pages.
   - Native PDF CropBox manipulation with automatic orientation-aware coordinate transformation on rotated pages.
   - Reset Crop functionality reverting CropBox to MediaBox.
3. **Custom Page Labels & Numbering Schemes**:
   - Full support for PDF page labeling dictionaries (decimal, roman, alphabetical, and custom prefix schemes like `A-1, A-2`).
   - Per-page label querying (`page.get_label()`) and persistence across save/reopen cycles.
   - Integrated with status bar and page indicators.
4. **Headers & Footers**:
   - Header & Footer dialog with 6 independent text slots (header/footer left, center, right).
   - Dynamic template variables: `{page}` (page label/number), `{total}` (total page count), `{date}` (current ISO date), `{filename}` (document name).
   - Safe margin and page boundary calculation with font-size bounding.
5. **Native Printing Support (`Ctrl+P`)**:
   - Qt Print Support integration (`QPrinter`, `QPrintDialog`).
   - Page range selection (all pages, custom page interval) with high-resolution scaled rendering.
   - *Documented limitation*: Pages are rendered as high-DPI raster images due to Qt print subsystem constraints.
6. **Multi-Format Page Export**:
   - Export Dialog allowing export of current page, page ranges, or all pages as PNG or JPEG image sequences.
   - Configurable resolution (72 to 600 DPI) and JPEG quality compression.
7. **Embedded Image Extraction**:
   - Image Extraction dialog inspecting all embedded raster images in the document.
   - Details display: containing page, dimensions (W×H), format, colorspace, and xref.
   - Interactive live image thumbnail preview.
   - One-click extraction of selected image or batch-extraction of all images to directory.
8. **PDF Attachments (Embedded Files)**:
   - Attachment manager dialog listing embedded files with file names, sizes, and descriptions.
   - Extract attachments to disk and embed new files into the document.
9. **Editable Bookmarks (Table of Contents)**:
   - Bookmark Editor dialog (`Ctrl+Shift+B`) displaying hierarchical outline tree.
   - Add new bookmarks pointing to arbitrary target pages, rename existing bookmarks, and delete bookmarks with live viewer/sidebar synchronization.
10. **Advanced Metadata Editing**:
    - Extended Document Properties dialog (`PropertiesDialog`) with editable fields for Title, Author, Subject, Keywords, Creator, and Producer.
    - Persists changes cleanly to the document.
11. **PDF Security & AES-256 Password Protection**:
    - Security Dialog to create password-protected PDF copies encrypted with AES-256 (`PDF_ENCRYPT_AES_256`).
    - Independent user (open) and owner (permissions) passwords.
    - Granular permission bitmask control (Printing, Content Copying, Document Modification).
12. **Professional Status Bar**:
    - Real-time formatted status line: `Page X of Y [label] | Z% | PDF V.V | N.N MB | Modified`.
    - Automatically displays page labels only when different from physical page indices.

### Milestone 6: High-DPI Sharpness, Cache Isolation, Race Protection & Responsive Polish
1. **HiDPI / Device-Pixel-Ratio (DPR) Aware Rendering**:
   - Device-pixel-aware rendering engine dynamically scaling PyMuPDF's rasterization matrix by `zoom * dpr` (supporting DPR 1.0, 1.5, 2.0, and fractional scaling).
   - Generates pixel-perfect, razor-sharp text and line art across all displays (Standard 1080p, 1440p, 4K, and Retina) without blurry bilinear interpolation.
2. **Native Physical-Pixel Rendering**:
   - Direct physical-to-logical pixel mapping via `QImage.setDevicePixelRatio(dpr)`.
   - `PageWidget` coordinates and paint events map directly to physical screen pixels with zero resampling distortion or fuzzy edge artifacts.
3. **Consistent Zoom Behavior**:
   - Normalizes zoom values (`round(zoom, 3)`) across all viewports (e.g., 25%, 50%, 75%, 100%, 150%, 200%, 300%).
   - All interactive elements (text selections, hyperlinks, form fields, redaction rectangles, rubber stamps, visible signatures) dynamically recompute logical-to-screen geometry with sub-pixel precision across all zoom levels.
4. **Render-Cache Multi-Dimensional Isolation**:
   - Multi-dimensional cache key in `RenderCache`: `(page_index, zoom, dpr, is_thumbnail, highlights_hash)`.
   - Strictly isolates DPR 1.0 from DPR 2.0, full-page document renders from thumbnail renders, and distinct search highlight states.
   - Bounded LRU eviction policy (default 32 entries) automatically discards the least-recently-accessed pages while keeping the active working set in memory.
5. **Stale-Render Race Protection**:
   - `PageWidget.set_image` validates incoming asynchronous renders against the active zoom level (`abs(self.zoom - zoom) <= 0.005`).
   - If user zooms rapidly (e.g. 100% -> 150% -> 200%) and renders finish out-of-order (100%, 200%, 150%), obsolete renders are safely rejected and the final visible image always matches the 200% state.
6. **Responsive Toolbar Refactoring**:
   - Refactored second toolbar organized into 4 distinct groups:
     - **PRIMARY MARKUP**: Select (`V`), Highlight (`H`), Underline (`U`), Note (`N`), Pen (`P`) with icon-only buttons and rich tooltips.
     - **REDACTION Group**: Redact (`Ctrl+Shift+X`), Apply Redactions... (`Ctrl+Shift+A`).
     - **SIGN & STAMP Menu**: `Sign & Stamp ▾` dropdown containing Add Stamp... (`Ctrl+Shift+T`) and Sign / Fill & Sign... (`Ctrl+Shift+G`).
     - **FORMS Menu**: `Interactive Form Mode` button (`Ctrl+Shift+M`) with split-menu for Fill Form Dialog... (`Ctrl+Shift+F`).
   - Usable at ~800px window width without horizontal clipping, unusable wrapping, or disappearing critical controls into overflow menus.
   - Strictly shared `QAction` instances between toolbar buttons, menu items, and keyboard shortcuts.
7. **Strict Atomic PDF Save Validation**:
   - Robust 7-step atomic write process in `_atomic_save()`:
     1. Write to temporary output (`.tmp_<stem>_<uuid>.pdf`).
     2. Close/flush temporary PDF write stream.
     3. Open temporary PDF with PyMuPDF.
     4. Verify it opens successfully as a valid PDF.
     5. Verify page count is readable and matches original document.
     6. Close verification handle.
     7. Atomically replace destination file.
   - If any validation or filesystem error occurs: destination remains untouched, temporary file is safely deleted, and original in-memory document remains fully usable.
8. **QA & Testing Procedure**:
   - 132 automated tests verifying rendering dimensions, DPR scaling, cache isolation, race conditions, coordinate mapping, atomic save integrity, and toolbar synchronization.

---

### Milestone 7: Packaging, Desktop Integration & Distribution Readiness
1. **Standalone Reproducible Linux Build**:
   - Automated one-directory packaging script: `scripts/build_linux.sh`.
   - Generates an isolated standalone application bundle under `dist/paperview/` containing the compiled binary, bundled Python 3 runtime, PySide6 Qt6 libraries, platform plugins (`wayland`, `xcb`, `eglfs`), PyMuPDF/MuPDF, and asset resources.
   - Completely separates build artifacts (`build/`, `dist/`) from editable source code.
2. **Application Identity & Version Information**:
   - Standardized application naming (`PaperView`) and semantic versioning (`1.0.0`).
   - Interactive **About Dialog** (`Help → About PaperView`): Displays application name, version, Python runtime, PySide6/Qt version, PyMuPDF engine version, and clear GNU AGPLv3 licensing notice.
   - Command-line flags `--version` (`-v`) and `--help` (`-h`) that exit instantly with zero GUI overhead.
3. **Application Icon & Desktop Integration**:
   - Official PaperView vector SVG icon (`packaging/icons/paperview.svg`) and multi-resolution rasterized assets (32x32, 48x48, 64x64, 128x128, 256x256 PNGs).
   - Crisp high-DPI application window icon configured via `QApplication.setWindowIcon()` and `MainWindow.setWindowIcon()`.
   - Freedesktop.org compliant XDG Desktop Entry (`packaging/paperview.desktop`) associating PaperView with PDF MIME types (`application/pdf`, `application/x-pdf`, etc.) and defining `StartupWMClass=PaperView`.
4. **User-Space Installation & Removal**:
   - User installation script (`scripts/install_user.sh`): Installs cleanly into `$HOME/.local` (`bin`, `lib`, `share/applications`, `share/icons/hicolor`) without requiring root or `sudo` privileges.
   - User removal script (`scripts/uninstall_user.sh`): Safely removes all installed binaries, desktop files, and icons from `$HOME/.local`.
5. **Runtime Robustness & Path Independence**:
   - Startup is completely independent of the caller's current working directory.
   - Robust command-line argument and file-path parsing handling relative paths, absolute paths, file paths containing spaces and symbols, and `file://` URI schemes passed by desktop file managers.
   - Elimination of all developer-specific hardcoded home directory paths in application runtime code.
   - Helpful pre-flight environment checks detecting missing Qt platform plugins (`libqwayland.so`, `libqxcb.so`) with actionable diagnostics.
6. **Integrity & Source Protection**:
   - Missing and corrupt input files are caught and reported clearly to the user with modal dialogs without application termination or crash.
   - Password-protected documents prompt for user passwords and handle incorrect entries gracefully.
   - `Save Copy As` protects the original file: explicitly blocks attempts to overwrite the active source document directly and preserves original source byte integrity.
7. **Comprehensive Automated Test Coverage**:
   - Full automated test suite expanded to **148 passed tests** (100% pass rate).

---

## Directory Structure

```
pdf_viewer/
├── packaging/
│   ├── paperview.desktop        # Validated XDG Desktop Entry specification
│   └── icons/                   # Vector SVG and multi-resolution PNG icons (32px to 256px)
├── scripts/
│   ├── build_linux.sh           # Reproducible PyInstaller one-directory packaging script
│   ├── install_user.sh          # User-space ~/.local installer (no root required)
│   └── uninstall_user.sh        # Safe user-space removal script
├── paperview/
│   ├── __init__.py              # Package metadata (__app_name__, __version__, __license__)
│   ├── app.py                   # Application entry point, CLI flags, Qt diagnostics
│   ├── main_window.py           # QMainWindow orchestrator, menus, toolbar, shortcuts, Help menu
│   ├── document.py              # PyMuPDF document manager: organize, merge, split, watermark, optimize, forms, redactions, signatures, stamps, undo/redo, crop, labels, headers/footers, export, images, attachments, bookmarks, metadata, security, atomic save validation
│   ├── organize_dialog.py       # Organize Pages workspace (visual grid, reorder, rotate, extract)
│   ├── operations_dialogs.py    # Merge, Split, Watermark (with preview), and Optimize dialogs
│   ├── milestone4_dialogs.py    # FormViewerDialog, RedactionDialog, SignatureDialog, StampDialog
│   ├── milestone5_dialogs.py    # CropDialog, HeaderFooterDialog, ExportDialog, AttachmentDialog, SecurityDialog, BookmarkEditorDialog, ImageExtractionDialog
│   ├── renderer.py              # Background render worker, high-DPI scaling, QImage conversion, LRU cache
│   ├── viewer.py                # Scrollable document viewer, PageWidget with text selection, forms, and redaction overlays
│   ├── sidebar.py               # Dual-tab sidebar (DPI-aware Thumbnails + Outline/TOC tree)
│   ├── search.py                # Background search worker & match coordinator
│   ├── search_bar.py            # Docked search input widget with match counters
│   ├── icons.py                 # Vector SVG icon generator and provider (app icon & UI icons)
│   ├── theme.py                 # Modern dark stylesheet and color tokens
│   └── dialogs.py               # Document Properties, Password prompt, and About PaperView dialogs
├── tests/
│   ├── test_core.py             # Core unit tests (open, metadata, large PDF, save, search)
│   ├── test_ui.py               # UI integration tests (widgets, viewer, main window)
│   ├── test_milestone2.py       # Text selection, annotation, layout, recent files tests
│   ├── test_milestone3.py       # Organization, merge, split, watermark, optimize, integrity tests
│   ├── test_milestone4.py       # Forms, redaction, visible signatures, rubber stamps, dialogs tests
│   ├── test_milestone5.py       # Undo/redo, crop, labels, headers/footers, export, image extraction, attachments, bookmarks, metadata, security, dialogs tests
│   ├── test_milestone6.py       # High-DPI rendering, DPR scaling, cache isolation, stale render rejection, coordinate mapping, atomic save validation
│   └── test_milestone7.py       # Packaging validation, desktop entry, icon assets, CLI paths, source protection, About dialog tests
├── dist/                        # Standalone build output directory (ignored by git)
│   └── paperview/               # Standalone one-dir application bundle
├── run.sh                       # One-click development execution script
├── requirements.txt             # Pinned python dependencies (core, testing, packaging)
├── pytest.ini                   # Test runner configuration
├── LICENSE_NOTES.md             # Licensing documentation and AGPLv3 obligations
└── README.md                    # User guide & documentation
```

---

## Standalone Linux Packaging Guide

### 1. Prerequisites
- **Operating System**: Linux x86_64 (tested on Arch Linux / Hyprland).
- **Python**: Python 3.10+ (tested on Python 3.14.8).
- **Dependencies**: `PySide6>=6.6.0`, `pymupdf>=1.24.0`, `pyinstaller>=6.10.0`.
- **System Libraries**: glibc (>= 2.35), Wayland (`libwayland-client`) or X11 (`libxcb`, `libx11`), `libxkbcommon`.

### 2. Building the Standalone Package
Run the reproducible packaging script:
```bash
./scripts/build_linux.sh
```
This script will:
1. Verify Python virtual environment and dependencies (auto-installing PyInstaller if needed).
2. Generate all required SVG and PNG icon assets into `packaging/icons/`.
3. Clean prior build artifacts from `build/` and `dist/`.
4. Run PyInstaller in `--onedir` mode bundling all required Qt platform plugins and PyMuPDF bindings.
5. Verify the generated executable and test `--version` reporting.

**Output Artifacts**:
- Bundle Directory: `dist/paperview/`
- Executable: `dist/paperview/paperview`

### 3. Launching the Packaged Application
The packaged application can be executed from any working directory:
```bash
# Launch with an optional PDF document
./dist/paperview/paperview [path/to/document.pdf]

# Check version
./dist/paperview/paperview --version

# Display CLI help
./dist/paperview/paperview --help
```

### 4. Installing for the Current User
To integrate PaperView with your desktop environment without root privileges:
```bash
./scripts/install_user.sh
```
This installs the application to `~/.local/lib/paperview`, creates a symlink at `~/.local/bin/paperview`, installs icons into `~/.local/share/icons/hicolor/`, and registers `~/.local/share/applications/paperview.desktop`.

To remove the installation:
```bash
./scripts/uninstall_user.sh
```

### 5. Clean-Environment Smoke-Test Procedure
To verify that the packaged binary runs independently of the development source tree:
```bash
# Create a clean temporary directory
mkdir -p /tmp/paperview_smoke_test
cd /tmp/paperview_smoke_test

# Test version and help flags
/home/jonsnow/Desktop/pdf_viewer/dist/paperview/paperview --version
/home/jonsnow/Desktop/pdf_viewer/dist/paperview/paperview --help

# Test opening a PDF located outside the repository
/home/jonsnow/Desktop/pdf_viewer/dist/paperview/paperview "/tmp/some_document with spaces.pdf"
```

### 6. Known Platform Limitations
- **Platform Architecture**: The built binary is targeted for Linux x86_64. It is not compatible with ARM64/aarch64 systems without rebuilding on an ARM host.
- **C Library Compatibility**: The standalone binary links against system `glibc` (Arch Linux glibc 2.44). Distributions with older glibc versions (e.g. Debian 10 / Ubuntu 20.04) require rebuilding on a matching older host or container.
- **Display Server**: Requires an active Wayland compositor or X11 display server. For headless automated testing, run with `QT_QPA_PLATFORM=offscreen` or `xvfb-run`.

---

## Running the Application (Development Mode)

### Option A: Using the launch script
```bash
./run.sh [optional_pdf_path]
```

### Option B: Using python directly in .venv
```bash
source .venv/bin/activate
python3 -m paperview.app [optional_pdf_path]
```

---

## Rendering Controls & Quality Architecture

- **Automatic DPI Detection**: PaperView dynamically queries Qt's `devicePixelRatioF()` for the active window and instructs PyMuPDF to rasterize at `zoom * dpr` resolution.
- **Zoom Controls**:
  - Zoom In: `Ctrl++` (or toolbar button)
  - Zoom Out: `Ctrl+-` (or toolbar button)
  - Fit Width: `Ctrl+W`
  - Fit Page: `Ctrl+0`
  - Preset Dropdown: 50%, 75%, 100%, 125%, 150%, 200%, 300%
- **High-DPI Support**: Automatically scales on 4K, 1440p, Retina, and Wayland fractional-scaling desktop environments without font blurring.
- **Bounded LRU Cache**: Fixed at 32 pages max to guarantee strict memory bounds regardless of PDF page count or zoom level.

---

## Release & QA Verification Checklist

Before release, verify:
1. **Automated Test Suite**:
   ```bash
   .venv/bin/python -m pytest -v
   ```
   All 148 tests must pass with 100% success rate.
2. **Bytecode Compilation**:
   ```bash
   .venv/bin/python -m compileall paperview
   ```
   Must compile with 0 errors.
3. **Reproducible Build**:
   ```bash
   ./scripts/build_linux.sh
   ```
   Must generate a valid `dist/paperview/paperview` executable.
4. **Desktop Entry Validation**:
   ```bash
   desktop-file-validate packaging/paperview.desktop
   ```
   Must pass with 0 errors.
5. **Sharp Text at 100% Zoom**:
   Launch `./run.sh ~/Desktop/Resume_CV.pdf` and confirm text glyphs are sharp, crisp, and high-contrast at 100% zoom.
6. **Smooth Zooming**:
   Zoom in to 150% and 200% and zoom out to 75% and 50%; verify rendering refreshes crisply without blurring.
7. **Window Resizing**:
   Resize the main window narrower (down to 800px width) and wider; verify the toolbar wraps cleanly and pages remain centered without overflow.
8. **Interactive Overlays**:
   Verify text selection, search highlights, form fields, and sticky notes remain pixel-aligned with text across zoom levels.
9. **Destructive Actions**:
   Confirm "Apply Redactions..." displays appropriate warning dialogs and permanently strips underlying PDF content.

---

## Running Tests

Execute the automated test suite with pytest:
```bash
source .venv/bin/activate
pytest -v
```
All **148 tests** across all 7 milestones (core viewing, text selection & annotations, document reorganization, merge, split, watermark, optimization, AcroForms, permanent redaction, visible signatures, rubber stamps, undo/redo, crop, page labels, headers/footers, export, image extraction, attachments, bookmarks, metadata editing, security, high-DPI rendering, DPR scaling, cache isolation, atomic save validation, standalone packaging, desktop integration, and error resilience) pass cleanly with 100% success rate.

---

## Licensing Gate Notice

See [LICENSE_NOTES.md](file:///home/jonsnow/Desktop/pdf_viewer/LICENSE_NOTES.md) for full licensing details regarding PyMuPDF's AGPLv3 obligations. PaperView must not be distributed as closed-source proprietary software without obtaining a commercial license from Artifex Software, Inc.
