"""
EXR Channel Recombiner — Main Entry Point

Run this to start the GUI application.
"""

import sys
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.oiio import OiioAdapter


def main():
    """Launch the application."""
    # Verify OIIO
    oiio_version = OiioAdapter.get_oiio_version()
    print(f"OpenImageIO version: {oiio_version}")

    # Create Qt application
    app = QApplication(sys.argv)

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
