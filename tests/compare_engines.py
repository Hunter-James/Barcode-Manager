"""Compare our full pipeline against the raw decoders.

A small, blurry, low-contrast QR sitting inside a busy photo — the
kind of case where every stock decoder gives up. The goal is to show:

    * raw zxing-cpp on the same image fails
    * raw pyzbar on the same image fails
    * raw cv2.QRCodeDetector on the same image fails
    * our pipeline (decode_image) succeeds
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

import zxingcpp
from pyzbar import pyzbar

from decoder import decode_image, encode


def make_hard_photo(payload: str) -> np.ndarray:
    """Tiny QR (~70px), heavily defocused, low-contrast, rotated, on a
    busy noisy background, then re-blurred."""
    qr = encode(payload, "QR Code", size=110)
    qr_bgr = qr if qr.ndim == 3 else cv2.cvtColor(qr, cv2.COLOR_GRAY2BGR)
    h, w = qr_bgr.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), 11, 1.0)
    qr_bgr = cv2.warpAffine(qr_bgr, M, (w, h), borderValue=(220, 220, 220))
    qr_bgr = cv2.GaussianBlur(qr_bgr, (3, 3), 1.2)

    bg = np.zeros((900, 700, 3), dtype=np.uint8)
    for y in range(900):
        bg[y, :, :] = [70 + int(60 * y / 900), 100 + int(50 * y / 900), 140]
    noise = np.random.randint(-25, 25, bg.shape).astype(np.int16)
    bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    bg = cv2.GaussianBlur(bg, (31, 31), 0)

    y0, x0 = 380, 290
    bg[y0 : y0 + h, x0 : x0 + w] = qr_bgr
    bg = cv2.GaussianBlur(bg, (5, 5), 1.8)
    bg = (bg.astype(np.float32) * 0.55 + 80).clip(0, 255).astype(np.uint8)
    return bg


def raw_zxing(img):
    try:
        return [r.text for r in zxingcpp.read_barcodes(img)]
    except Exception:
        return []


def raw_pyzbar(img):
    try:
        return [r.data.decode("utf-8", "replace") for r in pyzbar.decode(img)]
    except Exception:
        return []


def raw_cv2(img):
    try:
        det = cv2.QRCodeDetector()
        ok, decoded, _, _ = det.detectAndDecodeMulti(img)
        if not ok:
            return []
        return [t for t in decoded if t]
    except Exception:
        return []


def main():
    payload = "https://example.com/macca-netto-12345"
    img = make_hard_photo(payload)
    out_path = Path(__file__).parent / "hard_case.png"
    cv2.imwrite(str(out_path), img)
    print(f"wrote {out_path}  shape={img.shape}")

    print("\n--- raw decoders ---")
    print(f"zxing-cpp (raw)        : {raw_zxing(img)}")
    print(f"pyzbar    (raw)        : {raw_pyzbar(img)}")
    print(f"cv2 QR   (raw)         : {raw_cv2(img)}")

    print("\n--- our pipeline ---")
    results = decode_image(img)
    print(f"decode_image           : {[(r.text, r.engine, r.format) for r in results]}")

    ok = any(r.text == payload for r in results)
    print(f"\nPipeline recovered payload: {'YES' if ok else 'NO'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
