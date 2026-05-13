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
from storage import HistoryEntry, HistoryStore, snapshots_dir

from .icons import chevron_icon, close_icon, filter_icon, more_icon, search_icon
from .text_util import display_text, inline_text


class _ClickableFrame(QFrame):
    """QFrame that emits ``clicked`` on left mouse press anywhere on it.

    Used for the History group header so clicking the whole bar toggles
    the group (not just the small chevron button on the left)."""

    clicked = pyqtSignal()

    def mousePressEvent(self, e):  # type: ignore[override]
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


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
    def __init__(
        self,
        entry: HistoryEntry,
        thumb: QPixmap,
        in_group: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HistoryItemGrouped" if in_group else "HistoryItem")
        self._entry = entry

        layout = QHBoxLayout(self)
        # Slightly larger left padding for grouped items keeps the
        # accent border from overlapping the thumbnail.
        layout.setContentsMargins(14 if not in_group else 11, 10, 14, 10)
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

        flat = inline_text(entry.text)
        snippet = flat if len(flat) <= 36 else flat[:33] + "..."
        title = QLabel(snippet)
        title.setObjectName("HistoryItemTitle")
        # Tooltip keeps the multi-line view so the full payload structure
        # is visible on hover.
        title.setToolTip(display_text(entry.text))
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
        # Copy the raw payload, FNC1 and all, so it can be pasted into a
        # strict-format consumer (e.g. a database lookup).
        QApplication.clipboard().setText(self._entry.text)

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        copy_act = QAction("Copy text", self)
        copy_act.triggered.connect(
            lambda: QApplication.clipboard().setText(self._entry.text)
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
        # group_id -> expanded? Default True so the most recent scan
        # arrives unfolded; the user collapses what they don't want
        # to keep occupying screen real estate.
        self._expanded: dict[str, bool] = {}

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

        # Multi-code scans share a non-empty group_id and were inserted
        # consecutively, so we just collect runs of equal group_id.
        i = 0
        while i < len(entries):
            e = entries[i]
            if e.group_id:
                j = i + 1
                while j < len(entries) and entries[j].group_id == e.group_id:
                    j += 1
                self._append_group(entries[i:j])
                i = j
            else:
                self._append_item(e, in_group=False)
                i += 1

    def _append_item(self, entry: HistoryEntry, *, in_group: bool) -> None:
        thumb = self._get_thumb(entry.text, entry.format)
        item = _HistoryItemWidget(entry, thumb, in_group=in_group)
        self._container_layout.insertWidget(self._container_layout.count() - 1, item)

    def _append_group(self, group: list[HistoryEntry]) -> None:
        gid = group[0].group_id
        expanded = self._expanded.setdefault(gid, True)

        when = datetime.datetime.fromtimestamp(group[0].timestamp).strftime(
            "%d.%m.%Y %H:%M:%S"
        )

        header = _ClickableFrame()
        header.setObjectName("HistoryGroupHeader")
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.clicked.connect(lambda g=gid: self._toggle_group(g))
        h = QHBoxLayout(header)
        h.setContentsMargins(8, 6, 14, 6)
        h.setSpacing(6)

        chevron = QToolButton()
        chevron.setObjectName("HistoryGroupChevron")
        chevron.setIcon(chevron_icon("down" if expanded else "right", size=18, color="#1A8FE3"))
        chevron.setIconSize(QSize(14, 14))
        chevron.setCursor(Qt.CursorShape.PointingHandCursor)
        chevron.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        chevron.setFixedSize(QSize(22, 22))
        chevron.clicked.connect(lambda _=False, g=gid: self._toggle_group(g))
        h.addWidget(chevron)

        title = QLabel(f"{len(group)} codes scanned together")
        title.setObjectName("HistoryGroupHeaderLabel")
        h.addWidget(title)
        h.addStretch(1)
        time_label = QLabel(when)
        time_label.setObjectName("HistoryGroupHeaderTime")
        h.addWidget(time_label)

        self._container_layout.insertWidget(self._container_layout.count() - 1, header)
        if not expanded:
            return

        # Snapshot — the captured area with green polygons and red
        # number badges, exactly as the user saw it in the preview.
        snap_path = snapshots_dir() / f"{gid}.png"
        if snap_path.exists():
            snap_pm = QPixmap(str(snap_path))
            if not snap_pm.isNull():
                wrap = QFrame()
                wrap.setObjectName("HistoryGroupSnapshot")
                wl = QHBoxLayout(wrap)
                wl.setContentsMargins(11, 4, 14, 8)
                snap_label = QLabel()
                snap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # Match the container's width budget — items have ~340 usable.
                target_w = 340
                if snap_pm.width() > target_w:
                    snap_pm = snap_pm.scaledToWidth(
                        target_w, Qt.TransformationMode.SmoothTransformation
                    )
                snap_label.setPixmap(snap_pm)
                wl.addWidget(snap_label)
                self._container_layout.insertWidget(
                    self._container_layout.count() - 1, wrap
                )

        for entry in group:
            self._append_item(entry, in_group=True)

    def _toggle_group(self, group_id: str) -> None:
        self._expanded[group_id] = not self._expanded.get(group_id, True)
        self.refresh()

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
