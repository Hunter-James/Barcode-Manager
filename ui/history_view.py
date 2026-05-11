"""History view — full-page replacement with blue header and thumbnails."""

from __future__ import annotations

import datetime

import cv2
import numpy as np
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from decoder import canonical_format, encode
from storage import HistoryEntry, HistoryStore

from .icons import close_icon, filter_icon, more_icon, search_icon
from .text_util import display_text


def _ndarray_to_qpixmap(img: np.ndarray) -> QPixmap:
    if img.ndim == 2:
        h, w = img.shape
        qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
    else:
        h, w, _ = img.shape
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


THUMB_SIZE = 56


class _HistoryItemWidget(QFrame):
    def __init__(self, entry: HistoryEntry, thumb: QPixmap, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("HistoryItem")
        self._entry = entry

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        thumb_label = QLabel()
        thumb_label.setFixedSize(QSize(THUMB_SIZE, THUMB_SIZE))
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setPixmap(thumb)
        thumb_label.setStyleSheet(
            "background-color: white; border-radius: 2px; padding: 2px;"
        )
        layout.addWidget(thumb_label)

        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)

        clean = display_text(entry.text)
        snippet = clean if len(clean) <= 36 else clean[:33] + "..."
        title = QLabel(snippet)
        title.setObjectName("HistoryItemTitle")
        title.setToolTip(clean)
        info.addWidget(title)

        type_label = QLabel(f"Type: {canonical_format(entry.format)}")
        type_label.setObjectName("HistoryItemMeta")
        info.addWidget(type_label)

        when = datetime.datetime.fromtimestamp(entry.timestamp).strftime(
            "%d.%m.%Y %H:%M:%S"
        )
        time_label = QLabel(f"Scanned at: {when}")
        time_label.setObjectName("HistoryItemMeta")
        info.addWidget(time_label)

        layout.addLayout(info, 1)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseDoubleClickEvent(self, _e) -> None:
        QApplication.clipboard().setText(display_text(self._entry.text))

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        copy_act = QAction("Copy text", self)
        copy_act.triggered.connect(
            lambda: QApplication.clipboard().setText(display_text(self._entry.text))
        )
        menu.addAction(copy_act)
        menu.exec(e.globalPos())


class HistoryView(QWidget):
    closed = pyqtSignal()
    cleared = pyqtSignal()

    def __init__(self, store: HistoryStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self._thumb_cache: dict[tuple[str, str], QPixmap] = {}
        self._query = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())

        self._scroll = QScrollArea()
        self._scroll.setObjectName("HistoryScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setObjectName("HistoryContainer")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)
        self._container_layout.addStretch(1)

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll, 1)

        self.refresh()

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HistoryHeader")
        header.setFixedHeight(54)
        h = QHBoxLayout(header)
        h.setContentsMargins(6, 0, 6, 0)
        h.setSpacing(4)

        self._close_btn = self._make_header_btn(close_icon(28), self.closed.emit)
        h.addWidget(self._close_btn)

        title = QLabel("History")
        title.setObjectName("HistoryTitle")
        h.addWidget(title)
        h.addStretch(1)

        for icon, slot in (
            (search_icon(28), self._noop),
            (filter_icon(28), self._noop),
            (more_icon(28), self._show_menu),
        ):
            btn = self._make_header_btn(icon, slot)
            h.addWidget(btn)

        return header

    @staticmethod
    def _make_header_btn(icon, slot) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("HistoryHeaderBtn")
        btn.setIcon(icon)
        btn.setIconSize(QSize(20, 20))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(QSize(40, 40))
        btn.setAutoRaise(False)  # let QSS style hover/pressed states
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.clicked.connect(slot)
        return btn

    def _noop(self) -> None:
        pass

    def _show_menu(self) -> None:
        menu = QMenu(self)
        clear_act = QAction("Clear history", self)
        clear_act.triggered.connect(self._clear)
        menu.addAction(clear_act)
        menu.exec(self._close_btn.parentWidget().mapToGlobal(
            self._close_btn.parentWidget().rect().bottomRight()
        ))

    def refresh(self) -> None:
        # remove existing items (everything except the trailing stretch).
        # setParent(None) detaches immediately from the rendering tree —
        # deleteLater alone would leave the old widgets visible until the
        # next event-loop tick, producing overlapping rows on a snapshot
        # or a fast successive refresh.
        while self._container_layout.count() > 1:
            it = self._container_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        entries = self._store.all()
        if not entries:
            empty = QLabel("No items yet")
            empty.setObjectName("HistoryEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setContentsMargins(0, 40, 0, 0)
            self._container_layout.insertWidget(self._container_layout.count() - 1, empty)
            return

        for e in entries:
            thumb = self._get_thumb(e.text, e.format)
            item = _HistoryItemWidget(e, thumb)
            self._container_layout.insertWidget(self._container_layout.count() - 1, item)

    def _get_thumb(self, text: str, fmt: str) -> QPixmap:
        key = (text, fmt)
        cached = self._thumb_cache.get(key)
        if cached is not None:
            return cached
        pm: QPixmap | None = None
        try:
            img = encode(text, canonical_format(fmt), size=140)
            pm = _ndarray_to_qpixmap(img).scaled(
                THUMB_SIZE,
                THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        except Exception:
            pm = None
        if pm is None or pm.isNull():
            pm = QPixmap(THUMB_SIZE, THUMB_SIZE)
            pm.fill(QColor("#D0D0D0"))
        self._thumb_cache[key] = pm
        return pm

    def add(self, _entry: HistoryEntry) -> None:
        # store has already accepted it; rebuild the view
        self.refresh()

    def _clear(self) -> None:
        self._store.clear()
        self._thumb_cache.clear()
        self.refresh()
        self.cleared.emit()
