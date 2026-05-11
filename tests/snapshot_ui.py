"""Render the main window in idle, preview, history and create modes to PNG.

Lets us eyeball the design without launching the GUI by hand.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

OUT = Path(__file__).parent / "snapshots"


def save(widget, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pm = widget.grab()
    pm.save(str(OUT / f"{name}.png"), "PNG")
    print(f"  -> {OUT / f'{name}.png'}")


def main():
    from decoder import encode
    from storage import HistoryEntry, HistoryStore
    from ui import MainWindow

    tmp = Path(tempfile.mkdtemp()) / "history.json"
    store = HistoryStore(path=tmp)
    for txt, fmt in [
        ("01046009050002402151NTzMa93wnfN", "Data Matrix"),
        ("01046009050002402152aDl0938Fpp", "Data Matrix"),
        ("https://example.com/test", "QR Code"),
        ("5901234123457", "EAN-13"),
    ]:
        store.add(HistoryEntry(text=txt, format=fmt, source="file", engine="test"))
        time.sleep(0.02)

    app = QApplication(sys.argv)
    win = MainWindow()
    win._store = store
    win._history._store = store
    win._history.refresh()
    win.show()
    app.processEvents()

    save(win, "idle")

    # Decode result preview
    qr = encode("https://example.com/test", "QR Code", size=400)
    win._reader.show_image(qr, source="file")
    # wait for worker thread to decode
    for _ in range(30):
        app.processEvents()
        time.sleep(0.05)
    save(win, "preview")

    win._reader.reset()
    app.processEvents()

    # History
    win._goto_history()
    app.processEvents()
    save(win, "history")

    win._close_history()
    win._top.set_active("Create")
    app.processEvents()
    save(win, "create")

    win._top.set_active("Settings")
    app.processEvents()
    save(win, "settings")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
