"""Stress test for the decoder on synthesised hard cases.

Generates a QR code, then beats it up with blur, noise, rotation,
low contrast, perspective skew and downscaling — and asserts the
decoder still recovers the payload.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from decoder import decode_image, encode


def add_noise(img, sigma=10):
    noise = np.random.normal(0, sigma, img.shape).astype(np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def low_contrast(img, factor=0.4):
    mean = 128
    return np.clip((img.astype(np.float32) - mean) * factor + mean, 0, 255).astype(np.uint8)


def perspective(img, magnitude=0.08):
    h, w = img.shape[:2]
    m = magnitude
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32(
        [
            [w * m, h * m * 0.6],
            [w * (1 - m * 0.5), h * m],
            [w, h * (1 - m * 0.3)],
            [w * m * 0.6, h * (1 - m)],
        ]
    )
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderValue=(255, 255, 255))


def rotate(img, angle):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderValue=(255, 255, 255))


def put_on_busy_background(qr, bg_size=900):
    bg = np.random.randint(60, 200, (bg_size, bg_size, 3), dtype=np.uint8)
    bg = cv2.GaussianBlur(bg, (51, 51), 0)
    qh, qw = qr.shape[:2]
    y = (bg_size - qh) // 2
    x = (bg_size - qw) // 2
    bg[y : y + qh, x : x + qw] = qr
    return bg


def case_blur(payload):
    qr = encode(payload, "QR Code", size=400)
    return cv2.GaussianBlur(qr, (15, 15), 4)


def case_blur_low_contrast(payload):
    qr = encode(payload, "QR Code", size=400)
    qr = cv2.GaussianBlur(qr, (9, 9), 2)
    return low_contrast(qr, 0.5)


def case_rotated_noisy(payload):
    qr = encode(payload, "QR Code", size=400)
    qr = rotate(qr, 23)
    qr = cv2.GaussianBlur(qr, (5, 5), 1.5)
    return add_noise(qr, 15)


def case_tiny_in_photo(payload):
    qr = encode(payload, "QR Code", size=140)
    qr = cv2.GaussianBlur(qr, (3, 3), 1)
    return put_on_busy_background(qr, 900)


def case_perspective_blur(payload):
    qr = encode(payload, "QR Code", size=400)
    qr = perspective(qr, 0.12)
    qr = cv2.GaussianBlur(qr, (7, 7), 2)
    return add_noise(qr, 10)


def case_ean_blur(payload):
    bc = encode(payload, "EAN-13", size=400)
    bc = cv2.GaussianBlur(bc, (5, 5), 2)
    return low_contrast(bc, 0.55)


def main():
    cases = [
        ("heavy gaussian blur", case_blur, "Hello QR"),
        ("blur + low contrast", case_blur_low_contrast, "https://example.com/test"),
        ("rotated 23deg + noise", case_rotated_noisy, "Rotated payload 123"),
        ("tiny QR in busy 900px photo", case_tiny_in_photo, "Tiny payload"),
        ("perspective + blur + noise", case_perspective_blur, "Skewed photo"),
        ("EAN-13 blurred + low contrast", case_ean_blur, "5901234123457"),
    ]
    passed = failed = 0
    for name, fn, payload in cases:
        img = fn(payload)
        results = decode_image(img)
        ok = any(r.text == payload for r in results)
        engines = ", ".join(sorted({r.engine for r in results})) or "-"
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"  decoded: {[r.text for r in results]}")
        print(f"[{status}] {name:40s} payload={payload!r:35s} via {engines}")
    print(f"\nResults: {passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
