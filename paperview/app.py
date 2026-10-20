"""
PaperView Entry Point.
Launches the PySide6 Qt application.
Handles command-line arguments, desktop file paths, version reporting,
and environment diagnostics.
"""

import sys
from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import QApplication
from paperview import __app_name__, __description__, __version__
from paperview.icons import get_app_icon
from paperview.main_window import MainWindow


def print_version() -> None:
    """Prints the application name and version string to stdout."""
    print(f"{__app_name__} {__version__}")


def print_help() -> None:
    """Prints the CLI help and usage information to stdout."""
    print(f"{__app_name__} {__version__} — {__description__}\n")
    print("Usage:")
    print("  paperview [OPTIONS] [PDF_FILE]\n")
    print("Options:")
    print("  -v, --version    Show application version and exit")
    print("  -h, --help       Show this help message and exit\n")
    print("Arguments:")
    print("  PDF_FILE         Optional path to a PDF file to open on startup")


def _check_platform_plugins() -> None:
    """Verifies that Qt platform plugins are discoverable; logs diagnostic if missing."""
    try:
        from PySide6.QtCore import QLibraryInfo
        plugins_dir = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
        platforms_dir = plugins_dir / "platforms"
        if not platforms_dir.is_dir():
            sys.stderr.write(
                f"[PaperView Warning] Qt platform plugins directory not found at: {platforms_dir}\n"
                f"If the application fails to start, ensure Qt platform plugins (libqwayland.so, libqxcb.so) "
                f"are installed or configure QT_QPA_PLATFORM_PLUGIN_PATH.\n"
            )
    except Exception:
        pass


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main application entry point.
    Returns exit code (0 for success).
    """
    args = argv if argv is not None else sys.argv[1:]

    # Fast-path CLI flags that do not require GUI initialization
    if any(arg in ("-v", "--version") for arg in args):
        print_version()
        return 0

    if any(arg in ("-h", "--help") for arg in args):
        print_help()
        return 0

    # Extract target file path (first positional argument not starting with '-')
    initial_file: Optional[str] = None
    for arg in args:
        if not arg.startswith("-"):
            initial_file = arg
            break

    _check_platform_plugins()

    try:
        app = QApplication(sys.argv)
    except Exception as e:
        sys.stderr.write(
            f"[PaperView Error] Failed to initialize Qt GUI subsystem:\n{e}\n"
            f"Ensure a display server (Wayland or X11) is active and Qt platform plugins are installed.\n"
        )
        return 1

    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__app_name__)
    app.setOrganizationDomain("paperview.org")
    app.setWindowIcon(get_app_icon())

    window = MainWindow(initial_file=initial_file)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

