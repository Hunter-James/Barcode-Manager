"""Render the Reader preview with three Data Matrix codes side by side
to verify the numbered badges line up with the banner list."""

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

from decoder import encode
from storage import HistoryStore
from ui import MainWindow

OUT = Path(__file__).parent / "snapshots"
OUT.mkdir(parents=True, exist_ok=True)


def make_three_dm_image() -> np.ndarray:
    """Three GS1-like Data Matrix codes laid out left-to-right with a
    little white margin around each — what a multi-pack shelf shot
    looks like."""
    payloads = [
        "0104600905000240215aDl0\x1d93Fpp1",
        "0104600905000240215bDl0\x1d93Fpp2",
        "0104600905000240215cDl0\x1d93Fpp3",
    ]
    cells = []
    for p in payloads:
        dm = encode(p, "Data Matrix", size=160)
        if dm.ndim == 2:
            dm = cv2.cvtColor(dm, cv2.COLOR_GRAY2BGR)
        # Pad with white around each so they don't run together
        padded = cv2.copyMakeBorder(dm, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cells.append(padded)
    canvas = cv2.hconcat(cells)
    return canvas


def main():
    tmp = Path(tempfile.mkdtemp()) / "history.json"
    store = HistoryStore(path=tmp)

    app = QApplication(sys.argv)
    win = MainWindow()
    win._store = store
    win._history._store = store
    # MainWindow bound the reader's history_add callback to the
    # default store at construction time — repoint it at our temp
    # store so the test doesn't write into %APPDATA%.
    win._reader._history_add = store.add
    win.show()
    app.processEvents()

    img = make_three_dm_image()
    win._reader.show_image(img, source="file")

    # Wait for the worker to finish so the banner + polygons settle.
    for _ in range(60):
        app.processEvents()
        time.sleep(0.05)

    out_path = OUT / "multicode.png"
    pm = win.grab()
    pm.save(str(out_path), "PNG")
    print(f"  -> {out_path}")

    # Now show what History looks like after a multi-code scan +
    # one standalone scan, so the group block is visible against a
    # plain item.
    win._reader.show_image(encode("standalone-payload", "QR Code", size=300), source="file")
    for _ in range(30):
        app.processEvents()
        time.sleep(0.05)
    win._goto_history()
    app.processEvents()
    hist_path = OUT / "multicode_history.png"
    win.grab().save(str(hist_path), "PNG")
    print(f"  -> {hist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
