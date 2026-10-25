# PaperView — M8 Final Manual Acceptance Report

## 1. Executive Verdict

PASS

PaperView 1.0.0 satisfies all Milestone 8 release candidate acceptance criteria. The full automated test suite passes with 100% success rate (160 of 160 tests passed). Real desktop GUI acceptance under Hyprland (Wayland) conclusively verified application launch, sharp page rendering, multi-page thumbnail loading, zoom levels (100% through 300%), search highlighting, rapid interaction, and clean process termination. Large PDF testing on the 434-page e-book (47.6 MB) verified instant initial rendering, responsive page navigation, and stable memory/process execution without stale renders or crashes. Source document protection, byte-level redaction scrubbing, encryption authentication, and uninstaller isolation safeguards are verified and intact.

## 2. Environment

- OS: Arch Linux (Linux 7.2.11-arch1-1-x86_64)
- Desktop: Hyprland (Wayland session eDP-1, scale 1.25)
- Wayland/X11: Wayland (`WAYLAND_DISPLAY=wayland-1`, `DISPLAY=:1`)
- Python: 3.14.8 (`.venv/bin/python`)
- PySide6: 6.12.0
- PyMuPDF: 1.28.2
- PaperView version: 1.0.0
- Packaged binary: `/home/jonsnow/Desktop/pdf_viewer/dist/paperview/paperview` (281 MB standalone one-directory bundle)

## 3. Automated Verification

| Check | Result | Evidence |
|---|---|---|
| compileall | PASS | `.venv/bin/python -m compileall paperview tests` returned 0 with no syntax/compilation errors |
| pytest | PASS | 160 passed in 9.81s (`.venv/bin/python -m pytest -q`), 100% pass rate across all 8 milestones |
| packaged --version | PASS | Executed from `/tmp` outside repo: returned `PaperView 1.0.0`, exit code 0 |
| packaged --help | PASS | Executed from `/tmp` outside repo: printed full usage syntax and options, exit code 0 |
| invalid CLI option | PASS | `paperview --unknown-option` printed `unrecognized option` diagnostic to stderr, exit code 2 |

## 4. GUI Acceptance

All GUI checks were executed on the real Wayland display session with `dist/paperview/paperview` and programmatic Qt widget inspection.

| Feature | Result | Evidence |
|---|---|---|
| Startup | PASS | Launched `dist/paperview/paperview ~/Desktop/Resume_CV.pdf`; Wayland window mapped (`class=org.paperview.paperview`, size `[762, 954]`); window title `Resume_CV.pdf — PaperView`; visual screenshot confirmed window and toolbars active |
| Rendering | PASS | PyMuPDF pipeline rasterized Page 1 at 596x842; visual screenshot confirmed sharp text, no raster blur or clipping, text clearly legible |
| Navigation | PASS | Next page navigated to Page 2 (`viewer.current_page == 1`); Previous page returned to Page 1 (`viewer.current_page == 0`); page jump and page indicator label synchronized |
| Thumbnails | PASS | Sidebar "Pages" tab rendered crisp thumbnail cards for Page 1 and Page 2 with active blue selection frame |
| Zoom 100% | PASS | Verified `zoom == 1.00`, correct layout container width and crisp 1:1 render |
| Zoom 150% | PASS | Verified `zoom == 1.50`, smooth scaling, re-anchor keeps active page visible |
| Zoom 200% | PASS | Verified `zoom == 2.00`, high-resolution bitmap rendered with no clipping |
| Zoom 300% | PASS | Verified `zoom == 3.00`, ultra-sharp vector rasterization, DPR scaling intact |
| Search | PASS | Search bar toggled visible; input field populated; match highlighting and hit traversal operational |
| Text selection | PASS | Page text extracted (3,487 characters); verified selectable character rects and content matching |
| Copy | PASS | Text copied from document buffer verified against clipboard/text extraction |
| Highlight | PASS | Added yellow highlight across target text rects; `doc.annots()` registered subtype `/Highlight` |
| Underline | PASS | Added blue underline across target text rects; `doc.annots()` registered subtype `/Underline` |
| Note | PASS | Added sticky note comment annotation at `(300, 100)`; persisted icon and text |
| Pen | PASS | Added multi-segment freehand ink stroke annotation; persisted stroke coordinates |
| Resize | PASS | Cycled window geometry (762x954 → 1200x800 → 600x400 → 762x954); page container dynamically reflowed and remained centered |
| Rapid navigation | PASS | Rapid stress cycle (`zoom -> scroll -> page change -> zoom -> page change -> scroll`) completed with zero crashes and no stale render frames |
| Shutdown | PASS | Closed window; process received SIGTERM and terminated cleanly with no lingering threads |

## 5. Large PDF

Tested with `/home/jonsnow/Desktop/MAHABHARATAM-final-E-BOOK.pdf` (434 pages, 47.6 MB).

| Check | Result | Evidence |
|---|---|---|
| Open | PASS | Packaged binary opened instantly; status bar reported `Opened MAHABHARATAM-final-E-BOOK.pdf | Page 1 of 434 | 100% | PDF 1.4 | 47.6 MB` |
| Render | PASS | High-detail full-color title page illustration rendered sharply without blur or artifacts; sidebar thumbnails for pages 1-4 loaded cleanly |
| Navigation | PASS | Directly navigated across distant pages (Page 10, Page 50, Page 433); target pages rendered immediately |
| Zoom | PASS | Zoomed between 100% and 150%; container width updated with anchored viewport |
| Search | PASS | Search manager correctly traversed document text words and hit locations |
| Rapid scrolling | PASS | Scrolled continuously across 20+ pages; memory usage remained bounded; layout guard prevented multi-page render floods |

## 6. Editing

Tested using a dedicated temporary copy (`/tmp/edit_test.pdf`), preserving original source files.

| Feature | Result |
|---|---|
| Highlight | PASS |
| Underline | PASS |
| Note | PASS |
| Pen | PASS |
| Rotate | PASS |
| Reorder | PASS |
| Duplicate | PASS |
| Delete | PASS |
| Extract | PASS |
| Save/reopen | PASS |

All 4 authoring annotations (Highlight, Underline, Note, Pen) persisted in the PDF structure upon saving and were verified present and valid after reopening the saved document copy.

## 7. Redaction

Verified through both automated integration tests (`tests/test_milestone8.py::test_m8_permanent_redaction_integrity`) and programmatic audit:
1. Created temporary PDF containing unique secret: `PAPERVIEW_REDACTION_SECRET_7241`.
2. Verified secret text exists and search locates it in source.
3. Created redaction region over the secret bounding box and executed `apply_redactions()`.
4. Saved output copy to `Permanently_Redacted_Output.pdf`.
5. Reopened the saved copy with PyMuPDF:
   - `get_text()` returned zero occurrences of `PAPERVIEW_REDACTION_SECRET_7241`.
   - `search_for("PAPERVIEW_REDACTION_SECRET_7241")` returned 0 matches.
   - Non-redacted text on the same page remained intact.
6. Computed SHA256 of the source document before and after redaction: identical (`assert source_pdf.read_bytes() == source_bytes`).

Content removal is physical and irreversible in the exported copy.

## 8. Source Integrity

Original Desktop PDF hashes verified bit-for-bit identical before and after all audit operations:

```text
3558717842f301d16331c4fe277c213b00bf726e57cfeab7f95f39bc51604d56  /home/jonsnow/Desktop/Resume_CV.pdf
7054b9e9f9330acf5c9df71fcccc7ccaf8db442c21fa744d66c3d08bd95ae5c9  /home/jonsnow/Desktop/MAHABHARATAM-final-E-BOOK.pdf
7bbd8b11f5d55f0eadeaa62eb44df1827d4fe300b98c082cee3edfc30ad2d336  /home/jonsnow/Desktop/check_CV.pdf
```

Save Copy As protection verification:
- Attempting to overwrite the currently active file via "Save Copy As" is actively trapped and rejected with a user-facing warning dialog (`cannot overwrite the active file`).
- Saving to a distinct destination writes a valid multi-page PDF while leaving the active source file's SHA256 unchanged.

## 9. Password PDFs

Verified in `test_m8_password_protection_reopen_and_reject` and acceptance script:
- Opening an AES-256 encrypted PDF without a password or with an invalid password (`wrong_password`) triggers `PasswordRequiredError` / `InvalidPasswordError` and logs an error without crashing.
- Providing the correct password (`audit_pass_2026`) successfully authenticates, marks `meta.is_encrypted == True`, and decrypts and renders all protected page content.

## 10. Visible Signature / Stamp

- **Placement & Persistence:** Added visible signature bounding box with signer name and date. Persisted as a standard PDF annotation under subject `VisibleSignature`. Verified preserved upon save and reopen.
- **Cryptographic Disclaimer:** Both the `SignatureDialog` UI and underlying documentation explicitly state that visible signatures are visual stamps/annotations and NOT cryptographic digital signatures. The dialog contains the prominent notice: *"This is a visual signature annotation only, NOT a Cryptographic Digital Signature. It does not provide cryptographic tamper evidence or certificate-based non-repudiation."*

## 11. Packaging

- **Standalone Bundle:** PyInstaller one-directory bundle packaged at `dist/paperview/` (281 MB).
- **Bundled Plugins:** Contains required Qt platform plugins (`libqwayland.so`, `libqxcb.so`, `libqoffscreen.so`), image formats (`libqsvg.so`), icon engines (`libqsvgicon.so`), and print support (`libcupsprintersupport.so`).
- **External CWD Execution:** Successfully invoked from `/tmp` and non-repository directories for `--version`, `--help`, and document opening.
- **Rebuild Status:** Cleanly rebuilt with `scripts/build_linux.sh` during this audit to ensure all latest layout and zoom fixes are included in the distributed binary.

## 12. Installer

Tested with isolated temporary `HOME` directory containing spaces (`/tmp/PaperView Test User With Spaces/`):
- `install_user.sh` successfully installed `~/.local/bin/paperview`, `~/.local/lib/paperview/`, `~/.local/share/applications/paperview.desktop`, and scalable SVG icons without `sudo`.
- `XDG_DATA_HOME` override tested and confirmed to place desktop files under the configured custom data directory.
- Repeated installation is safe and idempotent.
- `uninstall_user.sh` cleanly removed PaperView files while preserving unrelated user binaries and desktop files (`unrelated_tool`, `other_app.desktop`).
- Repeated uninstallation is safe and idempotent.

## 13. Defects Found and Fixed

### Defect 1: Visible Page Range Layout Race on Large Documents
- **Reproduction:** Opening a large multi-page document before the main window is shown triggered render requests for almost all pages.
- **Root Cause:** Before the widget is first shown, child page widgets had uninitialized geometry `(y = 0)`, causing `get_visible_page_range()` to detect every page as visible.
- **Fix:** Added a visibility guard in `MainWindow._request_visible_renders()` (`if not self.viewer.isVisible(): return`). Layout-driven renders are deferred until the initial `showEvent` and `resizeEvent` when geometries are valid.
- **Regression Test:** Covered by `tests/test_milestone8.py::test_m8_gui_startup_render_nav_zoom_search_and_shutdown`.

### Defect 2: Viewport Desync After Zoom Reflow
- **Reproduction:** Zooming deep inside a multi-page document shifted scroll position so the active page fell outside the visible viewport, causing stale render labels.
- **Root Cause:** `set_zoom()` altered document dimensions without re-anchoring the scroll position to `current_page`.
- **Fix:** Added single-shot timer re-anchoring in `DocumentViewer.set_zoom()` to scroll back to the active anchor page if neither zoom nor page index changed during the reflow.
- **Regression Test:** Verified by `tests/test_ui.py::test_zoom_reanchors_current_page_after_zoom`.

### Defect 3: Discard Confirmation in Interactive Dialog Tests
- **Reproduction:** Running dialog workflow tests without mocking discard confirmation caused `win.close()` to prompt interactively for unsaved changes.
- **Fix:** Monkeypatched `QMessageBox.question` to return `StandardButton.Discard` during teardown in `test_milestone3.py` and `test_milestone4.py`.
- **Regression Test:** Verified by `tests/test_milestone3.py` and `tests/test_milestone4.py`.

## 14. Remaining Limitations

- Wayland input context displays benign client warnings on surface focus (`QtWaylandClient::QWaylandTextInputv3::disableSurface`), typical of Qt6 applications on Hyprland; does not affect application functionality.
- Visible signatures are non-cryptographic visual annotations by design; certificate-based digital signatures (/Sig dictionaries) are not supported.
- Form editing supports standard AcroForm text fields and checkboxes; dynamic XFA forms are outside the PyMuPDF/PaperView specification.

## 15. Final Release Decision

READY FOR PUBLIC RELEASE

All automated test suites pass (160/160 tests, 100% pass rate). All GUI acceptance criteria (startup, rendering, navigation, zoom, search, annotations, redaction, encryption, large document support, and clean packaging) are verified on real hardware under Wayland. No release-blocking defects exist.
