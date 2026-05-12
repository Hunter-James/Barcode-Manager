"""Main window — top tab strip, central stacked widget, bottom action bar."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from storage import HistoryEntry, HistoryStore

from .create_tab import CreateTab
from .history_view import HistoryView
from .icons import (
    app_icon,
    camera_icon,
    create_icon,
    file_icon,
    history_icon,
    more_icon,
    reader_icon,
    settings_icon,
    snip_icon,
)
from .reader_tab import ReaderTab
from .settings_tab import SettingsTab
from .style import QSS
from .widgets import BottomBar, TabStrip


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Barcode Manager")
        self.setWindowIcon(app_icon(64))
        self.setFixedSize(QSize(380, 640))
        # Disable maximize button on the title bar
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowMaximizeButtonHint
        self.setWindowFlags(flags)
        self.setStyleSheet(QSS)

        self._store = HistoryStore()

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # Top tabs
        self._top = TabStrip(
            [
                ("Reader", reader_icon(32)),
                ("Create", create_icon(32)),
                ("Settings", settings_icon(32)),
            ]
        )
        self._top.selected.connect(self._on_top_selected)
        v.addWidget(self._top)

        # Central stack
        self._stack = QStackedWidget()
        self._reader = ReaderTab(history_add=self._store.add)
        self._create = CreateTab(history_add=self._store.add)
        self._settings = SettingsTab(on_clear_history=self._clear_history)
        self._history = HistoryView(self._store)
        self._reader.result_decoded.connect(self._history.add)
        self._history.closed.connect(self._close_history)
        self._create_idx = self._stack.addWidget(self._reader)  # 0
        self._stack.addWidget(self._create)   # 1
        self._stack.addWidget(self._settings) # 2
        self._stack.addWidget(self._history)  # 3
        v.addWidget(self._stack, 1)

        # Bottom bar — icons only, tooltips on hover
        self._bottom = BottomBar(
            [
                ("Screen Snip", snip_icon(32), "snip"),
                ("File", file_icon(32), "file"),
                ("Camera", camera_icon(32), "camera"),
                ("History", history_icon(32), "history"),
                ("More", more_icon(32), "more"),
            ]
        )
        self._bottom.clicked_action.connect(self._on_bottom_action)
        v.addWidget(self._bottom)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._reader.open_file)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self._reader.start_snip)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self._goto_history)
        QShortcut(QKeySequence("Escape"), self, activated=self._reader.reset)

        self._top.set_active("Reader")

    # ----- routing -----
    def _on_top_selected(self, name: str) -> None:
        self._top.setVisible(True)
        if name == "Reader":
            self._stack.setCurrentWidget(self._reader)
        elif name == "Create":
            self._reader.stop_camera()
            self._stack.setCurrentWidget(self._create)
        elif name == "Settings":
            self._reader.stop_camera()
            self._stack.setCurrentWidget(self._settings)
        self._bottom.set_active(None)

    def _on_bottom_action(self, key: str) -> None:
        if key != "history":
            self._top.setVisible(True)
        if key == "snip":
            self._top.set_active("Reader")
            self._stack.setCurrentWidget(self._reader)
            self._reader.start_snip()
            self._bottom.set_active("snip")
        elif key == "file":
            self._top.set_active("Reader")
            self._stack.setCurrentWidget(self._reader)
            self._reader.open_file()
            self._bottom.set_active("file")
        elif key == "camera":
            self._top.set_active("Reader")
            self._stack.setCurrentWidget(self._reader)
            self._reader.start_camera()
            self._bottom.set_active("camera")
        elif key == "history":
            self._goto_history()
        elif key == "more":
            self._show_more_menu()

    def _goto_history(self) -> None:
        self._reader.stop_camera()
        self._history.refresh()
        self._top.setVisible(False)
        self._stack.setCurrentWidget(self._history)
        self._bottom.set_active("history")

    def _close_history(self) -> None:
        self._top.setVisible(True)
        self._stack.setCurrentWidget(self._reader)
        self._top.set_active("Reader")
        self._bottom.set_active(None)

    def _show_more_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Paste from clipboard", self._paste_clipboard)
        menu.addAction("Clear history", self._clear_history)
        menu.addSeparator()
        menu.addAction("About", self._about)
        # Anchor to the rightmost bottom button
        btn = self._bottom.findChild(QToolButton)  # first button is fine for positioning fallback
        pos = self.mapToGlobal(self._bottom.geometry().bottomRight())
        menu.exec(pos)

    def _paste_clipboard(self) -> None:
        cb = QApplication.clipboard()
        mime = cb.mimeData()
        if mime.hasImage():
            from PyQt6.QtGui import QImage

            qimg = QImage(mime.imageData())
            if qimg.isNull():
                return
            qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
            import numpy as np

            w, h = qimg.width(), qimg.height()
            ptr = qimg.constBits()
            ptr.setsize(qimg.sizeInBytes())
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, qimg.bytesPerLine())[:, : w * 3]
            arr = arr.reshape(h, w, 3)
            import cv2
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            self._top.set_active("Reader")
            self._stack.setCurrentWidget(self._reader)
            self._reader.show_image(bgr, source="file")
        else:
            QMessageBox.information(self, "Paste", "Clipboard has no image.")

    def _clear_history(self) -> None:
        self._store.clear()
        self._history.refresh()

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About Barcode Manager",
            "Barcode Manager\n"
            "Version 1.0.0\n\n"
            "Multi-engine recognition with aggressive preprocessing.\n"
            "Powered by zxing-cpp, pyzbar, OpenCV, PyQt6.",
        )

    def closeEvent(self, e) -> None:
        self._reader.stop_camera()
        super().closeEvent(e)
