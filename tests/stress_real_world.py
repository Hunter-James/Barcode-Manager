"""Stress test for real-world failure modes.

Two scenarios that stock decoders typically miss but our pipeline should
recover:

* A tiny linear barcode coming out of a screen-snip (200×40 px), the
  kind you get when you crop a small region of a phone screen or web
  page. zxing-cpp on the raw image typically fails because there's not
  enough signal — only an upscale-first path saves it.

* A Data Matrix printed by inkjet on beige cardboard, with a specular
  glare on one side. Substrate texture and uneven illumination defeat
  the default binarizer.
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


# ---------- Case 1: tiny screen-snipped Code 128 ----------

def case_tiny_code128(payload: str) -> np.ndarray:
    """Mimics what `ImageGrab.grab` returns when the user snips a small
    region containing a Code 128 barcode (clean white background,
    moderate JPEG-like noise from rendering)."""
    full = encode(payload, "Code 128", size=400)
    # zxing returns ~200×100; tighten margins to mimic a tight snip
    gray = cv2.cvtColor(full, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(gray < 80)
    if len(xs) == 0:
        return full
    pad = 18
    x0, x1 = max(0, xs.min() - pad), min(gray.shape[1], xs.max() + pad)
    y0, y1 = max(0, ys.min() - pad), min(gray.shape[0], ys.max() + pad)
    cropped = full[y0:y1, x0:x1]
    # Downscale to ~200px wide — that's where stock zxing tends to choke
    target_w = 220
    scale = target_w / cropped.shape[1]
    small = cv2.resize(cropped, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    # Mild blur to mimic display rendering
    small = cv2.GaussianBlur(small, (3, 3), 0.6)
    return small


# ---------- Case 2: Data Matrix on textured surface with glare ----------

def case_dm_on_cardboard(payload: str) -> np.ndarray:
    dm = encode(payload, "Data Matrix", size=220)
    if dm.ndim == 2:
        dm = cv2.cvtColor(dm, cv2.COLOR_GRAY2BGR)
    h, w = dm.shape[:2]

    # 900×700 beige cardboard background with subtle fibre noise
    bg = np.full((900, 700, 3), (190, 200, 215), dtype=np.uint8)
    noise = np.random.randint(-12, 12, bg.shape).astype(np.int16)
    bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    bg = cv2.GaussianBlur(bg, (3, 3), 0)

    # Place DM
    y0, x0 = 320, 240
    bg[y0 : y0 + h, x0 : x0 + w] = dm

    # Glare on the right side — a bright vertical gradient overlay
    gradient = np.zeros_like(bg, dtype=np.float32)
    for x in range(bg.shape[1]):
        falloff = max(0.0, (x - bg.shape[1] * 0.55) / (bg.shape[1] * 0.45))
        gradient[:, x] = falloff * 80
    glare = (bg.astype(np.float32) + gradient).clip(0, 255).astype(np.uint8)

    # Slight defocus over the whole photo
    return cv2.GaussianBlur(glare, (3, 3), 0.8)


# ---------- Case 3: blurry low-contrast Code 128 on warm paper -----

def case_code128_warm_blur(payload: str) -> np.ndarray:
    bc = encode(payload, "Code 128", size=600)
    if bc.ndim == 2:
        bc = cv2.cvtColor(bc, cv2.COLOR_GRAY2BGR)
    # Tint towards warm paper
    bc = bc.astype(np.float32)
    bc[..., 0] = bc[..., 0] * 0.92  # less blue
    bc[..., 2] = np.minimum(bc[..., 2] * 1.05, 255)  # more red
    bc = bc.astype(np.uint8)
    # Defocus
    bc = cv2.GaussianBlur(bc, (5, 5), 1.4)
    # Contrast crush
    bc = (bc.astype(np.float32) * 0.7 + 50).clip(0, 255).astype(np.uint8)
    return bc


def case_dm_inkjet_dots(payload: str) -> np.ndarray:
    """Inkjet-printed Data Matrix on a curved cardboard surface with
    glare on one side. The print is dotted (sparse 'cells' painted as
    tiny scattered ink drops) — that's exactly the look on screen 2."""
    dm = encode(payload, "Data Matrix", size=200)
    if dm.ndim == 3:
        dm = cv2.cvtColor(dm, cv2.COLOR_BGR2GRAY)
    # Make the dark modules look like ink-jet dots
    dotted = np.full_like(dm, 230, dtype=np.uint8)
    dark = dm < 80
    rng = np.random.default_rng(7)
    # Inside each dark module, draw a smaller dot
    h, w = dm.shape
    for y in range(2, h - 2, 4):
        for x in range(2, w - 2, 4):
            if dark[y, x]:
                cv2.circle(dotted, (x + rng.integers(-1, 2), y + rng.integers(-1, 2)),
                           1, 30, -1)
    # Background beige photo
    bg = np.full((900, 700, 3), (170, 185, 205), dtype=np.uint8)
    noise = np.random.randint(-15, 15, bg.shape).astype(np.int16)
    bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    bg = cv2.GaussianBlur(bg, (5, 5), 0)
    # Place
    y0, x0 = 340, 240
    dotted_bgr = cv2.cvtColor(dotted, cv2.COLOR_GRAY2BGR)
    bg[y0 : y0 + h, x0 : x0 + w] = dotted_bgr
    # Glare on right
    gradient = np.zeros_like(bg, dtype=np.float32)
    for x in range(bg.shape[1]):
        falloff = max(0.0, (x - bg.shape[1] * 0.60) / (bg.shape[1] * 0.40))
        gradient[:, x] = falloff * 90
    out = (bg.astype(np.float32) + gradient).clip(0, 255).astype(np.uint8)
    return cv2.GaussianBlur(out, (3, 3), 0.7)


CASES = [
    ("tiny snipped Code 128 (~220 px wide)", case_tiny_code128, "0004625941930755771115"),
    ("Data Matrix on beige cardboard + glare", case_dm_on_cardboard, "01046009050002402151"),
    ("Code 128 warm paper + defocus + low contrast", case_code128_warm_blur, "0014625941930555571624"),
    ("Data Matrix inkjet dotted + glare", case_dm_inkjet_dots, "0104600905000240"),
]


def main():
    passed = failed = 0
    for name, fn, payload in CASES:
        img = fn(payload)
        raw_z = raw_zxing(img)
        raw_p = raw_pyzbar(img)
        ours = [r.text for r in decode_image(img)]
        ok = payload in ours
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"[{status}] {name}")
        print(f"   raw zxing-cpp : {raw_z}")
        print(f"   raw pyzbar    : {raw_p}")
        print(f"   our pipeline  : {ours}")
        print(f"   expected      : {payload!r}")
    print(f"\n{passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
