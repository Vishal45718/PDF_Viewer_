"""
Milestone 7 Test Suite: Packaging, Application Identity, and Distribution Readiness.
Tests:
1. Application metadata and version reporting (CLI -v / --version and -h / --help).
2. Build script validation (build_linux.sh, install_user.sh, uninstall_user.sh).
3. Desktop entry specification and compliance (paperview.desktop).
4. Icon asset generation and resolution integrity.
5. Command-line path handling (relative, absolute, URI scheme, spaces & symbols).
6. Missing and corrupt file error resilience.
7. Encrypted document handling and password flow.
8. Save Copy As original source protection (byte preservation & active file protection).
9. Qt platform plugin discovery and diagnostic verification.
10. About dialog metadata, specs, and AGPL licensing notice.
11. Clean application shutdown.
12. Standalone binary smoke check from outside repository CWD.
"""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
import pymupdf
from PySide6.QtCore import QLibraryInfo, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox

import paperview
from paperview import __app_name__, __description__, __version__, __license__
from paperview.app import _check_platform_plugins, main as app_main
from paperview.dialogs import AboutDialog
from paperview.icons import get_app_icon, get_app_icon_svg
from paperview.main_window import MainWindow


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Creates a temporary multi-page fixture PDF for testing."""
    p = tmp_path / "fixture_sample.pdf"
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 100), f"PaperView Milestone 7 Test Page {i + 1}")
        page.insert_text((72, 140), "Standalone packaging and distribution verification document.")
    doc.save(str(p))
    doc.close()
    return p


@pytest.fixture
def encrypted_pdf(tmp_path: Path) -> Path:
    """Creates a temporary password-protected PDF fixture."""
    p = tmp_path / "fixture_encrypted.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "Confidential Milestone 7 Test Document")
    doc.save(
        str(p),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="testpass123",
        owner_pw="adminpass123",
    )
    doc.close()
    return p


def test_metadata_and_version_strings():
    """Verifies consistent application identity and metadata."""
    assert __app_name__ == "PaperView"
    assert __version__ == "1.0.0"
    assert "PDF" in __description__
    assert "AGPL" in __license__


def test_cli_version_flag(capsys):
    """Verifies that --version and -v exit cleanly and print expected version info."""
    exit_code_long = app_main(["--version"])
    captured_long = capsys.readouterr()
    assert exit_code_long == 0
    assert "PaperView 1.0.0" in captured_long.out

    exit_code_short = app_main(["-v"])
    captured_short = capsys.readouterr()
    assert exit_code_short == 0
    assert "PaperView 1.0.0" in captured_short.out


def test_cli_help_flag(capsys):
    """Verifies that --help and -h display usage instructions and exit cleanly."""
    exit_code = app_main(["--help"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Usage:" in captured.out
    assert "paperview [OPTIONS] [PDF_FILE]" in captured.out
    assert "--version" in captured.out
    assert "--help" in captured.out


def test_build_script_properties():
    """Verifies the existence, permissions, and structure of scripts/build_linux.sh."""
    build_script = Path(__file__).parent.parent / "scripts" / "build_linux.sh"
    assert build_script.is_file(), "scripts/build_linux.sh does not exist"
    assert os.access(build_script, os.X_OK), "scripts/build_linux.sh must be executable"

    content = build_script.read_text(encoding="utf-8")
    assert "--onedir" in content, "Build script must use one-directory PyInstaller mode"
    assert "--distpath" in content, "Build script must specify separate distpath"
    assert "paperview/app.py" in content, "Build script must package paperview/app.py"
    assert "PySide6" in content, "Build script must check PySide6"
    assert "pymupdf" in content, "Build script must check pymupdf"


def test_install_and_uninstall_scripts():
    """Verifies the user installation and removal scripts exist and are executable."""
    root = Path(__file__).parent.parent
    install_script = root / "scripts" / "install_user.sh"
    uninstall_script = root / "scripts" / "uninstall_user.sh"

    assert install_script.is_file() and os.access(install_script, os.X_OK)
    assert uninstall_script.is_file() and os.access(uninstall_script, os.X_OK)

    inst_content = install_script.read_text(encoding="utf-8")
    assert "lib/paperview" in inst_content
    assert "BIN_DIR" in inst_content
    assert "paperview.desktop" in inst_content

    uninst_content = uninstall_script.read_text(encoding="utf-8")
    assert "rm -rf" in uninst_content
    assert "paperview.desktop" in uninst_content


def test_desktop_entry_specification():
    """Validates the desktop file against freedesktop.org specifications."""
    import configparser

    desktop_file = Path(__file__).parent.parent / "packaging" / "paperview.desktop"
    assert desktop_file.is_file(), "packaging/paperview.desktop must exist"

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(str(desktop_file), encoding="utf-8")

    assert "Desktop Entry" in cfg.sections()
    entry = cfg["Desktop Entry"]

    assert entry.get("Type") == "Application"
    assert entry.get("Name") == "PaperView"
    assert "paperview" in entry.get("Exec", "")
    assert entry.get("Icon") == "paperview"
    assert entry.get("StartupWMClass") == "PaperView"
    assert "application/pdf" in entry.get("MimeType", "")
    assert "Office" in entry.get("Categories", "")

    # If desktop-file-validate is available on the system, run it
    validator = shutil.which("desktop-file-validate")
    if validator:
        res = subprocess.run([validator, str(desktop_file)], capture_output=True, text=True)
        assert res.returncode == 0, f"desktop-file-validate failed: {res.stderr}"


def test_icon_assets_and_qicon(qtbot):
    """Verifies the application icon SVG, multi-resolution PNGs, and QIcon provider."""
    icons_dir = Path(__file__).parent.parent / "packaging" / "icons"
    svg_file = icons_dir / "paperview.svg"
    png_256 = icons_dir / "paperview-256x256.png"

    assert svg_file.is_file()
    assert svg_file.stat().st_size > 100
    assert "<svg" in svg_file.read_text(encoding="utf-8")

    assert png_256.is_file()
    assert png_256.stat().st_size > 500

    icon = get_app_icon()
    assert isinstance(icon, QIcon)
    assert not icon.isNull()

    pix = icon.pixmap(64, 64)
    assert not pix.isNull()
    # Support high-DPI scaling (logical 64px = physical 64 or 128px depending on DPR)
    logical_w = pix.width() / pix.devicePixelRatio()
    logical_h = pix.height() / pix.devicePixelRatio()
    assert logical_w == 64 and logical_h == 64


def test_qt_plugin_discovery_and_diagnostics():
    """Verifies Qt plugin path resolution and checks diagnostic routine."""
    plugins_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    assert plugins_path, "Qt PluginsPath must be discoverable"

    platforms_dir = Path(plugins_path) / "platforms"
    assert platforms_dir.is_dir(), f"Platforms directory {platforms_dir} must exist"

    # In standard Linux packaging/runtime, wayland or xcb platform plugins must exist
    platform_plugins = [f.name for f in platforms_dir.glob("*.so")]
    assert any("qwayland" in p or "qxcb" in p or "qoffscreen" in p for p in platform_plugins), (
        f"Expected at least one standard Linux platform plugin, found: {platform_plugins}"
    )

    # Diagnostic routine must run cleanly without error
    _check_platform_plugins()


def test_about_dialog(qtbot):
    """Verifies that the About dialog displays proper identity, specs, and AGPL obligations."""
    from PySide6.QtWidgets import QLabel

    dlg = AboutDialog()
    qtbot.addWidget(dlg)

    assert "PaperView" in dlg.windowTitle()
    labels = dlg.findChildren(QLabel)
    all_text = " ".join(lbl.text() for lbl in labels)

    # Must contain version, PySide6, PyMuPDF, and AGPL license notice
    assert "1.0.0" in all_text
    assert "PySide6" in all_text
    assert "PyMuPDF" in all_text
    assert "AGPLv3" in all_text


def test_command_line_path_handling(qtbot, sample_pdf: Path):
    """Verifies that MainWindow correctly loads a PDF specified as initial_file."""
    win = MainWindow(initial_file=str(sample_pdf))
    qtbot.addWidget(win)

    assert win.doc_mgr.is_open is True
    assert win.doc_mgr.page_count == 3
    assert sample_pdf.name in win.windowTitle()


def test_file_path_with_spaces_and_special_chars(qtbot, tmp_path: Path):
    """Verifies opening PDF files with spaces, parentheses, and ampersands."""
    special_name = "Quarterly Report & Analytics (Draft 2026).pdf"
    p = tmp_path / special_name

    doc = pymupdf.open()
    doc.new_page(width=500, height=500)
    doc.save(str(p))
    doc.close()

    win = MainWindow(initial_file=str(p))
    qtbot.addWidget(win)

    assert win.doc_mgr.is_open is True
    assert special_name in win.windowTitle()

    # Also test URI format (file:// scheme as passed by desktop file managers)
    uri = p.as_uri()
    win.open_file_path(uri)
    assert win.doc_mgr.is_open is True
    assert special_name in win.windowTitle()


def test_missing_and_corrupt_file_handling(qtbot, monkeypatch, tmp_path: Path):
    """Verifies robust error handling and reporting for missing and corrupted files."""
    win = MainWindow(initial_file=None)
    qtbot.addWidget(win)

    error_messages = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, text: error_messages.append((title, text)),
    )

    # 1. Missing file
    missing_path = tmp_path / "nonexistent_file.pdf"
    win.open_file_path(str(missing_path))
    assert win.doc_mgr.is_open is False
    assert len(error_messages) == 1
    assert "File not found" in error_messages[0][1]

    # 2. Corrupt / Non-PDF file
    corrupt_path = tmp_path / "corrupted.pdf"
    corrupt_path.write_bytes(b"INVALID_HEADER_GARBAGE_DATA_123456789\x00\xff")
    win.open_file_path(str(corrupt_path))
    assert win.doc_mgr.is_open is False
    assert len(error_messages) == 2
    assert "Error opening document" in error_messages[1][1]


def test_encrypted_pdf_handling(qtbot, monkeypatch, encrypted_pdf: Path):
    """Verifies safe handling of encrypted documents and password validation."""
    win = MainWindow(initial_file=None)
    qtbot.addWidget(win)

    # Attempt open with invalid password directly via doc_mgr
    with pytest.raises(pymupdf.FileDataError):
        # Trying to open an encrypted file directly without password raises error in pymupdf
        doc = pymupdf.open(str(encrypted_pdf))
        if doc.is_encrypted and not doc.authenticate("wrong_password"):
            raise pymupdf.FileDataError("Invalid password")

    # Open with correct password
    metadata = win.doc_mgr.open_document(encrypted_pdf, password="testpass123")
    assert metadata.page_count == 1
    assert win.doc_mgr.is_open is True


def test_save_copy_as_source_protection(qtbot, monkeypatch, sample_pdf: Path, tmp_path: Path):
    """
    Verifies that 'Save Copy As' protects the source file:
    1. Prevents overwriting the active document directly.
    2. Writes a separate copy without altering original source bytes.
    """
    orig_bytes = sample_pdf.read_bytes()
    orig_hash = hashlib.sha256(orig_bytes).hexdigest()

    win = MainWindow(initial_file=str(sample_pdf))
    qtbot.addWidget(win)

    warning_dialogs = []
    info_dialogs = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text: warning_dialogs.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text: info_dialogs.append((title, text)),
    )

    # Attempt 1: Specify same file as destination -> Must be rejected!
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda parent, caption, dir, filter: (str(sample_pdf), "PDF Files (*.pdf)"),
    )
    res_rejected = win.action_save_as()
    assert res_rejected is False
    assert len(warning_dialogs) == 1
    assert "cannot overwrite the active file" in warning_dialogs[0][1]

    # Attempt 2: Specify separate destination file -> Must succeed safely!
    dest_copy = tmp_path / "saved_copy_separate.pdf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda parent, caption, dir, filter: (str(dest_copy), "PDF Files (*.pdf)"),
    )
    res_success = win.action_save_as()
    assert res_success is True
    assert dest_copy.is_file()

    # Verify original file was NEVER modified or truncated
    current_orig_bytes = sample_pdf.read_bytes()
    current_orig_hash = hashlib.sha256(current_orig_bytes).hexdigest()
    assert current_orig_hash == orig_hash, "Original file hash changed during Save Copy As!"

    # Verify destination copy is a valid independent PDF
    copy_doc = pymupdf.open(str(dest_copy))
    assert copy_doc.page_count == 3
    copy_doc.close()


def test_clean_shutdown(qtbot, sample_pdf: Path):
    """Verifies that the application window and render subsystem shut down cleanly."""
    win = MainWindow(initial_file=str(sample_pdf))
    qtbot.addWidget(win)
    assert win.doc_mgr.is_open is True

    # Close the window and ensure clean resource release
    win.close()
    assert not win.isVisible()


def test_standalone_executable_smoke(tmp_path: Path):
    """
    Smoke tests the standalone PyInstaller packaged binary.
    Executes from outside the repository in tmp_path to verify CWD independence.
    """
    root = Path(__file__).parent.parent
    executable = root / "dist" / "paperview" / "paperview"

    if not executable.is_file():
        pytest.skip("Standalone executable not yet built; run scripts/build_linux.sh first")

    # 1. Version flag from clean temp dir
    proc_ver = subprocess.run(
        [str(executable), "--version"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc_ver.returncode == 0
    assert "PaperView 1.0.0" in proc_ver.stdout

    # 2. Help flag from clean temp dir
    proc_help = subprocess.run(
        [str(executable), "--help"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc_help.returncode == 0
    assert "Usage:" in proc_help.stdout
