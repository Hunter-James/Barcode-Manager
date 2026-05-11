"""Vector icons drawn with QPainter — no external asset files needed."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _make(size: int, draw: Callable[[QPainter, int], None]) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    draw(p, size)
    p.end()
    return QIcon(pm)


def _stroke(p: QPainter, color: str, width: float) -> None:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)


def reader_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Scanner viewfinder (corners + horizontal scanning line)."""

    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.4, s / 16))
        m = s * 0.18
        corner = s * 0.22
        # top-left
        p.drawLine(QPointF(m, m + corner), QPointF(m, m))
        p.drawLine(QPointF(m, m), QPointF(m + corner, m))
        # top-right
        p.drawLine(QPointF(s - m - corner, m), QPointF(s - m, m))
        p.drawLine(QPointF(s - m, m), QPointF(s - m, m + corner))
        # bottom-left
        p.drawLine(QPointF(m, s - m - corner), QPointF(m, s - m))
        p.drawLine(QPointF(m, s - m), QPointF(m + corner, s - m))
        # bottom-right
        p.drawLine(QPointF(s - m - corner, s - m), QPointF(s - m, s - m))
        p.drawLine(QPointF(s - m, s - m), QPointF(s - m, s - m - corner))
        # scan line
        p.drawLine(QPointF(m + 2, s / 2), QPointF(s - m - 2, s / 2))

    return _make(size, draw)


def create_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Barcode: vertical bars."""

    def draw(p: QPainter, s: int) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        widths = [2, 1, 3, 1, 2, 1, 1, 2, 1, 3, 1, 2]
        margin = s * 0.18
        usable = s - 2 * margin
        total = sum(widths) * 2  # bars + gaps
        unit = usable / total
        x = margin
        for w in widths:
            p.drawRect(QRectF(x, margin, w * unit, s - 2 * margin))
            x += (w + 1) * unit

    return _make(size, draw)


def settings_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Gear icon."""

    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.4, s / 16))
        c = s / 2
        outer = s * 0.36
        inner = s * 0.18
        tooth = s * 0.08
        path = QPainterPath()
        import math

        teeth = 8
        for i in range(teeth * 2):
            ang = i * math.pi / teeth
            r = outer + (tooth if i % 2 == 0 else 0)
            x = c + r * math.cos(ang)
            y = c + r * math.sin(ang)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        p.drawPath(path)
        p.drawEllipse(QPointF(c, c), inner, inner)

    return _make(size, draw)


def snip_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Rounded rectangle with a small plus, like the big screen-snip art."""

    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.4, s / 14))
        m = s * 0.18
        r = s * 0.14
        rect = QRectF(m, m, s - 2 * m, s - 2 * m)
        p.drawRoundedRect(rect, r, r)
        # plus on bottom-right
        cx, cy = s - m, s - m
        arm = s * 0.10
        p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
        p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))

    return _make(size, draw)


def file_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Picture / file icon: framed image with sun + mountain."""

    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.4, s / 16))
        m = s * 0.18
        r = s * 0.06
        rect = QRectF(m, m, s - 2 * m, s - 2 * m)
        p.drawRoundedRect(rect, r, r)
        # sun
        p.drawEllipse(QPointF(m + (s - 2 * m) * 0.28, m + (s - 2 * m) * 0.30), s * 0.05, s * 0.05)
        # mountain
        path = QPainterPath()
        path.moveTo(m + (s - 2 * m) * 0.10, s - m - 2)
        path.lineTo(m + (s - 2 * m) * 0.42, m + (s - 2 * m) * 0.45)
        path.lineTo(m + (s - 2 * m) * 0.70, m + (s - 2 * m) * 0.75)
        path.lineTo(m + (s - 2 * m) * 0.90, s - m - 2)
        p.drawPath(path)

    return _make(size, draw)


def camera_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Camera body + lens."""

    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.4, s / 16))
        m = s * 0.16
        body = QRectF(m, m + s * 0.10, s - 2 * m, s - 2 * m - s * 0.10)
        r = s * 0.06
        p.drawRoundedRect(body, r, r)
        # bump
        bump = QRectF(m + s * 0.18, m + s * 0.04, s * 0.22, s * 0.10)
        p.drawRoundedRect(bump, s * 0.02, s * 0.02)
        # lens
        p.drawEllipse(QPointF(s / 2, s / 2 + s * 0.06), s * 0.14, s * 0.14)

    return _make(size, draw)


def history_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Three horizontal lines."""

    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.6, s / 14))
        m = s * 0.20
        gap = (s - 2 * m) / 4
        p.drawLine(QPointF(m, m + gap), QPointF(s - m, m + gap))
        p.drawLine(QPointF(m, m + 2 * gap), QPointF(s - m, m + 2 * gap))
        p.drawLine(QPointF(m, m + 3 * gap), QPointF(s - m, m + 3 * gap))

    return _make(size, draw)


def more_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Horizontal three-dot 'more' icon."""

    def draw(p: QPainter, s: int) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        r = s * 0.06
        for i, fx in enumerate((0.30, 0.50, 0.70)):
            p.drawEllipse(QPointF(s * fx, s * 0.50), r, r)

    return _make(size, draw)


def search_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Magnifying glass."""

    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.5, s / 14))
        cx, cy = s * 0.42, s * 0.42
        r = s * 0.22
        p.drawEllipse(QPointF(cx, cy), r, r)
        import math
        hx = cx + r * math.cos(math.pi / 4)
        hy = cy + r * math.sin(math.pi / 4)
        p.drawLine(QPointF(hx, hy), QPointF(s - s * 0.18, s - s * 0.18))

    return _make(size, draw)


def filter_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    """Funnel."""

    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.5, s / 14))
        m = s * 0.22
        path = QPainterPath()
        path.moveTo(m, m)
        path.lineTo(s - m, m)
        path.lineTo(s * 0.58, s * 0.50)
        path.lineTo(s * 0.58, s - m * 0.7)
        path.lineTo(s * 0.42, s - m * 0.4)
        path.lineTo(s * 0.42, s * 0.50)
        path.closeSubpath()
        p.drawPath(path)

    return _make(size, draw)


def close_icon(size: int = 32, color: str = "#FFFFFF") -> QIcon:
    def draw(p: QPainter, s: int) -> None:
        _stroke(p, color, max(1.6, s / 12))
        m = s * 0.28
        p.drawLine(QPointF(m, m), QPointF(s - m, s - m))
        p.drawLine(QPointF(s - m, m), QPointF(m, s - m))

    return _make(size, draw)


def app_icon(size: int = 64) -> QIcon:
    """Simple square 'BM' app icon."""

    def draw(p: QPainter, s: int) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1A8FE3"))
        p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.18, s * 0.18)
        _stroke(p, "#FFFFFF", max(2, s / 10))
        m = s * 0.22
        corner = s * 0.18
        # corner brackets like reader icon
        p.drawLine(QPointF(m, m + corner), QPointF(m, m))
        p.drawLine(QPointF(m, m), QPointF(m + corner, m))
        p.drawLine(QPointF(s - m - corner, m), QPointF(s - m, m))
        p.drawLine(QPointF(s - m, m), QPointF(s - m, m + corner))
        p.drawLine(QPointF(m, s - m - corner), QPointF(m, s - m))
        p.drawLine(QPointF(m, s - m), QPointF(m + corner, s - m))
        p.drawLine(QPointF(s - m - corner, s - m), QPointF(s - m, s - m))
        p.drawLine(QPointF(s - m, s - m), QPointF(s - m, s - m - corner))
        p.drawLine(QPointF(s * 0.32, s / 2), QPointF(s * 0.68, s / 2))

    return _make(size, draw)
