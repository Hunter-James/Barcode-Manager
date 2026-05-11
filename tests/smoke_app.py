"""Boot the app, render the main window for one event loop iteration, exit."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from ui import MainWindow


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    QTimer.singleShot(1500, app.quit)
    rc = app.exec()
    print(f"app exited cleanly with rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
