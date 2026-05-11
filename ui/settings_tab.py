"""Settings tab — app-level preferences, persisted in QSettings."""

from __future__ import annotations

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsTab(QWidget):
    def __init__(self, on_clear_history, parent=None) -> None:
        super().__init__(parent)
        self.settings = QSettings("BarcodeManager", "BarcodeManager")
        self._on_clear_history = on_clear_history

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._copy_on_decode = QCheckBox("Copy decoded text to clipboard automatically")
        self._copy_on_decode.setChecked(self.settings.value("copy_on_decode", False, bool))
        self._copy_on_decode.toggled.connect(lambda v: self.settings.setValue("copy_on_decode", v))
        form.addRow(self._copy_on_decode)

        self._beep_on_decode = QCheckBox("Play a sound on successful decode")
        self._beep_on_decode.setChecked(self.settings.value("beep_on_decode", True, bool))
        self._beep_on_decode.toggled.connect(lambda v: self.settings.setValue("beep_on_decode", v))
        form.addRow(self._beep_on_decode)

        self._open_url = QCheckBox("Offer to open URLs in browser")
        self._open_url.setChecked(self.settings.value("offer_open_url", True, bool))
        self._open_url.toggled.connect(lambda v: self.settings.setValue("offer_open_url", v))
        form.addRow(self._open_url)

        self._camera_index = QSpinBox()
        self._camera_index.setRange(0, 9)
        self._camera_index.setValue(int(self.settings.value("camera_index", 0)))
        self._camera_index.valueChanged.connect(lambda v: self.settings.setValue("camera_index", v))
        form.addRow("Preferred camera index", self._camera_index)

        self._decode_interval = QSpinBox()
        self._decode_interval.setRange(50, 2000)
        self._decode_interval.setSuffix(" ms")
        self._decode_interval.setSingleStep(50)
        self._decode_interval.setValue(int(self.settings.value("decode_interval_ms", 250)))
        self._decode_interval.valueChanged.connect(
            lambda v: self.settings.setValue("decode_interval_ms", v)
        )
        form.addRow("Live decode interval", self._decode_interval)

        outer.addLayout(form)

        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(self._on_clear_history)
        outer.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        outer.addStretch(1)

        about = QLabel(
            "Barcode Manager (Open Edition)\n"
            "Multi-engine recognition: zxing-cpp + pyzbar + OpenCV\n"
            "Aggressive image preprocessing for hard-to-read codes."
        )
        about.setStyleSheet("color: #B8B8B8;")
        about.setWordWrap(True)
        outer.addWidget(about)
