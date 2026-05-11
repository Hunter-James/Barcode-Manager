"""Create tab — generate QR / barcode images from text."""

from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from decoder import encode, supported_formats
from storage import HistoryEntry


def _ndarray_to_qpixmap(img: np.ndarray) -> QPixmap:
    if img.ndim == 2:
        h, w = img.shape
        qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
    else:
        h, w, _ = img.shape
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class CreateTab(QWidget):
    def __init__(self, history_add: Callable[[HistoryEntry], None], parent=None) -> None:
        super().__init__(parent)
        self._history_add = history_add
        self._last_image: np.ndarray | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)

        self._format = QComboBox()
        self._format.addItems(supported_formats())
        self._format.setCurrentText("QR Code")
        form.addRow("Format", self._format)

        self._text = QPlainTextEdit()
        self._text.setPlaceholderText("Enter text, URL, or numeric payload...")
        self._text.setFixedHeight(90)
        form.addRow("Content", self._text)

        outer.addLayout(form)

        btn_row = QHBoxLayout()
        self._generate_btn = QPushButton("Generate")
        self._generate_btn.setObjectName("AccentButton")
        self._generate_btn.clicked.connect(self._generate)
        self._save_btn = QPushButton("Save as...")
        self._save_btn.clicked.connect(self._save)
        self._save_btn.setEnabled(False)
        self._copy_btn = QPushButton("Copy image")
        self._copy_btn.clicked.connect(self._copy)
        self._copy_btn.setEnabled(False)
        btn_row.addWidget(self._generate_btn)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._copy_btn)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)

        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("background-color: #FFFFFF; border: 1px solid #3A3A3A; border-radius: 4px;")
        self._preview.setMinimumHeight(280)
        outer.addWidget(self._preview, 1)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #B8B8B8;")
        outer.addWidget(self._status)

    def _generate(self) -> None:
        text = self._text.toPlainText().strip()
        fmt = self._format.currentText()
        if not text:
            self._status.setText("Enter some content first.")
            return
        try:
            img = encode(text, fmt, size=480)
        except Exception as e:
            self._status.setText(f"Failed: {e}")
            self._preview.clear()
            self._save_btn.setEnabled(False)
            self._copy_btn.setEnabled(False)
            self._last_image = None
            return
        self._last_image = img
        pm = _ndarray_to_qpixmap(img).scaled(
            self._preview.width() - 20,
            self._preview.height() - 20,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(pm)
        self._save_btn.setEnabled(True)
        self._copy_btn.setEnabled(True)
        self._status.setText(f"Generated {fmt}")
        self._history_add(HistoryEntry(text=text, format=fmt, source="create", engine="zxing-cpp"))

    def _save(self) -> None:
        if self._last_image is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save image", "barcode.png", "PNG (*.png);;JPEG (*.jpg *.jpeg);;BMP (*.bmp)"
        )
        if not path:
            return
        ok, buf = cv2.imencode("." + path.rsplit(".", 1)[-1].lower(), self._last_image)
        if not ok:
            self._status.setText("Failed to encode file")
            return
        buf.tofile(path)
        self._status.setText(f"Saved to {path}")

    def _copy(self) -> None:
        if self._last_image is None:
            return
        QApplication.clipboard().setPixmap(_ndarray_to_qpixmap(self._last_image))
        self._status.setText("Image copied to clipboard")
