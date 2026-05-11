"""Shared widgets — the top tab strip and the icon-only bottom action bar."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QToolButton


class _TopTabButton(QToolButton):
    """Top-tab button: icon over short text, with an active-state underline."""

    def __init__(self, text: str, icon: QIcon, parent=None) -> None:
        super().__init__(parent)
        self.setText(text)
        self.setIcon(icon)
        self.setIconSize(QSize(20, 20))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setProperty("topTab", True)
        self.setProperty("active", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Enough room for both the icon and the text descender ("g" in
        # "Settings"); without this 20 + 14 pt easily clips on the
        # default style.
        self.setMinimumHeight(54)

    def set_active(self, active: bool) -> None:
        if bool(self.property("active")) == active:
            return
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class _BottomTabButton(QToolButton):
    """Bottom-bar button: icon-only with a tooltip."""

    def __init__(self, tooltip: str, icon: QIcon, parent=None) -> None:
        super().__init__(parent)
        self.setIcon(icon)
        self.setIconSize(QSize(22, 22))
        self.setToolTip(tooltip)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setProperty("bottomTab", True)
        self.setProperty("active", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMinimumHeight(40)

    def set_active(self, active: bool) -> None:
        if bool(self.property("active")) == active:
            return
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class TabStrip(QFrame):
    """Top tab strip (Reader / Create / Settings)."""

    selected = pyqtSignal(str)

    HEIGHT = 56

    def __init__(self, items: list[tuple[str, QIcon]], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(self.HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._buttons: dict[str, _TopTabButton] = {}
        for name, icon in items:
            btn = _TopTabButton(name, icon)
            btn.clicked.connect(lambda _=False, n=name: self.set_active(n))
            layout.addWidget(btn, 1)
            self._buttons[name] = btn

    def set_active(self, name: str) -> None:
        for n, btn in self._buttons.items():
            btn.set_active(n == name)
        self.selected.emit(name)


class BottomBar(QFrame):
    """Bottom action strip — icons only, with tooltips."""

    clicked_action = pyqtSignal(str)

    HEIGHT = 46

    def __init__(self, items: list[tuple[str, QIcon, str]], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(self.HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._buttons: dict[str, _BottomTabButton] = {}
        for tooltip, icon, key in items:
            btn = _BottomTabButton(tooltip, icon)
            btn.clicked.connect(lambda _=False, k=key: self.clicked_action.emit(k))
            layout.addWidget(btn, 1)
            self._buttons[key] = btn

    def set_active(self, key: str | None) -> None:
        for k, btn in self._buttons.items():
            btn.set_active(k == key)
