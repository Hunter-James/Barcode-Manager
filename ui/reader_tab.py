"""Reader tab — the main scanning surface.

Three modes share the same surface:
    * 'idle'    — the big SCREEN SNIP button (matches the original).
    * 'preview' — shows a still image and the decoded result banner.
    * 'camera'  — shows a live camera feed and a result banner.
"""

from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np
from PyQt6.QtCore import QPointF, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from decoder import BarcodeResult, decode_image, decode_path
from storage import HistoryEntry

from .icons import close_icon, snip_icon
from .snip_overlay import WindowsSnipper


def ndarray_to_qpixmap(img: np.ndarray) -> QPixmap:
    if img is None or img.size == 0:
        return QPixmap()
    if img.ndim == 2:
        h, w = img.shape
        qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
    else:
        h, w, _ = img.shape
        # OpenCV BGR -> RGB for Qt
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class _DecodeWorker(QThread):
    """One-shot decode of a single image off the GUI thread."""

    finished_with = pyqtSignal(list)  # list[BarcodeResult]

    def __init__(self, image: np.ndarray, parent=None) -> None:
        super().__init__(parent)
        self._img = image

    def run(self) -> None:
        try:
            results = decode_image(self._img)
        except Exception:
            results = []
        self.finished_with.emit(results)


class PreviewLabel(QLabel):
    """QLabel that scales the pixmap to fit while keeping aspect ratio,
    and draws polygons around decoded barcodes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(QSize(200, 200))
        self.setStyleSheet("background-color: #1A6FB5;")
        self._raw: QPixmap | None = None
        self._polys: list[list[tuple[int, int]]] = []

    def set_image(self, pm: QPixmap | None) -> None:
        self._raw = pm
        self._polys = []
        self._render()

    def set_polygons(self, polys: list[list[tuple[int, int]]]) -> None:
        self._polys = polys
        self._render()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._render()

    def _render(self) -> None:
        if self._raw is None or self._raw.isNull():
            self.clear()
            return
        scaled = self._raw.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not self._polys:
            self.setPixmap(scaled)
            return
        # draw polygons in image-space, then scale
        canvas = self._raw.copy()
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#39FF14"))
        pen.setWidth(max(2, self._raw.width() // 200))
        p.setPen(pen)
        for poly in self._polys:
            if len(poly) < 2:
                continue
            for i in range(len(poly)):
                a = poly[i]
                b = poly[(i + 1) % len(poly)]
                p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
        p.end()
        scaled = canvas.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


class ReaderTab(QWidget):
    result_decoded = pyqtSignal(object)  # HistoryEntry
    busy_changed = pyqtSignal(bool)

    def __init__(self, history_add: Callable[[HistoryEntry], None], parent=None) -> None:
        super().__init__(parent)
        self._history_add = history_add
        self._worker: _DecodeWorker | None = None
        self._camera = None
        self._current_image: np.ndarray | None = None
        self._last_camera_result_text: str | None = None

        self.setAcceptDrops(True)

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

        self._idle = self._build_idle()
        self._preview = self._build_preview()

        self._stack.addWidget(self._idle)
        self._stack.addWidget(self._preview)
        self._stack.setCurrentWidget(self._idle)

    # --------- Idle ----------
    def _build_idle(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("ReaderArea")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)

        art = QLabel()
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = QPixmap(180, 180)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidthF(8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        from PyQt6.QtCore import QRectF

        p.drawRoundedRect(QRectF(10, 10, 130, 130), 26, 26)
        # plus
        p.drawLine(QPointF(155, 130), QPointF(155, 170))
        p.drawLine(QPointF(135, 150), QPointF(175, 150))
        p.end()
        art.setPixmap(pm)
        layout.addWidget(art, alignment=Qt.AlignmentFlag.AlignCenter)

        btn = QPushButton("SCREEN SNIP")
        btn.setObjectName("PrimaryButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.start_snip)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(2)

        version = QLabel("Version 5.2.0.0")
        version.setObjectName("VersionLabel")
        version.setAlignment(Qt.AlignmentFlag.AlignRight)
        version.setContentsMargins(0, 0, 12, 8)
        layout.addWidget(version)
        return frame

    # --------- Preview ----------
    def _build_preview(self) -> QWidget:
        wrapper = QFrame()
        wrapper.setObjectName("ReaderArea")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # close button at top-right
        top_row = QHBoxLayout()
        top_row.setContentsMargins(8, 8, 8, 0)
        top_row.addStretch(1)
        self._close_btn = QToolButton()
        self._close_btn.setIcon(close_icon(28))
        self._close_btn.setIconSize(QSize(20, 20))
        self._close_btn.setAutoRaise(True)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.reset)
        top_row.addWidget(self._close_btn)
        layout.addLayout(top_row)

        self._preview_label = PreviewLabel()
        layout.addWidget(self._preview_label, 1)

        self._banner = QLabel("")
        self._banner.setObjectName("StatusBanner")
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setWordWrap(True)
        self._banner.setCursor(Qt.CursorShape.PointingHandCursor)
        self._banner.mousePressEvent = self._banner_clicked  # type: ignore[assignment]
        layout.addWidget(self._banner)

        self._subtle = QLabel("")
        self._subtle.setObjectName("StatusSubtle")
        self._subtle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._subtle)
        return wrapper

    def _banner_clicked(self, _ev) -> None:
        if self._banner.property("kind") == "error" and self._current_image is not None:
            self._run_decode(self._current_image, source="file")
        elif self._banner.property("kind") == "ok":
            QApplication.clipboard().setText(self._current_text or "")
            self._subtle.setText("Copied to clipboard")

    # --------- Public API ----------
    def reset(self) -> None:
        self.stop_camera()
        self._current_image = None
        self._current_text = None
        self._preview_label.set_image(None)
        self._stack.setCurrentWidget(self._idle)

    def show_image(self, img: np.ndarray, source: str = "file") -> None:
        self.stop_camera()
        if img is None or img.size == 0:
            return
        self._current_image = img
        self._preview_label.set_image(ndarray_to_qpixmap(img))
        self._banner.setText("Decoding...")
        self._banner.setObjectName("StatusBanner")
        self._banner.setProperty("kind", "pending")
        self._refresh_banner_style()
        self._subtle.setText("")
        self._stack.setCurrentWidget(self._preview)
        self._run_decode(img, source=source)

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff *.gif);;All files (*.*)",
        )
        if not path:
            return
        data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            self._banner.setText("Cannot read this image")
            self._banner.setObjectName("StatusBannerError")
            self._banner.setProperty("kind", "error")
            self._refresh_banner_style()
            return
        self.show_image(img, source="file")

    def start_snip(self) -> None:
        self.stop_camera()
        # Use the Windows built-in Snipping Tool — handles multi-monitor
        # and DPI scaling natively.
        self._snipper = WindowsSnipper(self)
        self._snipper.captured.connect(self._on_snip)
        self._snipper.cancelled.connect(self._on_snip_cancel)
        self._snipper.start()

    def _on_snip(self, arr: np.ndarray) -> None:
        win = self.window()
        win.raise_()
        win.activateWindow()
        self.show_image(arr, source="snip")

    def _on_snip_cancel(self) -> None:
        # Nothing to restore — Windows snipper doesn't hide our window.
        pass

    def start_camera(self) -> None:
        from camera import CameraWorker, list_cameras

        self.stop_camera()
        cams = list_cameras()
        if not cams:
            self._stack.setCurrentWidget(self._preview)
            self._preview_label.set_image(None)
            self._banner.setText("No camera detected")
            self._banner.setObjectName("StatusBannerError")
            self._banner.setProperty("kind", "error")
            self._refresh_banner_style()
            self._subtle.setText("")
            return

        self._camera = CameraWorker(index=cams[0])
        self._camera.frame_ready.connect(self._on_camera_frame)
        self._camera.decode_request.connect(self._on_camera_decode)
        self._camera.error.connect(self._on_camera_error)
        self._stack.setCurrentWidget(self._preview)
        self._banner.setText("Point at a code")
        self._banner.setObjectName("StatusBanner")
        self._banner.setProperty("kind", "pending")
        self._refresh_banner_style()
        self._subtle.setText("")
        self._last_camera_result_text = None
        self._camera.start()

    def stop_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
            self._camera.wait(1000)
            self._camera = None

    def _on_camera_frame(self, frame: np.ndarray) -> None:
        self._current_image = frame
        self._preview_label.set_image(ndarray_to_qpixmap(frame))

    def _on_camera_decode(self, frame: np.ndarray) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._worker = _DecodeWorker(frame)
        self._worker.finished_with.connect(self._on_camera_decode_result)
        self._worker.start()

    def _on_camera_decode_result(self, results: list[BarcodeResult]) -> None:
        if not results:
            return
        r = results[0]
        if r.text == self._last_camera_result_text:
            return
        self._last_camera_result_text = r.text
        self._current_text = r.text
        self._banner.setText(r.text)
        self._banner.setObjectName("StatusBanner")
        self._banner.setProperty("kind", "ok")
        self._refresh_banner_style()
        self._subtle.setText(f"{r.format} • {r.engine}")
        self._preview_label.set_polygons([list(r.points) for r in results if r.points])
        self._history_add(
            HistoryEntry(text=r.text, format=r.format, source="camera", engine=r.engine)
        )
        self.result_decoded.emit(r)

    def _on_camera_error(self, msg: str) -> None:
        self._banner.setText(msg)
        self._banner.setObjectName("StatusBannerError")
        self._banner.setProperty("kind", "error")
        self._refresh_banner_style()

    # --------- Decode dispatch ----------
    def _run_decode(self, img: np.ndarray, source: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(50)
        self._pending_source = source
        self.busy_changed.emit(True)
        self._worker = _DecodeWorker(img)
        self._worker.finished_with.connect(self._on_decode_result)
        self._worker.start()

    def _on_decode_result(self, results: list[BarcodeResult]) -> None:
        self.busy_changed.emit(False)
        if not results:
            self._banner.setText("No barcode found")
            self._banner.setObjectName("StatusBannerError")
            self._banner.setProperty("kind", "error")
            self._refresh_banner_style()
            self._subtle.setText("Tap here to retry")
            self._preview_label.set_polygons([])
            self._current_text = None
            return
        r = results[0]
        self._current_text = r.text
        self._banner.setText(r.text)
        self._banner.setObjectName("StatusBanner")
        self._banner.setProperty("kind", "ok")
        self._refresh_banner_style()
        extra = f" (+{len(results)-1} more)" if len(results) > 1 else ""
        self._subtle.setText(f"{r.format} • {r.engine}{extra} • tap to copy")
        self._preview_label.set_polygons([list(rr.points) for rr in results if rr.points])
        self._history_add(
            HistoryEntry(
                text=r.text,
                format=r.format,
                source=getattr(self, "_pending_source", "file"),
                engine=r.engine,
            )
        )
        self.result_decoded.emit(r)

    def _refresh_banner_style(self) -> None:
        self._banner.style().unpolish(self._banner)
        self._banner.style().polish(self._banner)

    # --------- Drag & drop ----------
    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff", ".gif"))
            for u in e.mimeData().urls()
        ):
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent) -> None:
        for u in e.mimeData().urls():
            path = u.toLocalFile()
            if not path:
                continue
            data = np.fromfile(path, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is not None:
                self.show_image(img, source="file")
                return
