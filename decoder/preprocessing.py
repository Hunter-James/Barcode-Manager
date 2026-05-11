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


def morph_dilate(binary: Image, k: int = 2) -> Image:
    """Bridges gaps in dotted / inkjet-printed codes."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    return cv2.dilate(binary, kernel)


def bilateral(gray: Image, d: int = 7, sigma_color: int = 50, sigma_space: int = 50) -> Image:
    """Edge-preserving smoothing — removes substrate texture (cardboard,
    fabric) without softening the barcode/QR edges themselves."""
    return cv2.bilateralFilter(gray, d, sigma_color, sigma_space)


def gamma(gray: Image, g: float) -> Image:
    """Lighten (g<1) or darken (g>1) — useful when capture is over- or
    under-exposed."""
    inv = 1.0 / g
    lut = np.array([((i / 255.0) ** inv) * 255 for i in range(256)], dtype=np.uint8)
    return cv2.LUT(gray, lut)


def directional_sharpen(gray: Image, horizontal: bool = True) -> Image:
    """Sharpens edges along one axis — good for 1D barcodes where bars
    run perpendicular to one axis."""
    if horizontal:
        kernel = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32) / 8.0
    else:
        kernel = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32) / 8.0
    edges = cv2.filter2D(gray, cv2.CV_32F, kernel)
    sharpened = np.clip(gray.astype(np.float32) + 1.5 * np.abs(edges), 0, 255).astype(np.uint8)
    return sharpened


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

    # Contrast and sharpening
    cl = clahe(gray)
    yield cl
    yield unsharp(gray, amount=1.5, radius=2)
    yield unsharp(cl, amount=1.2, radius=2)
    yield unsharp(gray, amount=3.0, radius=5)  # aggressive — for heavily defocused

    # Edge-preserving smoothing — removes substrate texture (cardboard, fabric)
    bil = bilateral(gray)
    yield bil
    yield clahe(bil)
    yield unsharp(bil, amount=1.5, radius=2)

    # Thresholding
    yield otsu(gray)
    yield otsu(cl)
    yield otsu(bil)
    yield adaptive_threshold(gray, block=31, c=5)
    yield adaptive_threshold(gray, block=51, c=7)
    yield adaptive_threshold(cl, block=41, c=5)

    # Gamma — over/under exposure
    yield gamma(gray, 1.6)  # darken
    yield gamma(gray, 0.6)  # brighten
    yield otsu(gamma(gray, 1.6))
    yield otsu(gamma(gray, 0.6))

    # Inverts (light-on-dark codes)
    yield invert(gray)
    yield invert(otsu(gray))

    # Morphology — fill dotted / inkjet codes
    yield morph_close(otsu(gray), k=3)
    yield morph_close(adaptive_threshold(gray, 41, 5), k=3)
    yield morph_dilate(otsu(cl), k=2)
    yield morph_dilate(otsu(bil), k=2)
    yield morph_close(morph_dilate(otsu(cl), k=2), k=2)

    # 1D-friendly directional sharpening
    yield directional_sharpen(gray, horizontal=True)
    yield directional_sharpen(gray, horizontal=False)
    yield otsu(directional_sharpen(gray, horizontal=True))
    yield otsu(directional_sharpen(gray, horizontal=False))

    # Upscaled variants for tiny codes
    for scale in (1.5, 2.0, 3.0):
        big = upscale(gray, scale)
        yield big
        yield clahe(big)
        yield unsharp(big, amount=1.5, radius=2)
        yield otsu(big)
        yield adaptive_threshold(big, block=51, c=7)
        yield bilateral(big)
        yield otsu(bilateral(big))

    # Heaviest path — full denoise
    yield denoise(gray)
    yield unsharp(denoise(gray), amount=1.8, radius=3)
    yield denoise(upscale(gray, 2.0))
