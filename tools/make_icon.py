"""Render the in-app QPainter icon to a multi-resolution Windows .ico file."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtWidgets import QApplication

from ui.icons import app_icon

OUT_PNG = ROOT / "resources" / "app_icon.png"
OUT_ICO = ROOT / "resources" / "app_icon.ico"


def main() -> int:
    app = QApplication.instance() or QApplication([])
    _ = app  # keep reference
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)

    pm = app_icon(256).pixmap(256, 256)
    pm.save(str(OUT_PNG), "PNG")

    img = Image.open(OUT_PNG).convert("RGBA")
    img.save(
        OUT_ICO,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"wrote {OUT_PNG}")
    print(f"wrote {OUT_ICO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
