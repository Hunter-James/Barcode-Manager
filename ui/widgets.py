"""Small shared widgets — top tab strip, bottom tab strip."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QVBoxLayout


class TabButton(QToolButton):
    def __init__(
        self,
        text: str,
        icon: QIcon,
        bottom: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setIcon(icon)
        self.setIconSize(QSize(22 if bottom else 24, 22 if bottom else 24))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setProperty("topTab" if not bottom else "bottomTab", True)
        self.setProperty("active", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_active(self, active: bool) -> None:
        if bool(self.property("active")) == active:
            return
        self.setProperty("active", active)
        # re-apply stylesheet so the dynamic property takes effect
        self.style().unpolish(self)
        self.style().polish(self)


class TabStrip(QFrame):
    """Top tab strip (Reader / Create / Settings)."""

    selected = pyqtSignal(str)

    def __init__(self, items: list[tuple[str, QIcon]], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(60)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._buttons: dict[str, TabButton] = {}
        for name, icon in items:
            btn = TabButton(name, icon, bottom=False)
            btn.clicked.connect(lambda _=False, n=name: self.set_active(n))
            layout.addWidget(btn, 1)
            self._buttons[name] = btn

    def set_active(self, name: str) -> None:
        for n, btn in self._buttons.items():
            btn.set_active(n == name)
        self.selected.emit(name)


class BottomBar(QFrame):
    """Bottom action strip (Screen Snip / File / Camera / History / More)."""

    clicked_action = pyqtSignal(str)

    def __init__(
        self,
        items: list[tuple[str, QIcon, str]],  # (display_text, icon, action_key)
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)
        self._buttons: dict[str, TabButton] = {}
        for text, icon, key in items:
            btn = TabButton(text, icon, bottom=True)
            btn.clicked.connect(lambda _=False, k=key: self.clicked_action.emit(k))
            layout.addWidget(btn, 1)
            self._buttons[key] = btn

    def set_active(self, key: str | None) -> None:
        for k, btn in self._buttons.items():
            btn.set_active(k == key)
