"""Full-screen overlay used by the 'Screen Snip' tool.

The overlay grabs the entire virtual desktop, dims it, and lets the user
drag a rectangular selection. On release it emits the selected pixels as
a numpy array (BGR).
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QScreen,
)
from PyQt6.QtWidgets import QWidget


def _grab_virtual_desktop() -> tuple[QPixmap, QRect]:
    """Stitch every screen into one pixmap covering the whole virtual desktop."""
    screens: list[QScreen] = QGuiApplication.screens()
    if not screens:
        primary = QGuiApplication.primaryScreen()
        pm = primary.grabWindow(0)
        return pm, primary.geometry()

    # Compute bounding rect in device-independent coordinates
    rect = QRect()
    for s in screens:
        rect = rect.united(s.geometry())

    composite = QPixmap(rect.size())
    composite.fill(Qt.GlobalColor.black)
    p = QPainter(composite)
    for s in screens:
        g = s.geometry()
        shot = s.grabWindow(0)
        target = QRect(g.topLeft() - rect.topLeft(), g.size())
        p.drawPixmap(target, shot)
    p.end()
    return composite, rect


def pixmap_to_ndarray(pm: QPixmap) -> np.ndarray:
    """QPixmap -> BGR numpy array."""
    img = pm.toImage().convertToFormat(img_format_rgba8888())
    w, h = img.width(), img.height()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4).copy()
    # RGBA -> BGR
    return arr[:, :, [2, 1, 0]]


def img_format_rgba8888():
    from PyQt6.QtGui import QImage

    return QImage.Format.Format_RGBA8888


class SnipOverlay(QWidget):
    captured = pyqtSignal(np.ndarray)
    cancelled = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._background, self._virtual_rect = _grab_virtual_desktop()
        self.setGeometry(self._virtual_rect)

        self._start: QPoint | None = None
        self._end: QPoint | None = None

    def paintEvent(self, _: QPaintEvent) -> None:
        p = QPainter(self)
        p.drawPixmap(0, 0, self._background)
        # dim overlay
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))

        if self._start and self._end:
            sel = QRect(self._start, self._end).normalized()
            if not sel.isEmpty():
                p.drawPixmap(sel, self._background, sel)
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
            self.cancelled.emit()
            self.close()
            return
        cropped = self._background.copy(sel)
        self.captured.emit(pixmap_to_ndarray(cropped))
        self.close()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
