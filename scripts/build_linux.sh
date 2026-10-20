#!/usr/bin/env bash
# ==============================================================================
# PaperView — Reproducible Linux Standalone Build Script
# Builds a standalone one-directory Linux distribution package using PyInstaller.
# Tested on Arch Linux (x86_64) under Hyprland / Wayland & X11.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== PaperView Standalone Build Process ==="
echo "Project Root: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

# 1. Resolve Python and Virtual Environment
if [ -d "$PROJECT_ROOT/.venv" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="$(command -v python3)"
else
    echo "ERROR: Python 3 not found. Please create .venv or install python3." >&2
    exit 1
fi

echo "Using Python: $($PYTHON --version) at $PYTHON"

# 2. Verify / Install Required Build Dependencies
echo "Checking dependencies..."
$PYTHON -c "import PySide6, pymupdf" || {
    echo "ERROR: PySide6 or pymupdf missing from environment. Run: pip install -r requirements.txt" >&2
    exit 1
}

if ! $PYTHON -c "import PyInstaller" &>/dev/null; then
    echo "PyInstaller not found. Installing into virtualenv..."
    $PYTHON -m pip install "pyinstaller>=6.10.0"
fi

# 3. Ensure Icon Assets Exist
echo "Generating/verifying packaging icon assets..."
$PYTHON -c '
from pathlib import Path
from PySide6.QtGui import QGuiApplication, QPixmap, QPainter
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvg import QSvgRenderer
import sys
from paperview.icons import APP_ICON_SVG

icons_dir = Path("packaging/icons")
icons_dir.mkdir(parents=True, exist_ok=True)
(icons_dir / "paperview.svg").write_text(APP_ICON_SVG, encoding="utf-8")

app = QGuiApplication(sys.argv)
renderer = QSvgRenderer(QByteArray(APP_ICON_SVG.encode("utf-8")))
for size in (32, 48, 64, 128, 256):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    pix.save(str(icons_dir / f"paperview-{size}x{size}.png"), "PNG")
(icons_dir / "paperview-256x256.png").replace(icons_dir / "paperview-256x256.png")
pix256 = QPixmap(256, 256)
pix256.fill(Qt.GlobalColor.transparent)
p = QPainter(pix256)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
renderer.render(p)
p.end()
pix256.save(str(icons_dir / "paperview.png"), "PNG")
'

# 4. Prepare Output Directories
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"

echo "Cleaning previous build artifacts..."
rm -rf "$BUILD_DIR"
rm -rf "$DIST_DIR/paperview"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

# 5. Execute PyInstaller Standalone Build
echo "Executing PyInstaller one-directory packaging..."
$PYTHON -m PyInstaller \
    --name paperview \
    --onedir \
    --windowed \
    --clean \
    --noconfirm \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --specpath "$BUILD_DIR" \
    --icon "$PROJECT_ROOT/packaging/icons/paperview-256x256.png" \
    --add-data "$PROJECT_ROOT/packaging:packaging" \
    --add-data "$PROJECT_ROOT/LICENSE_NOTES.md:." \
    --hidden-import PySide6.QtSvg \
    --hidden-import PySide6.QtPrintSupport \
    --hidden-import fitz \
    --hidden-import pymupdf \
    "$PROJECT_ROOT/paperview/app.py"

# 6. Verify Packaging Result
EXECUTABLE="$DIST_DIR/paperview/paperview"
if [ ! -x "$EXECUTABLE" ]; then
    echo "ERROR: Packaged executable not found at $EXECUTABLE" >&2
    exit 1
fi

# Ensure executable permissions
chmod +x "$EXECUTABLE"

# 7. Verification Smoke Check
echo "Testing standalone executable version reporting..."
APP_VER_OUTPUT="$("$EXECUTABLE" --version)"
echo "Standalone binary reported: $APP_VER_OUTPUT"

echo ""
echo "================================================================="
echo "BUILD SUCCESSFUL!"
echo "Package directory : $DIST_DIR/paperview"
echo "Binary executable : $EXECUTABLE"
echo "Size on disk      : $(du -sh "$DIST_DIR/paperview" | cut -f1)"
echo ""
echo "To test run:"
echo "  $EXECUTABLE [path/to/file.pdf]"
echo ""
echo "To install for the current user:"
echo "  $PROJECT_ROOT/scripts/install_user.sh"
echo "================================================================="
