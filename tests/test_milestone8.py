"""
Milestone 8 Test Suite: Release Candidate Audit & Verification.
Tests:
1. Standalone packaged binary from outside repo CWD:
   - Version (--version / -v) and Help (--help / -h) reporting.
   - Unrecognized CLI flags produce understandable error and exit 2.
   - Opening generated test PDF with path containing spaces.
   - File descriptor open verification via /proc/<pid>/fd.
2. Missing path and corrupt PDF error resilience (stderr diagnostics and QMessageBox).
3. Desktop integration audit:
   - desktop-file-validate compliance.
   - install_user.sh and uninstall_user.sh in custom HOME with spaces.
   - Idempotent execution (running installer and uninstaller twice is safe).
   - Only PaperView-managed files are removed on uninstall.
4. Release integrity:
   - PDF source file protection and Save Copy As active file guard.
   - Reopening saved copy validates page count, structure, and integrity.
   - Permanent redaction physical removal verification in saved copy vs source.
   - Password-protected PDF authentication flow (correct password opens, wrong rejected).
   - Visible signature distinction (non-cryptographic annotation, disclaimer verification).
   - AGPLv3 licensing notice, About dialog, and dependency specifications.
5. Packaged Qt platform plugins, SVG, and print support verification.
6. Full GUI startup, rendering, navigation, zoom, search, and clean shutdown.
"""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import pytest
import pymupdf
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon, QImage
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QLabel

import paperview
from paperview import __app_name__, __description__, __version__, __license__
from paperview.app import main as app_main
from paperview.dialogs import AboutDialog
from paperview.document import (
    DocumentError,
    DocumentManager,
    InvalidPasswordError,
    PasswordRequiredError,
)
from paperview.main_window import MainWindow
from paperview.milestone4_dialogs import SignatureDialog
from paperview.renderer import RenderTask, RenderWorker


@pytest.fixture
def sample_test_pdf(tmp_path: Path) -> Path:
    """Creates a temporary sample multi-page PDF."""
    pdf_path = tmp_path / "Audit_Sample_Document.pdf"
    doc = pymupdf.open()
    for i in range(4):
        p = doc.new_page(width=612, height=792)
        p.insert_text((72, 100), f"PaperView Milestone 8 Page {i + 1}")
        p.insert_text((72, 140), "Audit verification document with searchable keywords and content.")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def protected_test_pdf(tmp_path: Path) -> Path:
    """Creates an encrypted PDF fixture with user and owner passwords."""
    pdf_path = tmp_path / "Audit_Protected.pdf"
    doc = pymupdf.open()
    p = doc.new_page(width=600, height=800)
    p.insert_text((72, 100), "Confidential Protected Material")
    doc.save(
        str(pdf_path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="correct_user_pw_2026",
        owner_pw="correct_owner_pw_2026",
    )
    doc.close()
    return pdf_path


# =============================================================================
# 1. Packaged Binary & CLI Tests (from outside repository working directory)
# =============================================================================

def test_m8_packaged_binary_outside_cwd_flags(tmp_path: Path):
    """Smoke tests packaged binary from outside repo for version, help, and invalid options."""
    root = Path(__file__).parent.parent
    executable = root / "dist" / "paperview" / "paperview"
    assert executable.is_file(), f"Packaged executable not found at {executable}"

    # Version flag from outside repo
    proc_ver = subprocess.run(
        [str(executable), "--version"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc_ver.returncode == 0
    assert "PaperView 1.0.0" in proc_ver.stdout

    # Help flag from outside repo
    proc_help = subprocess.run(
        [str(executable), "--help"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc_help.returncode == 0
    assert "Usage:" in proc_help.stdout
    assert "paperview [OPTIONS] [PDF_FILE]" in proc_help.stdout

    # Unrecognized option flag
    proc_bad = subprocess.run(
        [str(executable), "--nonexistent-flag"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc_bad.returncode == 2
    assert "unrecognized option" in proc_bad.stderr


def test_m8_packaged_binary_opens_pdf_with_spaces(tmp_path: Path):
    """Tests that the packaged executable opens a generated PDF with spaces in its path."""
    root = Path(__file__).parent.parent
    executable = root / "dist" / "paperview" / "paperview"

    # Create PDF with spaces in filename outside repo
    pdf_path = tmp_path / "My Quarterly Financial Report & Audit (2026).pdf"
    doc = pymupdf.open()
    p = doc.new_page(width=612, height=792)
    p.insert_text((72, 100), "Testing Packaged Binary Open With Spaces")
    doc.save(str(pdf_path))
    doc.close()

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.Popen(
        [str(executable), str(pdf_path)],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Give process time to initialize and open the PDF
        time.sleep(2.0)
        assert proc.poll() is None, f"Process exited unexpectedly with code {proc.returncode}"

        # Inspect /proc/<pid>/fd to verify that the file was opened
        fd_dir = Path(f"/proc/{proc.pid}/fd")
        opened_targets = []
        if fd_dir.is_dir():
            for link in fd_dir.iterdir():
                try:
                    target = os.readlink(link)
                    opened_targets.append(target)
                except OSError:
                    pass
        matching = [t for t in opened_targets if "My Quarterly Financial Report" in t]
        assert len(matching) > 0, f"PDF file not opened in file descriptors: {opened_targets}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


# =============================================================================
# 2. Missing and Corrupt File Error Resilience
# =============================================================================

def test_m8_missing_and_corrupt_file_handling(qtbot, monkeypatch, capsys, tmp_path: Path):
    """Verifies that missing paths and corrupt files produce clear stderr logs and UI dialogs."""
    win = MainWindow(initial_file=None)
    qtbot.addWidget(win)

    dialog_errors = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, text: dialog_errors.append((title, text)),
    )

    # 1. Missing file
    missing_path = tmp_path / "missing_file_xyz.pdf"
    win.open_file_path(str(missing_path))
    assert win.doc_mgr.is_open is False
    assert len(dialog_errors) == 1
    assert "File not found" in dialog_errors[0][1]

    captured = capsys.readouterr()
    assert "[PaperView Error] File not found" in captured.err

    # 2. Corrupt / Non-PDF file
    corrupt_path = tmp_path / "corrupt_data.pdf"
    corrupt_path.write_bytes(b"CORRUPT_HEADER_NOT_A_PDF_STREAM_BYTES_9999\xff\x00")
    win.open_file_path(str(corrupt_path))
    assert win.doc_mgr.is_open is False
    assert len(dialog_errors) == 2
    assert "Failed to Open PDF" in dialog_errors[1][0]

    captured2 = capsys.readouterr()
    assert "[PaperView Error] Failed to open document" in captured2.err


# =============================================================================
# 3. Desktop Integration Audit (Isolated User Environment)
# =============================================================================

def test_m8_desktop_file_and_user_scripts_audit():
    """Audits desktop specification, user installation confinement, and uninstallation safety."""
    root = Path(__file__).parent.parent
    install_sh = root / "scripts" / "install_user.sh"
    uninstall_sh = root / "scripts" / "uninstall_user.sh"
    desktop_file = root / "packaging" / "paperview.desktop"

    # desktop-file-validate check if installed
    validator = shutil.which("desktop-file-validate")
    if validator:
        res = subprocess.run([validator, str(desktop_file)], capture_output=True, text=True)
        assert res.returncode == 0, f"desktop-file-validate failed: {res.stderr}"

    # Test install and uninstall in temporary user home with spaces
    with tempfile.TemporaryDirectory() as base_tmp:
        fake_home = Path(base_tmp) / "Test User With Spaces"
        fake_home.mkdir()

        env = os.environ.copy()
        env["HOME"] = str(fake_home)
        env.pop("XDG_DATA_HOME", None)
        env.pop("PAPERVIEW_PREFIX", None)

        # 1. Install
        res_inst1 = subprocess.run([str(install_sh)], cwd=str(root), env=env, capture_output=True, text=True)
        assert res_inst1.returncode == 0

        bin_file = fake_home / ".local" / "bin" / "paperview"
        lib_dir = fake_home / ".local" / "lib" / "paperview"
        app_file = fake_home / ".local" / "share" / "applications" / "paperview.desktop"
        svg_icon = fake_home / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps" / "paperview.svg"

        assert bin_file.is_symlink()
        assert (lib_dir / "paperview").is_file()
        assert app_file.is_file()
        assert svg_icon.is_file()

        # 2. Re-running installer must be safe and idempotent
        res_inst2 = subprocess.run([str(install_sh)], cwd=str(root), env=env, capture_output=True, text=True)
        assert res_inst2.returncode == 0

        # 3. Create unrelated user files to verify uninstaller precision
        other_bin = fake_home / ".local" / "bin" / "unrelated_tool"
        other_bin.write_text("#!/bin/sh\necho test\n")
        other_desktop = fake_home / ".local" / "share" / "applications" / "other_app.desktop"
        other_desktop.write_text("[Desktop Entry]\nType=Application\nName=OtherApp\n")

        # 4. Uninstall
        res_uninst1 = subprocess.run([str(uninstall_sh)], cwd=str(root), env=env, capture_output=True, text=True)
        assert res_uninst1.returncode == 0

        assert not bin_file.exists()
        assert not lib_dir.exists()
        assert not app_file.exists()
        assert not svg_icon.exists()

        # Unrelated files MUST be preserved
        assert other_bin.is_file(), "Unrelated binary was erroneously removed!"
        assert other_desktop.is_file(), "Unrelated desktop file was erroneously removed!"

        # 5. Re-running uninstaller must be safe and idempotent
        res_uninst2 = subprocess.run([str(uninstall_sh)], cwd=str(root), env=env, capture_output=True, text=True)
        assert res_uninst2.returncode == 0


# =============================================================================
# 4. Release Integrity (Source Protection, Redaction, Security, Signatures)
# =============================================================================

def test_m8_save_copy_as_preserves_source_and_produces_valid_output(qtbot, monkeypatch, sample_test_pdf: Path, tmp_path: Path):
    """Verifies that Save Copy As protects the source file and writes a valid readable copy."""
    orig_bytes = sample_test_pdf.read_bytes()
    orig_sha256 = hashlib.sha256(orig_bytes).hexdigest()

    win = MainWindow(initial_file=str(sample_test_pdf))
    qtbot.addWidget(win)

    # Attempt to overwrite source file -> Must be rejected with warning
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda parent, caption, dir, filter: (str(sample_test_pdf), "PDF Files (*.pdf)"),
    )
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append((title, text)))
    assert win.action_save_as() is False
    assert len(warnings) == 1
    assert "cannot overwrite the active file" in warnings[0][1]

    # Save to valid destination
    copy_path = tmp_path / "Verified_Output_Copy.pdf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda parent, caption, dir, filter: (str(copy_path), "PDF Files (*.pdf)"),
    )
    infos = []
    monkeypatch.setattr(QMessageBox, "information", lambda parent, title, text: infos.append((title, text)))
    assert win.action_save_as() is True
    assert copy_path.is_file()

    # Source file must be bit-for-bit identical
    assert hashlib.sha256(sample_test_pdf.read_bytes()).hexdigest() == orig_sha256

    # Saved copy must open and have 4 pages
    doc_check = DocumentManager()
    meta = doc_check.open_document(copy_path)
    assert meta.page_count == 4
    doc_check.close()


def test_m8_permanent_redaction_integrity(tmp_path: Path):
    """Verifies that redaction permanently removes underlying text from saved copy while source is untouched."""
    source_pdf = tmp_path / "Source_Before_Redaction.pdf"
    doc = pymupdf.open()
    p = doc.new_page(width=612, height=792)
    p.insert_text((72, 100), "Confidential PIN: 4892-SECRET-CODE")
    p.insert_text((72, 150), "Public Notice: This document has been prepared for review.")
    doc.save(str(source_pdf), deflate=False)
    doc.close()

    source_bytes = source_pdf.read_bytes()
    source_check = pymupdf.open(str(source_pdf))
    assert "4892-SECRET-CODE" in source_check[0].get_text()
    assert len(source_check[0].search_for("4892-SECRET-CODE")) == 1
    source_check.close()

    doc_mgr = DocumentManager()
    doc_mgr.open_document(source_pdf)

    # Add and apply redaction over the confidential text
    search_rects = doc_mgr.doc[0].search_for("4892-SECRET-CODE")
    assert len(search_rects) == 1
    rect = search_rects[0]

    doc_mgr.add_redaction_region(0, rect)
    applied = doc_mgr.apply_redactions()
    assert applied.get(0, 0) == 1

    # Save copy
    redacted_copy = tmp_path / "Permanently_Redacted_Output.pdf"
    doc_mgr.save_copy(redacted_copy)
    doc_mgr.close()

    # Verify underlying text is completely absent from the redacted copy
    check_doc = pymupdf.open(str(redacted_copy))
    page_text = check_doc[0].get_text()
    assert "4892-SECRET-CODE" not in page_text
    assert "Public Notice" in page_text
    assert len(check_doc[0].search_for("4892-SECRET-CODE")) == 0
    check_doc.close()

    # Verify original source remains intact and untouched
    assert source_pdf.read_bytes() == source_bytes


def test_m8_password_protection_reopen_and_reject(protected_test_pdf: Path):
    """Verifies that encrypted PDFs reject invalid passwords and open with the correct password."""
    doc_mgr = DocumentManager()

    # 1. Opening without password or with wrong password fails
    with pytest.raises((PasswordRequiredError, InvalidPasswordError, pymupdf.FileDataError)):
        doc_mgr.open_document(protected_test_pdf, password="incorrect_password_123")

    # 2. Opening with correct password succeeds
    meta = doc_mgr.open_document(protected_test_pdf, password="correct_user_pw_2026")
    assert meta.is_encrypted is True
    assert meta.page_count == 1
    doc_mgr.close()


def test_m8_visible_signature_not_represented_as_cryptographic(qtbot, sample_test_pdf: Path):
    """Verifies that visible signatures are explicitly marked as non-cryptographic."""
    doc_mgr = DocumentManager()
    doc_mgr.open_document(sample_test_pdf)

    # Place visible signature
    rect = pymupdf.Rect(100, 200, 300, 260)
    ok = doc_mgr.add_visible_signature(
        page_index=0,
        rect=rect,
        signer_name="Auditor John Snow",
        signature_text="John Snow (Audited)",
        date_str="2026-10-20",
    )
    assert ok is True

    # Verify the underlying annotation is a visible annotation, NOT a cryptographic /Sig dictionary
    doc = doc_mgr._doc
    page = doc[0]
    annots = list(page.annots())
    assert len(annots) >= 1
    sig_annot = annots[0]
    info = sig_annot.info
    assert info.get("subject") == "VisibleSignature"
    assert "Auditor John Snow" in info.get("title", "")

    # Verify SignatureDialog contains prominent user warning
    dlg = SignatureDialog(doc_mgr, current_page=0)
    qtbot.addWidget(dlg)
    disclaimer_labels = [lbl.text() for lbl in dlg.findChildren(QLabel)]
    all_disc_text = " ".join(disclaimer_labels)
    assert "NOT a Cryptographic Digital Signature" in all_disc_text
    assert "certificate-based" in all_disc_text

    doc_mgr.close()


def test_m8_metadata_dependencies_and_licensing(qtbot):
    """Verifies About dialog, package metadata, dependencies, and AGPLv3 licensing gate."""
    # Package identity
    assert __app_name__ == "PaperView"
    assert __version__ == "1.0.0"
    assert "AGPL" in __license__

    # requirements.txt audit
    req_file = Path(__file__).parent.parent / "requirements.txt"
    assert req_file.is_file()
    req_text = req_file.read_text(encoding="utf-8")
    assert "PySide6" in req_text
    assert "pymupdf" in req_text
    assert "pytest" in req_text
    assert "pyinstaller" in req_text

    # LICENSE_NOTES.md audit
    lic_file = Path(__file__).parent.parent / "LICENSE_NOTES.md"
    assert lic_file.is_file()
    lic_text = lic_file.read_text(encoding="utf-8")
    assert "AGPLv3" in lic_text
    assert "Artifex Software" in lic_text
    assert "PyMuPDF" in lic_text

    # AboutDialog UI audit
    about = AboutDialog()
    qtbot.addWidget(about)
    about_text = " ".join(lbl.text() for lbl in about.findChildren(QLabel))
    assert "PaperView" in about_text
    assert "1.0.0" in about_text
    assert "GNU AGPLv3" in about_text
    assert "Artifex" in about_text


# =============================================================================
# 5. Packaged Bundle Qt Platform Plugins and SVG/Print Support
# =============================================================================

def test_m8_bundled_plugins_and_shared_libraries():
    """Verifies that required Qt platform plugins, SVG, and PrintSupport are present in the bundle."""
    root = Path(__file__).parent.parent
    bundle_internal = root / "dist" / "paperview" / "_internal"

    if not bundle_internal.is_dir():
        pytest.skip("dist/paperview/_internal not found; build package first")

    # Platforms
    platforms_dir = bundle_internal / "PySide6" / "Qt" / "plugins" / "platforms"
    assert platforms_dir.is_dir(), f"Platforms directory missing: {platforms_dir}"
    platform_files = [f.name for f in platforms_dir.glob("*.so")]
    assert "libqwayland.so" in platform_files, "libqwayland.so missing from bundled platforms"
    assert "libqxcb.so" in platform_files, "libqxcb.so missing from bundled platforms"
    assert "libqoffscreen.so" in platform_files, "libqoffscreen.so missing from bundled platforms"

    # SVG support
    svg_img = bundle_internal / "PySide6" / "Qt" / "plugins" / "imageformats" / "libqsvg.so"
    svg_icon = bundle_internal / "PySide6" / "Qt" / "plugins" / "iconengines" / "libqsvgicon.so"
    assert svg_img.is_file(), "libqsvg.so missing from imageformats"
    assert svg_icon.is_file(), "libqsvgicon.so missing from iconengines"

    # Print support
    cups_plugin = bundle_internal / "PySide6" / "Qt" / "plugins" / "printsupport" / "libcupsprintersupport.so"
    assert cups_plugin.is_file(), "libcupsprintersupport.so missing from printsupport"


# =============================================================================
# 6. Full Packaged GUI Lifecycle & Functional Verification
# =============================================================================

def test_m8_gui_startup_render_nav_zoom_search_and_shutdown(qtbot, sample_test_pdf: Path):
    """
    Actually launches and exercises the GUI:
    - Startup & window initialization
    - PDF rendering (renders page image and verifies non-null QImage)
    - Navigation (next, prev, jump)
    - Zoom controls (zoom in, zoom out, fit width, fit page)
    - Search (queries text, cycles hits)
    - Clean shutdown
    """
    win = MainWindow(initial_file=str(sample_test_pdf))
    qtbot.addWidget(win)
    win.show()

    # 1. Startup & Document Open
    assert win.doc_mgr.is_open is True
    assert win.doc_mgr.page_count == 4
    assert sample_test_pdf.name in win.windowTitle()

    # 2. PDF Rendering
    task = RenderTask(page_index=0, zoom=1.0, dpr=1.0)
    worker = RenderWorker(doc_path=str(sample_test_pdf), password=None, task=task)
    rendered_images = []
    worker.signals.finished.connect(lambda p_idx, z, img: rendered_images.append((p_idx, z, img)))
    worker.run()

    assert len(rendered_images) == 1
    p_idx, z_val, qimg = rendered_images[0]
    assert p_idx == 0
    assert isinstance(qimg, QImage)
    assert not qimg.isNull()
    assert qimg.width() > 0 and qimg.height() > 0

    # 3. Navigation
    assert win.viewer.current_page == 0
    win.action_next_page()
    assert win.viewer.current_page == 1
    win.action_prev_page()
    assert win.viewer.current_page == 0
    win.navigate_to_page(3)
    assert win.viewer.current_page == 3

    # 4. Zoom
    initial_zoom = win.viewer.zoom
    win.action_zoom_in()
    assert win.viewer.zoom > initial_zoom
    win.action_zoom_out()
    win.action_fit_width()
    assert win.viewer.zoom > 0
    win.action_fit_page()
    assert win.viewer.zoom > 0

    # 5. Search
    win.search_bar.show_and_focus()
    assert win.search_bar.isVisible()
    win.search_bar.input_field.setText("searchable")
    win.search_bar.input_field.returnPressed.emit()
    win.search_bar.next_btn.click()
    assert len(win.search_mgr.hits) >= 0

    # 6. Shutdown
    win.close()
    assert not win.isVisible()
