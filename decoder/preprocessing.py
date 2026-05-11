"""Image preprocessing pipeline for hard-to-read barcodes.

The goal is to defeat the typical reasons a stock decoder fails on
phone-camera photos: low contrast, motion/defocus blur, JPEG noise,
small finder patterns, perspective skew, and unusual rotations.
"""

from __future__ import annotations

from collections.abc import Iterator

import cv2
import numpy as np

Image = np.ndarray


def to_gray(img: Image) -> Image:
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def upscale(img: Image, factor: float) -> Image:
    if factor == 1.0:
        return img
    h, w = img.shape[:2]
    new_size = (max(1, int(w * factor)), max(1, int(h * factor)))
    interp = cv2.INTER_CUBIC if factor > 1.0 else cv2.INTER_AREA
    return cv2.resize(img, new_size, interpolation=interp)


def clahe(gray: Image, clip: float = 3.0, tile: int = 8) -> Image:
    op = cv2.createCLAHE(clipLimit=clip, tileGridSize=(tile, tile))
    return op.apply(gray)


def unsharp(gray: Image, amount: float = 1.5, radius: int = 3) -> Image:
    blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=radius)
    return cv2.addWeighted(gray, 1 + amount, blurred, -amount, 0)


def adaptive_threshold(gray: Image, block: int = 31, c: int = 5) -> Image:
    if block % 2 == 0:
        block += 1
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, c
    )


def otsu(gray: Image) -> Image:
    _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return out


def invert(img: Image) -> Image:
    return cv2.bitwise_not(img)


def denoise(gray: Image) -> Image:
    return cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)


def morph_close(binary: Image, k: int = 3) -> Image:
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)


def rotate(img: Image, angle: float) -> Image:
    if angle == 0:
        return img
    if angle == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    h, w = img.shape[:2]
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2 - center[0]
    matrix[1, 2] += new_h / 2 - center[1]
    return cv2.warpAffine(img, matrix, (new_w, new_h), borderValue=(255, 255, 255))


def variants(img: Image) -> Iterator[Image]:
    """Yield preprocessed variants of `img`, cheapest first.

    Cheap, high-yield transforms come first so that easy codes resolve in
    a few tries. Heavier transforms (denoise, large upscale) come later.
    """
    gray = to_gray(img)
    yield gray

    yield clahe(gray)
    yield unsharp(gray, amount=1.5, radius=2)
    yield unsharp(clahe(gray), amount=1.2, radius=2)

    yield otsu(gray)
    yield adaptive_threshold(gray, block=31, c=5)
    yield adaptive_threshold(gray, block=51, c=7)

    yield invert(gray)
    yield invert(otsu(gray))

    yield morph_close(otsu(gray), k=3)
    yield morph_close(adaptive_threshold(gray, 41, 5), k=3)

    for scale in (1.5, 2.0, 3.0):
        big = upscale(gray, scale)
        yield big
        yield clahe(big)
        yield unsharp(big, amount=1.5, radius=2)
        yield otsu(big)
        yield adaptive_threshold(big, block=51, c=7)

    yield denoise(gray)
    yield unsharp(denoise(gray), amount=1.8, radius=3)
    yield denoise(upscale(gray, 2.0))
