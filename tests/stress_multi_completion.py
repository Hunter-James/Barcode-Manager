"""Verify the decoder picks up *every* code in a multi-code image.

The fast path in ``decode_image`` used to short-circuit on the first
non-empty result, so a multi-code shot where zxing's default binarizer
just barely missed one symbol would lose that symbol forever. The
completion sweep that runs after the fast path is supposed to rescue
those borderline-contrast codes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

import zxingcpp
from decoder import decode_image, encode


def _low_contrast(img: np.ndarray, factor: float = 0.35, bias: int = 90) -> np.ndarray:
    f = img.astype(np.float32)
    return ((f * factor) + bias).clip(0, 255).astype(np.uint8)


def make_multi_one_degraded() -> tuple[np.ndarray, set[str]]:
    """Three QR codes side by side. The middle one is buried under
    a uniform mid-grey overlay plus blur so the default binarizer
    drops it but CLAHE / Otsu rescue it."""
    a = encode("AAA111", "QR Code", size=240)
    b = encode("BBB222", "QR Code", size=240)
    c = encode("CCC333", "QR Code", size=240)
    # Hammer b: heavy blur, very low contrast pulled toward mid grey.
    b = cv2.GaussianBlur(b, (11, 11), 4.0)
    b = ((b.astype(np.float32) * 0.10) + 118).clip(0, 255).astype(np.uint8)
    canvas = cv2.hconcat([a, b, c])
    canvas = cv2.GaussianBlur(canvas, (3, 3), 0.8)
    return canvas, {"AAA111", "BBB222", "CCC333"}


def make_multi_dm() -> tuple[np.ndarray, set[str]]:
    """Three Data Matrix codes with the middle one degraded enough
    that default zxing misses it."""
    payloads = ["AAA1", "BBB2", "CCC3"]
    cells = []
    for i, p in enumerate(payloads):
        dm = encode(p, "Data Matrix", size=160)
        if dm.ndim == 2:
            dm = cv2.cvtColor(dm, cv2.COLOR_GRAY2BGR)
        padded = cv2.copyMakeBorder(dm, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        if i == 1:
            padded = cv2.GaussianBlur(padded, (5, 5), 1.6)
            padded = ((padded.astype(np.float32) * 0.22) + 105).clip(0, 255).astype(np.uint8)
        cells.append(padded)
    canvas = cv2.hconcat(cells)
    return canvas, set(payloads)


def main() -> int:
    cases = [
        ("3 QR codes, middle one low-contrast", make_multi_one_degraded),
        ("3 Data Matrix codes, middle one low-contrast", make_multi_dm),
    ]
    passed = failed = 0
    for name, fn in cases:
        img, expected = fn()
        raw_z = {r.text for r in zxingcpp.read_barcodes(img)}
        ours = {r.text for r in decode_image(img)}
        missed_raw = expected - raw_z
        missed_ours = expected - ours
        ok = len(missed_ours) == 0
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"[{status}] {name}")
        print(f"   raw zxing-cpp found  : {sorted(raw_z)}  (missed {sorted(missed_raw)})")
        print(f"   our pipeline found   : {sorted(ours)}  (missed {sorted(missed_ours)})")
        print(f"   expected             : {sorted(expected)}")
    print(f"\n{passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
