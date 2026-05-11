"""Application stylesheet — mirrors the look of Barcode Manager for Windows."""

ACCENT = "#1A8FE3"
ACCENT_DARK = "#1572B6"
BG = "#1F1F1F"
BG_PANEL = "#2A2A2A"
BG_HEADER = "#2A2A2A"
BG_READER = "#1A6FB5"  # the blue Reader area
TEXT = "#FFFFFF"
TEXT_DIM = "#B8B8B8"
SEPARATOR = "#3A3A3A"

QSS = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', 'Segoe UI Variable', sans-serif;
    font-size: 10pt;
}}

QFrame#TopBar {{
    background-color: {BG_HEADER};
    border-bottom: 1px solid {SEPARATOR};
}}

QToolButton[topTab="true"] {{
    background: transparent;
    color: {TEXT_DIM};
    border: none;
    padding: 10px 18px;
    font-size: 10pt;
}}
QToolButton[topTab="true"]:hover {{
    color: {TEXT};
}}
QToolButton[topTab="true"][active="true"] {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

QFrame#BottomBar {{
    background-color: {BG_HEADER};
    border-top: 1px solid {SEPARATOR};
}}

QToolButton[bottomTab="true"] {{
    background: transparent;
    color: {TEXT_DIM};
    border: none;
    padding: 8px 4px;
    font-size: 8.5pt;
}}
QToolButton[bottomTab="true"]:hover {{
    color: {TEXT};
}}
QToolButton[bottomTab="true"][active="true"] {{
    color: {ACCENT};
}}

QFrame#ReaderArea {{
    background-color: {BG_READER};
}}

QPushButton#PrimaryButton {{
    background: transparent;
    border: 2px solid white;
    border-radius: 24px;
    color: white;
    padding: 10px 28px;
    font-size: 11pt;
    font-weight: 600;
    letter-spacing: 1px;
}}
QPushButton#PrimaryButton:hover {{
    background-color: rgba(255, 255, 255, 0.10);
}}
QPushButton#PrimaryButton:pressed {{
    background-color: rgba(255, 255, 255, 0.18);
}}

QLabel#VersionLabel {{
    color: rgba(255, 255, 255, 0.65);
    font-size: 8.5pt;
}}

QPushButton {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 4px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    background-color: #3A3A3A;
}}
QPushButton:pressed {{
    background-color: {ACCENT_DARK};
}}
QPushButton#AccentButton {{
    background-color: {ACCENT};
    color: white;
    border: 1px solid {ACCENT};
}}
QPushButton#AccentButton:hover {{
    background-color: {ACCENT_DARK};
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 4px;
    padding: 6px;
    selection-background-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; }}

QLabel#StatusBanner {{
    background-color: {ACCENT};
    color: white;
    padding: 10px;
    font-size: 11pt;
    font-weight: 600;
}}
QLabel#StatusBannerError {{
    background-color: #C04040;
    color: white;
    padding: 10px;
    font-size: 11pt;
    font-weight: 600;
}}
QLabel#StatusSubtle {{
    color: rgba(255,255,255,0.75);
    background-color: {ACCENT};
    padding: 0 0 8px 0;
    font-size: 9pt;
}}

QListWidget {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 4px;
}}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid {SEPARATOR}; }}
QListWidget::item:selected {{ background-color: {ACCENT_DARK}; color: white; }}

QScrollBar:vertical {{
    background: {BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #4A4A4A;
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: #5A5A5A; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {SEPARATOR};
    border-radius: 3px;
    background: {BG_PANEL};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QMenu {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
}}
QMenu::item:selected {{ background-color: {ACCENT}; }}

QToolTip {{
    background-color: #1A1A1A;
    color: white;
    border: 1px solid {SEPARATOR};
    padding: 4px;
}}
"""
