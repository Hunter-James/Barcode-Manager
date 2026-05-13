"""Multi-engine barcode/QR decoder.

Strategy:
    1. Try every engine on the raw image (fast path).
    2. If nothing, push the image through the preprocessing pipeline.
    3. If still nothing, detect candidate regions (OpenCV QR/barcode
       detectors) and re-run the pipeline on each cropped region.
    4. If still nothing, brute-force rotations (skewed phone shots).

Decoders used:
    * zxing-cpp — fast, broad symbology coverage, best on damaged QR.
    * pyzbar    — robust on 1D codes, good complement to zxing.
    * cv2.QRCodeDetector / QRCodeDetectorAruco — region detection +
      cheap fallback decode.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Iterable
from pathlib import Path

import cv2
import numpy as np

try:
    import zxingcpp
except ImportError:  # pragma: no cover - hard dependency at runtime
    zxingcpp = None

try:
    from pyzbar import pyzbar
except (ImportError, OSError):  # pyzbar needs a native dll
    pyzbar = None

from . import preprocessing as pp

Image = np.ndarray


_FORMAT_ALIASES: dict[str, str] = {
    "QRCode": "QR Code",
    "QRCODE": "QR Code",
    "DataMatrix": "Data Matrix",
    "DATAMATRIX": "Data Matrix",
    "Aztec": "Aztec",
    "AZTEC": "Aztec",
    "PDF417": "PDF417",
    "Code128": "Code 128",
    "CODE128": "Code 128",
    "Code39": "Code 39",
    "CODE39": "Code 39",
    "Code93": "Code 93",
    "CODE93": "Code 93",
    "Codabar": "Codabar",
    "CODABAR": "Codabar",
    "EAN13": "EAN-13",
    "EAN-13": "EAN-13",
    "EAN8": "EAN-8",
    "EAN-8": "EAN-8",
    "UPCA": "UPC-A",
    "UPC-A": "UPC-A",
    "UPCE": "UPC-E",
    "UPC-E": "UPC-E",
    "ITF": "ITF",
}


def canonical_format(name: str) -> str:
    """Normalize a barcode format name to the friendly form used by encode()."""
    if not name:
        return name
    return _FORMAT_ALIASES.get(name, _FORMAT_ALIASES.get(name.replace(" ", ""), name))


@dataclasses.dataclass(frozen=True)
class BarcodeResult:
    text: str
    format: str
    engine: str
    points: tuple[tuple[int, int], ...] = ()

    def key(self) -> tuple[str, str]:
        return (self.text, self.format)


_ZXING_BINARIZERS: list[object] = []


def _zxing_binarizers() -> list[object]:
    global _ZXING_BINARIZERS
    if _ZXING_BINARIZERS or zxingcpp is None:
        return _ZXING_BINARIZERS
    b = zxingcpp.Binarizer
    # Order matters — cheapest / most accurate first; fall back to the
    # alternatives only if LocalAverage misses.
    candidates = ["LocalAverage", "GlobalHistogram", "FixedThreshold", "BoolCast"]
    _ZXING_BINARIZERS = [getattr(b, name) for name in candidates if hasattr(b, name)]
    return _ZXING_BINARIZERS


# AIM symbology identifiers that mean "this symbol was encoded as GS1".
# When zxing-cpp's TextMode.Plain returns the payload, it strips the
# GS1 "Macro" codeword that lives at the head of such a symbol — but
# downstream consumers (ERP, label printer, database) require the
# leading 0x1d (FNC1) byte to be present.
_GS1_SYMBOLOGY_IDS = frozenset(
    {"]d2", "]C1", "]e0", "]e1", "]e2", "]e3", "]e4", "]e5", "]Q3", "]Q4", "]Q5"}
)


def _looks_gs1(r) -> bool:
    sym_id = (getattr(r, "symbology_identifier", "") or "").strip()
    if sym_id in _GS1_SYMBOLOGY_IDS:
        return True
    ct = getattr(r, "content_type", None)
    gs1 = getattr(zxingcpp, "ContentType", None)
    gs1 = getattr(gs1, "GS1", None) if gs1 is not None else None
    if gs1 is not None and ct == gs1:
        return True
    return False


def _restore_gs1_prefix(r) -> str:
    text = r.text
    if not text or text.startswith("\x1d"):
        return text
    if _looks_gs1(r):
        return "\x1d" + text
    return text


def _zxing_decode(img: Image, multi_binarizer: bool = False) -> list[BarcodeResult]:
    if zxingcpp is None:
        return []
    binarizers = _zxing_binarizers() if multi_binarizer else _zxing_binarizers()[:1]
    # Plain mode returns the raw decoded bytes — for GS1 Data Matrix that
    # means the AIs are NOT wrapped in parentheses (HRI) and FNC1 (0x1d)
    # separators are preserved literally. The downstream system that
    # consumes the clipboard text is strict about format and needs these
    # bytes intact.
    text_mode = zxingcpp.TextMode.Plain
    for binarizer in binarizers:
        out: list[BarcodeResult] = []
        try:
            results = zxingcpp.read_barcodes(img, binarizer=binarizer, text_mode=text_mode)
        except Exception:
            results = []
        for r in results:
            if not r.text:
                continue
            pts = ()
            if r.position is not None:
                p = r.position
                pts = (
                    (int(p.top_left.x), int(p.top_left.y)),
                    (int(p.top_right.x), int(p.top_right.y)),
                    (int(p.bottom_right.x), int(p.bottom_right.y)),
                    (int(p.bottom_left.x), int(p.bottom_left.y)),
                )
            raw_name = str(r.format).split(".")[-1]
            out.append(
                BarcodeResult(
                    text=_restore_gs1_prefix(r),
                    format=canonical_format(raw_name),
                    engine="zxing-cpp",
                    points=pts,
                )
            )
        if out:
            return out
    return []


def _pyzbar_decode(img: Image) -> list[BarcodeResult]:
    if pyzbar is None:
        return []
    out: list[BarcodeResult] = []
    try:
        for r in pyzbar.decode(img):
            try:
                text = r.data.decode("utf-8")
            except UnicodeDecodeError:
                text = r.data.decode("latin-1", errors="replace")
            pts = tuple((int(pt.x), int(pt.y)) for pt in r.polygon) if r.polygon else ()
            out.append(
                BarcodeResult(
                    text=text,
                    format=canonical_format(str(r.type)),
                    engine="pyzbar",
                    points=pts,
                )
            )
    except Exception:
        pass
    return out


_qr_detector: cv2.QRCodeDetector | None = None


def _get_qr_detector() -> cv2.QRCodeDetector:
    global _qr_detector
    if _qr_detector is None:
        _qr_detector = cv2.QRCodeDetector()
    return _qr_detector


def _cv2_qr_decode(img: Image) -> list[BarcodeResult]:
    det = _get_qr_detector()
    out: list[BarcodeResult] = []
    try:
        ok, decoded, points, _ = det.detectAndDecodeMulti(img)
        if not ok:
            return out
        for txt, pts in zip(decoded, points or []):
            if not txt:
                continue
            poly = tuple((int(p[0]), int(p[1])) for p in pts) if pts is not None else ()
            out.append(
                BarcodeResult(text=txt, format="QR Code", engine="cv2-qr", points=poly)
            )
    except Exception:
        pass
    return out


def _engines(img: Image, *, deep: bool = False) -> list[BarcodeResult]:
    """First-hit decoder pass used by the deep cascade. Tries zxing,
    then pyzbar, then cv2-qr — short-circuits on the first non-empty
    result so the cascade stays cheap when the easier engines win."""
    out: list[BarcodeResult] = []
    out.extend(_zxing_decode(img, multi_binarizer=deep))
    if not out:
        out.extend(_pyzbar_decode(img))
    if not out:
        out.extend(_cv2_qr_decode(img))
    return out


def _all_engines(img: Image) -> list[BarcodeResult]:
    """Union of every decoder's findings on *img*.

    Used by the fast path and the completion sweep, where we care
    about *completeness* (catching every code in a multi-code shot)
    rather than the speed-optimised first-hit policy of ``_engines``."""
    out: list[BarcodeResult] = []
    out.extend(_zxing_decode(img))
    out.extend(_pyzbar_decode(img))
    out.extend(_cv2_qr_decode(img))
    return out


def _completion_sweep(img: Image, exclude: set[tuple[str, str]]) -> list[BarcodeResult]:
    """Mop-up pass after a successful fast decode.

    Even when zxing already returns N codes on the raw frame, one code
    in a multi-code shot can be just below the default binarizer's
    contrast threshold and slip through. We retry on a small set of
    cheap preprocessed variants — CLAHE, bilateral, Otsu, adaptive
    threshold — and return anything new (not already in *exclude*).
    """
    gray = pp.to_gray(img)
    variants = (
        pp.clahe(gray),
        pp.bilateral(gray),
        pp.otsu(gray),
        pp.adaptive_threshold(gray, 41, 5),
        pp.unsharp(pp.clahe(gray), amount=1.2, radius=2),
    )
    out: list[BarcodeResult] = []
    seen = set(exclude)
    for variant in variants:
        for r in _all_engines(variant):
            if r.key() in seen:
                continue
            seen.add(r.key())
            out.append(r)
    return out


def _detect_regions(img: Image) -> list[Image]:
    """Use OpenCV detectors to crop candidate barcode regions.

    Helps when the symbol is tiny inside a busy photo — we re-run the
    pipeline on the crop, which has much higher effective resolution
    after upscaling.
    """
    regions: list[Image] = []
    gray = pp.to_gray(img)
    h, w = gray.shape[:2]

    det = _get_qr_detector()
    try:
        ok, points = det.detectMulti(gray)
        if ok and points is not None:
            for pts in points:
                regions.append(_crop_quad(img, pts, pad=int(0.1 * max(w, h))))
    except Exception:
        pass

    try:
        bdet = cv2.barcode.BarcodeDetector()
        ok, points = bdet.detectMulti(gray)
        if ok and points is not None:
            for pts in points:
                regions.append(_crop_quad(img, pts, pad=int(0.1 * max(w, h))))
    except Exception:
        pass

    return regions


def _crop_quad(img: Image, pts: np.ndarray, pad: int = 0) -> Image:
    pts = np.asarray(pts, dtype=np.float32).reshape(-1, 2)
    x_min, y_min = pts.min(axis=0)
    x_max, y_max = pts.max(axis=0)
    h, w = img.shape[:2]
    x0 = max(0, int(x_min) - pad)
    y0 = max(0, int(y_min) - pad)
    x1 = min(w, int(x_max) + pad)
    y1 = min(h, int(y_max) + pad)
    return img[y0:y1, x0:x1]


def _polygons_overlap(a: tuple, b: tuple) -> bool:
    """True if the bounding boxes of two polygons overlap by more than
    half the smaller box. Used by ``_dedup`` to decide whether two
    decode results refer to the same physical symbol (polygons sit on
    top of each other) or to two distinct symbols that happen to
    share a payload — like a pallet of identical product boxes."""
    if not a or not b:
        # One of them has no spatial info (came from a transformed
        # variant whose coordinates aren't valid in the original
        # frame). Without geometry we can't tell instances apart, so
        # we conservatively treat them as the same.
        return True
    xs_a = [p[0] for p in a]
    ys_a = [p[1] for p in a]
    xs_b = [p[0] for p in b]
    ys_b = [p[1] for p in b]
    ax0, ay0, ax1, ay1 = min(xs_a), min(ys_a), max(xs_a), max(ys_a)
    bx0, by0, bx1, by1 = min(xs_b), min(ys_b), max(xs_b), max(ys_b)
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix0 >= ix1 or iy0 >= iy1:
        return False
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max(1, (ax1 - ax0) * (ay1 - ay0))
    area_b = max(1, (bx1 - bx0) * (by1 - by0))
    return inter > 0.5 * min(area_a, area_b)


def _dedup(results: Iterable[BarcodeResult]) -> list[BarcodeResult]:
    """Drop duplicates while preserving distinct physical codes that
    happen to share a payload (e.g. nine identical product Data
    Matrix codes in one shelf shot). Two results are duplicates only
    when their (text, format) match *and* their polygons overlap. A
    result without a polygon — typically one rescued by a transformed
    preprocessing variant — is treated as a duplicate of any
    same-payload result that does have a polygon."""
    out: list[BarcodeResult] = []
    for r in results:
        is_dup = False
        for existing in out:
            if r.key() != existing.key():
                continue
            if _polygons_overlap(r.points, existing.points):
                is_dup = True
                break
        if not is_dup:
            out.append(r)
    return out


_MIN_INPUT_DIM = 480


def _ensure_min_resolution(img: Image) -> Image:
    """Phone-camera shots through a screen-snip of a small region come in
    very tiny (e.g. 200×40 px barcodes). zxing/pyzbar struggle below
    roughly 400 px on the longest side, so always upscale first."""
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest >= _MIN_INPUT_DIM:
        return img
    scale = _MIN_INPUT_DIM / longest
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _strip_points(results: list[BarcodeResult]) -> list[BarcodeResult]:
    """Return copies without ``points`` — used for results coming out of
    transformed images (upscaled / rotated / cropped), whose coordinates
    no longer match the original frame, so drawing them on the preview
    would put the polygon in the wrong place."""
    return [
        BarcodeResult(text=r.text, format=r.format, engine=r.engine, points=())
        for r in results
    ]


def _scale_points(results: list[BarcodeResult], sx: float, sy: float) -> list[BarcodeResult]:
    if sx == 1.0 and sy == 1.0:
        return results
    return [
        BarcodeResult(
            text=r.text,
            format=r.format,
            engine=r.engine,
            points=tuple((int(p[0] * sx), int(p[1] * sy)) for p in r.points),
        )
        for r in results
    ]


def decode_image(img: Image) -> list[BarcodeResult]:
    """Return every barcode/QR found in `img` after exhaustive preprocessing."""
    if img is None or img.size == 0:
        return []

    orig_h, orig_w = img.shape[:2]
    img = _ensure_min_resolution(img)
    new_h, new_w = img.shape[:2]
    # If we upscaled the input we need to scale fast-path coordinates
    # back so the polygon lands on the right place in the *original*
    # frame (which is what the preview shows).
    sx = orig_w / new_w if new_w else 1.0
    sy = orig_h / new_h if new_h else 1.0

    results: list[BarcodeResult] = []

    # Fast path — every engine, full union (a multi-code shot may have
    # one symbol that only pyzbar likes and another that only zxing
    # likes; we want both).
    fast = _all_engines(img)
    if fast:
        fast = _scale_points(fast, sx, sy)
        # Completion sweep — one code in a multi-code image often sits
        # just outside the default binarizer's comfort zone. A few
        # cheap preprocessed variants rescue it without touching the
        # rest of the cascade.
        extras = _strip_points(
            _completion_sweep(img, exclude={r.key() for r in fast})
        )
        return _dedup(fast + extras)

    for variant in pp.variants(img):
        found = _engines(variant)
        if found:
            results.extend(_strip_points(found))
            break

    if not results:
        for region in _detect_regions(img):
            if region.size == 0:
                continue
            region = _ensure_min_resolution(region)
            found = _engines(region)
            if found:
                results.extend(_strip_points(found))
                continue
            for variant in pp.variants(region):
                found = _engines(variant)
                if found:
                    results.extend(_strip_points(found))
                    break
            if results:
                break

    if not results:
        for angle in (90, 180, 270, 45, 135, 225, 315, 15, 30, 60):
            rotated = pp.rotate(img, angle)
            found = _engines(rotated)
            if found:
                results.extend(_strip_points(found))
                break
            for variant in pp.variants(rotated):
                found = _engines(variant)
                if found:
                    results.extend(_strip_points(found))
                    break
            if results:
                break

    # Deep multi-binarizer pass — last resort, more expensive
    if not results:
        for variant in pp.variants(img):
            found = _engines(variant, deep=True)
            if found:
                results.extend(_strip_points(found))
                break

    return _dedup(results)


def decode_path(path: str | os.PathLike[str]) -> list[BarcodeResult]:
    p = Path(path)
    data = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        return []
    return decode_image(img)


_FORMATS_BY_NAME: dict[str, object] = {}


def _formats() -> dict[str, object]:
    global _FORMATS_BY_NAME
    if _FORMATS_BY_NAME or zxingcpp is None:
        return _FORMATS_BY_NAME
    fmt = zxingcpp.BarcodeFormat
    _FORMATS_BY_NAME = {
        "QR Code": fmt.QRCode,
        "Data Matrix": fmt.DataMatrix,
        "Aztec": fmt.Aztec,
        "PDF417": fmt.PDF417,
        "Code 128": fmt.Code128,
        "Code 39": fmt.Code39,
        "Code 93": fmt.Code93,
        "Codabar": fmt.Codabar,
        "EAN-13": fmt.EAN13,
        "EAN-8": fmt.EAN8,
        "UPC-A": fmt.UPCA,
        "UPC-E": fmt.UPCE,
        "ITF": fmt.ITF,
    }
    return _FORMATS_BY_NAME


def supported_formats() -> list[str]:
    return list(_formats().keys())


def encode(text: str, fmt_name: str, size: int = 512) -> Image:
    """Generate a barcode/QR image (BGR) for the given text and format."""
    if zxingcpp is None:
        raise RuntimeError("zxing-cpp is not available")
    fmt = _formats().get(fmt_name)
    if fmt is None:
        raise ValueError(f"unknown format: {fmt_name}")
    img = zxingcpp.write_barcode(fmt, text, width=size, height=size)
    if img is None:
        raise ValueError("failed to encode")
    arr = np.asarray(img, dtype=np.uint8)
    if arr.ndim == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return arr
