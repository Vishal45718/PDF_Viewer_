"""
PaperView Entry Point.
Launches the PySide6 Qt application.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from paperview.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PaperView")
    app.setOrganizationName("PaperView")

    # Optional file argument from command line
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None

    window = MainWindow(initial_file=initial_file)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
