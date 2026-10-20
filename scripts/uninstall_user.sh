#!/usr/bin/env bash
# ==============================================================================
# PaperView — User Uninstallation Script
# Safely removes PaperView from $HOME/.local
# ==============================================================================
set -euo pipefail

PREFIX="${PAPERVIEW_PREFIX:-$HOME/.local}"
LIB_DIR="$PREFIX/lib/paperview"
BIN_FILE="$HOME/.local/bin/paperview"
APP_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/applications/paperview.desktop"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"

echo "=== Uninstalling PaperView from $HOME/.local ==="

if [ -d "$LIB_DIR" ]; then
    echo "Removing $LIB_DIR..."
    rm -rf "$LIB_DIR"
fi

# Clean up legacy library path if previously installed there
LEGACY_LIB="${XDG_DATA_HOME:-$HOME/.local/share}/lib/paperview"
if [ -d "$LEGACY_LIB" ]; then
    echo "Removing legacy library directory $LEGACY_LIB..."
    rm -rf "$LEGACY_LIB"
fi

if [ -L "$BIN_FILE" ] || [ -f "$BIN_FILE" ]; then
    echo "Removing $BIN_FILE..."
    rm -f "$BIN_FILE"
fi

if [ -f "$APP_FILE" ]; then
    echo "Removing $APP_FILE..."
    rm -f "$APP_FILE"
fi

echo "Removing installed icons..."
rm -f "$ICON_DIR/scalable/apps/paperview.svg"
for size in 32 48 64 128 256; do
    rm -f "$ICON_DIR/${size}x${size}/apps/paperview.png"
done

# Update Desktop and Icon Caches
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "${XDG_DATA_HOME:-$HOME/.local/share}/applications" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$ICON_DIR" 2>/dev/null || true
fi

echo "PaperView has been completely removed from your user environment."
