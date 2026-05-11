"""Screen snipping via the Windows built-in Snipping Tool.

Launching the `ms-screenclip:` URI scheme triggers the same rectangle
selector that Win+Shift+S uses. It handles arbitrary numbers of monitors
and DPI scaling correctly because it is part of Windows itself — we just
listen for the resulting image on the clipboard.
"""

from __future__ import annotations

import os

import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication


def qimage_to_ndarray(qimg: QImage) -> np.ndarray:
    """QImage -> BGR uint8 numpy array."""
    fmt = qimg.convertToFormat(QImage.Format.Format_RGB888)
    w, h = fmt.width(), fmt.height()
    bpl = fmt.bytesPerLine()
    ptr = fmt.constBits()
    ptr.setsize(fmt.sizeInBytes())
    raw = np.frombuffer(ptr, dtype=np.uint8).reshape(h, bpl)
    rgb = raw[:, : w * 3].reshape(h, w, 3).copy()
    return rgb[:, :, ::-1]  # RGB -> BGR


class WindowsSnipper(QObject):
    """One-shot snip using the Windows Snipping Tool.

    Emits :attr:`captured` with a BGR numpy array when the user finishes
    the selection, or :attr:`cancelled` if the user dismisses the
    snipper without capturing anything (timeout-based).
    """

    captured = pyqtSignal(np.ndarray)
    cancelled = pyqtSignal()

    TIMEOUT_SEC = 60

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cb = QApplication.clipboard()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._active = False
        self._cb.dataChanged.connect(self._on_clipboard_change)

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        try:
            # The ms-screenclip URI opens the same rectangle picker as
            # Win+Shift+S and copies the result to the clipboard.
            os.startfile("ms-screenclip:")
        except OSError:
            self._active = False
            self.cancelled.emit()
            return
        self._timer.start(self.TIMEOUT_SEC * 1000)

    def _on_clipboard_change(self) -> None:
        if not self._active:
            return
        mime = self._cb.mimeData()
        if mime is None or not mime.hasImage():
            return
        qimg = self._cb.image()
        if qimg is None or qimg.isNull():
            return
        self._active = False
        self._timer.stop()
        arr = qimage_to_ndarray(qimg)
        self.captured.emit(arr)

    def _on_timeout(self) -> None:
        if not self._active:
            return
        self._active = False
        self.cancelled.emit()
