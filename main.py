"""Barcode Manager — desktop barcode / QR scanner for Windows.

Reads barcodes and QR codes from screen captures, image files, and live
camera. Uses zxing-cpp + pyzbar + OpenCV with an aggressive preprocessing
pipeline so it succeeds on the kind of phone-camera photo that stock
decoders give up on.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_project_on_path() -> None:
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))


def main() -> int:
    _ensure_project_on_path()
    # High-DPI is on by default in Qt6; just make sure pixmap upscaling looks ok.
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    from PyQt6.QtWidgets import QApplication
    from ui import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Barcode Manager")
    app.setOrganizationName("BarcodeManager")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
