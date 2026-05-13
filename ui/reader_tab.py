"""Reader tab — the main scanning surface.

Three modes share the same surface:
    * 'idle'    — the big SCREEN SNIP button.
    * 'preview' — shows a still image and the decoded result banner.
    * 'camera'  — shows a live camera feed and a result banner.
"""

from __future__ import annotations

import uuid
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
from storage import HistoryEntry, snapshots_dir

from .icons import close_icon, snip_icon
from .snip_overlay import ScreenSnipper
from .text_util import display_text, inline_text


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
    """One-shot decode of a single image off the GUI thread.

    Each worker carries a monotonically increasing id; the Reader uses
    it to ignore results from outdated workers (i.e. when the user
    triggers a second decode before the first one finishes — that bug
    used to surface as "first scan succeeds, second one says
    No barcode found" because the late result of the previous worker
    over-wrote the new one).
    """

    finished_with = pyqtSignal(list, int)  # list[BarcodeResult], worker_id

    def __init__(self, image: np.ndarray, worker_id: int, parent=None) -> None:
        super().__init__(parent)
        self._img = image
        self._id = worker_id

    def run(self) -> None:
        try:
            results = decode_image(self._img)
        except Exception:
            results = []
        self.finished_with.emit(results, self._id)


class PreviewLabel(QLabel):
    """QLabel that scales the pixmap to fit while keeping aspect ratio,
    and draws polygons around decoded barcodes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(QSize(200, 200))
        self.setStyleSheet("background-color: #1A6FB5;")
        self._raw: QPixmap | None = None
        # Each marker is (polygon_points, label_or_None). When label is
        # not None, a numbered red badge is drawn at the polygon's
        # bottom-left corner so the user can match each polygon to its
        # entry in the banner list.
        self._markers: list[tuple[list[tuple[int, int]], str | None]] = []

    def set_image(self, pm: QPixmap | None) -> None:
        self._raw = pm
        self._markers = []
        self._render()

    def set_polygons(
        self,
        items: list[tuple[list[tuple[int, int]], str | None]] | list[list[tuple[int, int]]],
    ) -> None:
        # Backward-compatible: accept either a list of polygons or a list
        # of (polygon, label) tuples.
        if items and isinstance(items[0], tuple) and len(items[0]) == 2 and (
            items[0][1] is None or isinstance(items[0][1], str)
        ):
            self._markers = list(items)  # already in (poly, label) form
        else:
            self._markers = [(p, None) for p in items]
        self._render()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._render()

    def _render(self) -> None:
        if self._raw is None or self._raw.isNull():
            self.clear()
            return
        if not self._markers:
            scaled = self._raw.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
            return

        canvas = self.render_annotated(self._raw, self._markers)
        scaled = canvas.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    @classmethod
    def render_annotated(
        cls,
        raw: QPixmap,
        markers: list[tuple[list[tuple[int, int]], str | None]],
    ) -> QPixmap:
        """Return a copy of *raw* with all polygons and numbered badges
        drawn in place. Used both for the live preview and to persist
        an annotated snapshot per multi-code scan."""
        canvas = raw.copy()
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = raw.width()
        line_w = max(2, w // 200)
        pen = QPen(QColor("#39FF14"))
        pen.setWidth(line_w)
        for poly, label in markers:
            if len(poly) < 2:
                continue
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(len(poly)):
                a = poly[i]
                b = poly[(i + 1) % len(poly)]
                p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
            if label is not None:
                cls._draw_badge(p, poly, label, w)
        p.end()
        return canvas

    @staticmethod
    def _draw_badge(p: QPainter, poly: list[tuple[int, int]], label: str, img_w: int) -> None:
        # Place the badge straddling the bottom-left corner of the
        # polygon — half inside, half outside, so it's clearly attached
        # to *this* code and not the next one.
        xs = [pt[0] for pt in poly]
        ys = [pt[1] for pt in poly]
        cx = min(xs)
        cy = max(ys)
        radius = max(14, img_w // 36)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E33B3B"))
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        p.setPen(QColor("#FFFFFF"))
        font = p.font()
        font.setBold(True)
        font.setPixelSize(int(radius * 1.25))
        p.setFont(font)
        metrics = p.fontMetrics()
        rect = metrics.boundingRect(label)
        # Approximately center the digits inside the circle
        tx = cx - rect.width() / 2
        ty = cy + rect.height() / 2 - metrics.descent()
        p.drawText(QPointF(tx, ty), label)


class ReaderTab(QWidget):
    result_decoded = pyqtSignal(object)  # HistoryEntry
    busy_changed = pyqtSignal(bool)

    def __init__(self, history_add: Callable[[HistoryEntry], None], parent=None) -> None:
        super().__init__(parent)
        self._history_add = history_add
        self._camera = None
        self._current_image: np.ndarray | None = None
        self._last_camera_result_text: str | None = None
        # Workers are tracked by id; only the latest one's result is honoured.
        self._workers: list[_DecodeWorker] = []
        self._latest_still_id: int = 0
        self._latest_camera_id: int = 0
        self._worker_id_seq: int = 0

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
        layout.setSpacing(0)
        layout.addStretch(3)

        art = QLabel()
        art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        art.setPixmap(self._build_idle_art())
        art.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout.addWidget(art, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(18)

        btn = QPushButton("SCREEN SNIP")
        btn.setObjectName("PrimaryButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.start_snip)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(4)

        version_row = QHBoxLayout()
        version_row.setContentsMargins(0, 0, 12, 6)
        version_row.addStretch(1)
        version = QLabel("Version 1.0.0")
        version.setObjectName("VersionLabel")
        version_row.addWidget(version)
        layout.addLayout(version_row)
        return frame

    @staticmethod
    def _build_idle_art() -> QPixmap:
        from PyQt6.QtCore import QRectF

        size = 170
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidthF(7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        # Hollow rounded square, upper-left
        rect = QRectF(8, 8, 118, 118)
        p.drawRoundedRect(rect, 22, 22)
        # Plus sign at lower-right, slightly outside the square
        cx, cy = 144, 140
        arm = 20
        p.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
        p.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))
        p.end()
        return pm

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
        self._snipper = ScreenSnipper(self)
        self._snipper.captured.connect(self._on_snip)
        self._snipper.cancelled.connect(self._on_snip_cancel)
        # Hide the main window during the grab so the captured screenshot
        # doesn't contain our own UI.
        self._snipper.start(app_window=self.window())

    def _on_snip(self, arr: np.ndarray) -> None:
        self.show_image(arr, source="snip")

    def _on_snip_cancel(self) -> None:
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
        # Skip if any camera worker is still busy — frames arrive ~30 fps,
        # we don't want a backlog.
        if any(w.isRunning() for w in self._workers if getattr(w, "_purpose", "") == "camera"):
            return
        self._worker_id_seq += 1
        self._latest_camera_id = self._worker_id_seq
        worker = _DecodeWorker(frame, self._worker_id_seq, parent=self)
        worker._purpose = "camera"  # tag, used by the skip above
        worker.finished_with.connect(self._on_camera_decode_result)
        worker.finished.connect(self._cleanup_worker)
        self._workers.append(worker)
        worker.start()

    def _on_camera_decode_result(self, results: list[BarcodeResult], worker_id: int) -> None:
        if worker_id != self._latest_camera_id:
            return  # outdated frame, ignore
        if not results:
            return
        # Camera frames usually contain one code; if more arrive in the
        # same frame we just show the first one in the banner but still
        # number all of them on the preview.
        r = results[0]
        if r.text == self._last_camera_result_text:
            return
        self._last_camera_result_text = r.text
        self._current_text = r.text
        self._banner.setText(display_text(r.text))
        self._banner.setObjectName("StatusBanner")
        self._banner.setProperty("kind", "ok")
        self._refresh_banner_style()
        self._subtle.setText(f"{r.format} • {r.engine}")
        if len(results) > 1:
            markers = [(list(rr.points), str(i)) for i, rr in enumerate(results, 1) if rr.points]
        else:
            markers = [(list(rr.points), None) for rr in results if rr.points]
        self._preview_label.set_polygons(markers)
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
        self._worker_id_seq += 1
        self._latest_still_id = self._worker_id_seq
        self._pending_source = source
        self.busy_changed.emit(True)
        worker = _DecodeWorker(img, self._worker_id_seq, parent=self)
        worker._purpose = "still"
        worker.finished_with.connect(self._on_decode_result)
        worker.finished.connect(self._cleanup_worker)
        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self) -> None:
        w = self.sender()
        if w in self._workers:
            self._workers.remove(w)
            w.deleteLater()

    def _persist_group_snapshot(
        self,
        group_id: str,
        markers: list[tuple[list[tuple[int, int]], str | None]],
    ) -> None:
        """Save the captured frame, with polygons + numbered badges
        drawn on it, so the History view can show 'what was scanned'
        without re-running the decoder."""
        if self._current_image is None or self._current_image.size == 0:
            return
        try:
            raw = ndarray_to_qpixmap(self._current_image)
            annotated = PreviewLabel.render_annotated(raw, markers)
            path = snapshots_dir() / f"{group_id}.png"
            annotated.save(str(path), "PNG")
        except Exception:
            # Snapshot persistence is best-effort; never let it sink
            # an otherwise-successful scan.
            pass

    def _on_decode_result(self, results: list[BarcodeResult], worker_id: int) -> None:
        if worker_id != self._latest_still_id:
            return  # an older decode finished after we kicked off a newer one
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

        # Reading order — top-to-bottom, then left-to-right inside a row.
        def _key(r: BarcodeResult) -> tuple[float, float]:
            if not r.points:
                return (float("inf"), float("inf"))
            xs = [p[0] for p in r.points]
            ys = [p[1] for p in r.points]
            return (min(ys), min(xs))

        ordered = sorted(results, key=_key)
        source = getattr(self, "_pending_source", "file")

        if len(ordered) == 1:
            r = ordered[0]
            self._current_text = r.text
            self._banner.setText(display_text(r.text))
            self._banner.setObjectName("StatusBanner")
            self._banner.setProperty("kind", "ok")
            self._refresh_banner_style()
            self._subtle.setText(f"{r.format} • {r.engine} • tap to copy")
            self._preview_label.set_polygons(
                [(list(r.points), None)] if r.points else []
            )
            self._history_add(
                HistoryEntry(text=r.text, format=r.format, source=source, engine=r.engine)
            )
            self.result_decoded.emit(r)
            return

        # Multiple codes — number them and show as a list.
        banner_lines = [f"{i}. {inline_text(r.text)}" for i, r in enumerate(ordered, 1)]
        self._banner.setText("\n".join(banner_lines))
        self._banner.setObjectName("StatusBanner")
        self._banner.setProperty("kind", "ok")
        self._refresh_banner_style()
        # Clipboard carries raw payloads (FNC1 and all) one per line so
        # the consumer can split on \n.
        self._current_text = "\n".join(r.text for r in ordered)

        formats = sorted({r.format for r in ordered})
        engines = sorted({r.engine for r in ordered})
        self._subtle.setText(
            f"{len(ordered)} codes • {', '.join(formats)} • {', '.join(engines)} • tap to copy"
        )

        markers: list[tuple[list[tuple[int, int]], str | None]] = []
        for i, r in enumerate(ordered, 1):
            if r.points:
                markers.append((list(r.points), str(i)))
        self._preview_label.set_polygons(markers)

        # Group every entry of this scan under one uuid so the History
        # view can render them as a single "N codes scanned together"
        # block. Add in reverse so that after each insert-at-0 the
        # store ends up with the group in natural reading order
        # (code1 on top, code2 below it, etc.).
        group_id = uuid.uuid4().hex
        self._persist_group_snapshot(group_id, markers)
        for r in reversed(ordered):
            self._history_add(
                HistoryEntry(
                    text=r.text,
                    format=r.format,
                    source=source,
                    engine=r.engine,
                    group_id=group_id,
                    group_size=len(ordered),
                )
            )
        self.result_decoded.emit(ordered[0])

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
