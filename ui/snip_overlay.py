"""Custom screen-snip overlay that captures the entire virtual desktop.

Uses :func:`PIL.ImageGrab.grab(all_screens=True)` to snapshot every connected
monitor in one image (Pillow uses the Win32 ``CreateDC("DISPLAY")`` /
``BitBlt`` path internally, so it handles multi-monitor layouts and mixed
DPI correctly), then shows a single frameless overlay spanning the whole
virtual desktop. The user drags a rectangle, the selection is cropped from
the cached snapshot and returned.

Notably, this does **not** touch the system clipboard — unlike the previous
``ms-screenclip:`` integration.
"""

from __future__ import annotations

import ctypes
from typing import Optional

import numpy as np
from PIL import ImageGrab
from PyQt6.QtCore import QObject, QPoint, QRect, Qt, QTimer, pyqtSignal

# Windows 10 2004+: SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)
# causes BitBlt-based screen captures (which PIL.ImageGrab uses) to
# treat the window as if it weren't there. We rely on this so that
# our own UI cannot leak into the user's snip — ``hide()`` alone is
# racy on systems where the DWM compositor hasn't repainted the
# region behind us by the time the grab happens.
_WDA_NONE = 0x00000000
_WDA_EXCLUDEFROMCAPTURE = 0x00000011


def _set_capture_exclusion(hwnd: int, excluded: bool) -> bool:
    if not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.SetWindowDisplayAffinity.restype = ctypes.c_int
        flag = _WDA_EXCLUDEFROMCAPTURE if excluded else _WDA_NONE
        return bool(user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), flag))
    except Exception:
        return False
from PyQt6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget


def _pil_to_qpixmap(pil_img) -> QPixmap:
    pil_img = pil_img.convert("RGB")
    w, h = pil_img.size
    data = pil_img.tobytes("raw", "RGB")
    qimg = QImage(data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def _pil_to_ndarray_bgr(pil_img) -> np.ndarray:
    pil_img = pil_img.convert("RGB")
    arr = np.array(pil_img)
    return arr[:, :, ::-1].copy()  # RGB -> BGR


class _SnipOverlay(QWidget):
    """Frameless full-virtual-desktop overlay handling the drag selection."""

    captured = pyqtSignal(np.ndarray)
    cancelled = pyqtSignal()

    def __init__(self, screenshot_pil, virt_rect: QRect) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._full_bgr = _pil_to_ndarray_bgr(screenshot_pil)
        self._pixmap = _pil_to_qpixmap(screenshot_pil)

        self.setGeometry(virt_rect)

        self._start: Optional[QPoint] = None
        self._end: Optional[QPoint] = None

    def paintEvent(self, _e: QPaintEvent) -> None:
        p = QPainter(self)
        p.drawPixmap(self.rect(), self._pixmap)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if self._start is None or self._end is None:
            return
        sel = QRect(self._start, self._end).normalized()
        if sel.isEmpty():
            return

        # Map widget-DIP rect to source pixmap-pixel rect so the bright
        # cutout aligns with the underlying screenshot.
        pw, ph = self._pixmap.width(), self._pixmap.height()
        ww, wh = max(1, self.width()), max(1, self.height())
        src = QRect(
            int(sel.x() * pw / ww),
            int(sel.y() * ph / wh),
            int(sel.width() * pw / ww),
            int(sel.height() * ph / wh),
        )
        p.drawPixmap(sel, self._pixmap, src)
        pen = QPen(QColor("#1A8FE3"))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(sel)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._start = e.position().toPoint()
            self._end = self._start
            self.update()
        elif e.button() == Qt.MouseButton.RightButton:
            self._emit_cancel()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._start is not None:
            self._end = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        self._end = e.position().toPoint()
        sel = QRect(self._start, self._end).normalized()
        self.hide()
        if sel.width() < 6 or sel.height() < 6:
            self._emit_cancel()
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        ww, wh = max(1, self.width()), max(1, self.height())
        x0 = max(0, int(sel.x() * pw / ww))
        y0 = max(0, int(sel.y() * ph / wh))
        x1 = min(pw, int((sel.x() + sel.width()) * pw / ww))
        y1 = min(ph, int((sel.y() + sel.height()) * ph / wh))
        crop = self._full_bgr[y0:y1, x0:x1].copy()
        self.captured.emit(crop)
        self.close()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self._emit_cancel()

    def _emit_cancel(self) -> None:
        self.cancelled.emit()
        self.close()


class ScreenSnipper(QObject):
    """High-level controller — briefly hides the main window, grabs the
    virtual desktop, shows the overlay, restores the window afterwards.

    The clipboard is never written to.
    """

    captured = pyqtSignal(np.ndarray)
    cancelled = pyqtSignal()

    HIDE_DELAY_MS = 180

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._overlay: _SnipOverlay | None = None
        self._app_window: QWidget | None = None

    def start(self, app_window: QWidget | None = None) -> None:
        self._app_window = app_window
        if app_window is not None:
            hwnd = int(app_window.winId())
            # Belt-and-suspenders: exclude from BitBlt capture *and*
            # hide the visible window. Exclusion guarantees the app
            # cannot leak into the screenshot even if DWM repaint
            # hasn't caught up; hide() is the visual cue that the
            # snip mode is active.
            _set_capture_exclusion(hwnd, True)
            if app_window.isVisible():
                app_window.hide()
            QApplication.processEvents()
        # Give the OS a moment to redraw the area behind the hidden window
        QTimer.singleShot(self.HIDE_DELAY_MS, self._do_grab)

    def _do_grab(self) -> None:
        try:
            pil_img = ImageGrab.grab(all_screens=True)
        except Exception:
            self._restore_window()
            self.cancelled.emit()
            return

        virt_rect = QRect()
        for screen in QGuiApplication.screens():
            virt_rect = virt_rect.united(screen.geometry())
        if virt_rect.isEmpty():
            primary = QGuiApplication.primaryScreen()
            if primary is not None:
                virt_rect = primary.geometry()

        self._overlay = _SnipOverlay(pil_img, virt_rect)
        self._overlay.captured.connect(self._on_captured)
        self._overlay.cancelled.connect(self._on_cancelled)
        self._overlay.show()
        self._overlay.raise_()
        self._overlay.activateWindow()
        self._overlay.setFocus()

    def _on_captured(self, arr: np.ndarray) -> None:
        self._restore_window()
        self.captured.emit(arr)

    def _on_cancelled(self) -> None:
        self._restore_window()
        self.cancelled.emit()

    def _restore_window(self) -> None:
        if self._app_window is None:
            return
        # Undo the capture exclusion before the user gets the app back —
        # otherwise the next snapshot tool (their OS Snip & Sketch,
        # OBS, etc.) would see a black rectangle where our window is.
        try:
            hwnd = int(self._app_window.winId())
            _set_capture_exclusion(hwnd, False)
        except Exception:
            pass
        self._app_window.show()
        self._app_window.raise_()
        self._app_window.activateWindow()
