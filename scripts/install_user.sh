#!/usr/bin/env bash
# ==============================================================================
# PaperView — User Installation Script
# Installs PaperView into the user's home directory ($HOME/.local)
# Requires no root / sudo privileges.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist/paperview"

if [ ! -d "$DIST_DIR" ] || [ ! -x "$DIST_DIR/paperview" ]; then
    echo "ERROR: Standalone package not found at $DIST_DIR"
    echo "Please build the package first by running:"
    echo "  $PROJECT_ROOT/scripts/build_linux.sh"
    exit 1
fi

PREFIX="${PAPERVIEW_PREFIX:-$HOME/.local}"
LIB_DIR="$PREFIX/lib/paperview"
BIN_DIR="$HOME/.local/bin"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"

echo "=== Installing PaperView to $HOME/.local ==="

# 1. Install application bundle
echo "Installing application bundle to $LIB_DIR..."
rm -rf "$LIB_DIR"
mkdir -p "$LIB_DIR"
cp -r "$DIST_DIR"/* "$LIB_DIR/"

# 2. Install executable symlink
echo "Installing binary launcher to $BIN_DIR/paperview..."
mkdir -p "$BIN_DIR"
ln -sf "$LIB_DIR/paperview" "$BIN_DIR/paperview"

# 3. Install icons into hicolor theme
echo "Installing application icons to $ICON_DIR..."
mkdir -p "$ICON_DIR/scalable/apps"
cp "$PROJECT_ROOT/packaging/icons/paperview.svg" "$ICON_DIR/scalable/apps/paperview.svg"

for size in 32 48 64 128 256; do
    target_dir="$ICON_DIR/${size}x${size}/apps"
    mkdir -p "$target_dir"
    if [ -f "$PROJECT_ROOT/packaging/icons/paperview-${size}x${size}.png" ]; then
        cp "$PROJECT_ROOT/packaging/icons/paperview-${size}x${size}.png" "$target_dir/paperview.png"
    fi
done

# 4. Install Desktop Entry
echo "Installing desktop entry to $APP_DIR/paperview.desktop..."
mkdir -p "$APP_DIR"
cp "$PROJECT_ROOT/packaging/paperview.desktop" "$APP_DIR/paperview.desktop"

# 5. Update Desktop and Icon Caches if tools available
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$ICON_DIR" 2>/dev/null || true
fi

echo ""
echo "PaperView successfully installed!"
echo "Binary location: $BIN_DIR/paperview"
echo "Ensure $BIN_DIR is in your PATH (e.g. export PATH=\"\$HOME/.local/bin:\$PATH\")."
echo "You can launch PaperView from your desktop launcher or terminal with: paperview"
