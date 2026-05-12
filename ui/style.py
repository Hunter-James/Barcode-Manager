"""Application stylesheet — dark Windows-11-flavoured theme.

Key rule: do **not** apply ``background-color`` to ``QWidget`` globally —
that paints over every QLabel and ends up putting a dark square behind
the hero art and the version label. Backgrounds are set only on the
QMainWindow and on the few named containers that actually want one;
everything else stays transparent so the parent shows through.
"""

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
/* --- base palette ----------------------------------------------- */
QMainWindow {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', 'Segoe UI Variable', sans-serif;
    font-size: 9.5pt;
}}
QWidget {{
    color: {TEXT};
    font-family: 'Segoe UI', 'Segoe UI Variable', sans-serif;
    font-size: 9.5pt;
}}
QStackedWidget {{ background-color: {BG}; }}
QLabel {{ background-color: transparent; }}

/* --- top tab strip --------------------------------------------- */
QFrame#TopBar {{
    background-color: {BG_HEADER};
    border: none;
}}
QToolButton[topTab="true"] {{
    background: transparent;
    color: {TEXT_DIM};
    border: none;
    padding: 4px 4px 4px 4px;
    font-size: 9pt;
}}
QToolButton[topTab="true"]:hover {{ color: {TEXT}; }}
QToolButton[topTab="true"][active="true"] {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

/* --- bottom action bar ----------------------------------------- */
QFrame#BottomBar {{
    background-color: {BG_HEADER};
    border: none;
}}
QToolButton[bottomTab="true"] {{
    background: transparent;
    color: {TEXT_DIM};
    border: none;
    padding: 4px;
}}
QToolButton[bottomTab="true"]:hover {{ color: {TEXT}; }}
QToolButton[bottomTab="true"][active="true"] {{ color: {ACCENT}; }}

/* --- reader hero ----------------------------------------------- */
QFrame#ReaderArea {{ background-color: {BG_READER}; }}

QPushButton#PrimaryButton {{
    background: transparent;
    border: 2px solid white;
    border-radius: 22px;
    color: white;
    padding: 8px 26px;
    font-size: 10pt;
    font-weight: 600;
    letter-spacing: 1px;
}}
QPushButton#PrimaryButton:hover {{ background-color: rgba(255, 255, 255, 0.10); }}
QPushButton#PrimaryButton:pressed {{ background-color: rgba(255, 255, 255, 0.18); }}

QLabel#VersionLabel {{
    color: rgba(255, 255, 255, 0.65);
    font-size: 8.5pt;
    background-color: transparent;
}}

/* --- generic buttons / inputs ---------------------------------- */
QPushButton {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 4px;
    padding: 6px 14px;
}}
QPushButton:hover {{ background-color: #3A3A3A; }}
QPushButton:pressed {{ background-color: {ACCENT_DARK}; }}
QPushButton#AccentButton {{
    background-color: {ACCENT};
    color: white;
    border: 1px solid {ACCENT};
}}
QPushButton#AccentButton:hover {{ background-color: {ACCENT_DARK}; }}

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

/* --- status banners -------------------------------------------- */
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
    color: rgba(255,255,255,0.78);
    background-color: {ACCENT};
    padding: 0 0 8px 0;
    font-size: 9pt;
}}

/* --- legacy list (kept for safety; new history uses widgets) --- */
QListWidget {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 4px;
}}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid {SEPARATOR}; }}
QListWidget::item:selected {{ background-color: {ACCENT_DARK}; color: white; }}

/* --- history view ---------------------------------------------- */
QFrame#HistoryHeader {{
    background-color: {ACCENT};
    border: none;
}}
QLabel#HistoryTitle {{
    color: white;
    font-size: 14pt;
    font-weight: 500;
}}
QToolButton#HistoryHeaderBtn {{
    background: transparent;
    border: none;
    padding: 0;
    outline: 0;
}}
QToolButton#HistoryHeaderBtn:hover {{ background-color: rgba(255, 255, 255, 0.12); }}
QToolButton#HistoryHeaderBtn:pressed {{ background-color: rgba(255, 255, 255, 0.20); }}
QFrame#HistoryItem {{
    background-color: transparent;
    border: none;
    border-bottom: 1px solid {SEPARATOR};
}}
QLabel#HistoryItemTitle {{
    color: white;
    font-weight: 600;
    font-size: 10pt;
}}
QLabel#HistoryItemMeta {{
    color: {TEXT_DIM};
    font-size: 9pt;
}}
QScrollArea#HistoryScroll {{
    background-color: {BG};
    border: none;
}}
QWidget#HistoryContainer {{ background-color: {BG}; }}
QLabel#HistoryEmpty {{
    color: {TEXT_DIM};
    font-size: 11pt;
}}

/* --- scrollbars ------------------------------------------------ */
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

/* --- misc ------------------------------------------------------ */
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

QToolButton:focus {{ outline: 0; border: none; }}
"""
