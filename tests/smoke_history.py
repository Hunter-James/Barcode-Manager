"""Boot the app, pre-populate history, navigate to it, screenshot-style render."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


def main() -> int:
    from storage import HistoryEntry, HistoryStore
    from ui import MainWindow

    # Use a temp history file so we don't trash the user's real one.
    tmp = Path(tempfile.mkdtemp()) / "history.json"
    store = HistoryStore(path=tmp)
    for txt, fmt in [
        ("01046009050002402151NTzMa93w...", "Data Matrix"),
        ("01046009050002402152aDl0938Fpp", "Data Matrix"),
        ("https://example.com/test", "QR Code"),
        ("5901234123457", "EAN-13"),
    ]:
        store.add(HistoryEntry(text=txt, format=fmt, source="file", engine="test"))
        time.sleep(0.02)

    app = QApplication(sys.argv)
    win = MainWindow()
    # swap in our pre-populated store
    win._store = store
    win._history._store = store
    win._history.refresh()
    win.show()

    def open_history():
        win._goto_history()
        QTimer.singleShot(800, app.quit)

    QTimer.singleShot(500, open_history)
    rc = app.exec()
    print(f"smoke_history rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
