"""History tab — list of past scans/generations."""

from __future__ import annotations

import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storage import HistoryEntry, HistoryStore


class HistoryView(QWidget):
    cleared = pyqtSignal()

    def __init__(self, store: HistoryStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("History")
        title.setStyleSheet("font-size: 14pt; font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch(1)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear)
        title_row.addWidget(clear)
        outer.addLayout(title_row)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context)
        self._list.itemDoubleClicked.connect(self._copy_selected)
        outer.addWidget(self._list, 1)

        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        for e in self._store.all():
            self._list.addItem(self._make_item(e))

    def _make_item(self, e: HistoryEntry) -> QListWidgetItem:
        when = datetime.datetime.fromtimestamp(e.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        snippet = e.text if len(e.text) <= 80 else e.text[:77] + "..."
        label = f"[{e.format}] {snippet}\n{when} • via {e.source}"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, e.text)
        return item

    def add(self, _entry: HistoryEntry) -> None:
        # store has already taken care of it; just refresh
        self.refresh()

    def _clear(self) -> None:
        self._store.clear()
        self.refresh()
        self.cleared.emit()

    def _on_context(self, pos) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        copy_act = QAction("Copy text", self)
        copy_act.triggered.connect(lambda: self._copy_selected(item))
        menu.addAction(copy_act)
        menu.exec(self._list.mapToGlobal(pos))

    def _copy_selected(self, item: QListWidgetItem) -> None:
        text = item.data(Qt.ItemDataRole.UserRole) or ""
        QApplication.clipboard().setText(text)
