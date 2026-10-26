# Changelog

All notable changes to PaperView will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-26

### Added
- **Core Document Viewing & Navigation**
  - Smooth multi-page continuous and single-page viewing modes.
  - Zoom controls: Zoom In (`Ctrl++`), Zoom Out (`Ctrl+-`), Fit Width (`Ctrl+W`), Fit Page (`Ctrl+0`), and preset percentage dropdown (50% to 300%).
  - Left sidebar with dual tabs: interactive page thumbnail cards and hierarchical Outline / Table of Contents tree.
  - Non-blocking asynchronous background document search (`Ctrl+F`) with match count indicator and traversal highlighting.
  - Comprehensive Document Properties dialog (`Ctrl+D`) displaying title, author, producer, dimensions, and permissions.
  - Native password authentication prompt for encrypted PDF documents.
- **Text Selection & Annotations**
  - High-precision mouse drag selection across lines, words, and text columns.
  - System clipboard copy integration (`Ctrl+C`).
  - Standard PDF annotations: Highlight (`Ctrl+H`), Underline (`Ctrl+U`), Strikeout (`Ctrl+K`), and customizable Sticky Notes (`Ctrl+N`).
  - Freehand ink stylus / pen drawing annotations.
  - Persistent Recent Files menu stored via `QSettings`.
- **Page Organization & Document Operations**
  - Visual Organize Pages dialog (`Ctrl+Shift+O`) with thumbnail grid for reordering, rotating, duplicating, deleting, and extracting pages.
  - Multi-document Merge dialog (`Ctrl+Shift+M`) with drag-and-drop reordering, password-protected PDF support, and bookmark offset integration.
  - PDF Split tool (`Ctrl+Shift+P`) supporting arbitrary page ranges, individual extraction, or chunked outputs.
  - Custom vector/text watermarking engine with live thumbnail preview, opacity controls, and orientation presets.
  - PDF Optimization tool (`Ctrl+Shift+Z`) with stream deflation, xref garbage collection, and image downsampling.
- **Forms, Redaction & Signatures**
  - Interactive AcroForm field editing directly within viewport or via dedicated inspector dialog (`Ctrl+Shift+F`).
  - Irreversible Permanent Redaction tool (`R` / `Ctrl+Shift+X`) physically stripping underlying content streams, character encodings, and raster data.
  - Visible Signature tool (`Ctrl+Shift+S`) supporting cursive typography or drawn freehand ink stamps (with clear non-cryptographic disclaimers).
- **Advanced Document Manipulation**
  - Rubber stamp annotations (Approved, Draft, Confidential, etc.) with custom positioning.
  - Multi-level Undo/Redo history stack (`Ctrl+Z` / `Ctrl+Y`) for document operations and annotations.
  - Interactive crop tool (`C`) with visual margin drag handles.
  - Page labeling dialog with Roman numeral, decimal, and alphabetic numbering styles.
  - Header and footer insertion tool with dynamic page numbering macros.
  - Embedded file attachment manager (`Ctrl+Shift+A`) to inspect, extract, add, or delete document attachments.
  - High-resolution raster and vector page export (`Ctrl+E`) supporting PNG, JPEG, TIFF, and SVG.
  - Embedded image extraction tool to dump all raster images from document streams.
  - Interactive Outline / Bookmark hierarchy editor.
  - Live document metadata editor with instant persistence.
  - AES-256 password protection dialog for encrypting documents with separate user and owner passwords.
- **Desktop Integration & Packaging**
  - Linux standalone one-directory packaging via PyInstaller (`scripts/build_linux.sh`).
  - Non-root user installer (`scripts/install_user.sh`) and clean uninstaller (`scripts/uninstall_user.sh`) respecting `XDG_DATA_HOME` and custom prefixes.
  - Freedesktop compliant `paperview.desktop` entry and multi-resolution hicolor SVG/PNG application icons.
  - Automated test suite covering 160 unit, integration, and UI acceptance tests.

### Security & Compliance
- Full GNU AGPLv3 licensing documentation and canonical root `LICENSE` file in compliance with Artifex MuPDF / PyMuPDF copyleft obligations.
- Active source-file overwrite protection preventing accidental corruption of input documents.
- Atomic file writes using temporary staging files.
