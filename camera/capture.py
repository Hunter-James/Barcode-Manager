"""Webcam capture thread.

Each frame is delivered as a BGR numpy array via the `frame_ready` signal,
plus a periodic `decode_request` signal so the Reader can run decoding off
the GUI thread without saturating it.
"""

from __future__ import annotations

import time

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal


def list_cameras(max_index: int = 4) -> list[int]:
    """Probe the first few indices and return ones that opened successfully."""
    found: list[int] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok = cap.isOpened()
        cap.release()
        if ok:
            found.append(i)
    return found


class CameraWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    decode_request = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)

    def __init__(self, index: int = 0, decode_every_ms: int = 250, parent=None) -> None:
        super().__init__(parent)
        self._index = index
        self._stop = False
        self._decode_every = decode_every_ms / 1000.0
        self._last_decode = 0.0

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        cap = cv2.VideoCapture(self._index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.error.emit(f"Camera #{self._index} could not be opened")
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        try:
            while not self._stop:
                ok, frame = cap.read()
                if not ok or frame is None:
                    self.msleep(20)
                    continue
                self.frame_ready.emit(frame)
                now = time.monotonic()
                if now - self._last_decode >= self._decode_every:
                    self._last_decode = now
                    self.decode_request.emit(frame.copy())
                self.msleep(15)
        finally:
            cap.release()
