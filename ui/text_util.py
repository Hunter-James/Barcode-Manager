"""Helpers for rendering decoded barcode payloads in the UI.

The decoder returns *raw* bytes from the symbol (e.g. for a GS1 Data
Matrix the AIs are concatenated and separated by FNC1 / 0x1d). We
preserve that raw form for storage and clipboard — downstream code
(database lookups, log search) is type-strict and expects the original
invisible separators. For QLabel display we replace FNC1 with a real
newline so the user sees clear field boundaries.
"""

from __future__ import annotations

import re

# Drop everything else in the C0 / DEL block — those bytes don't have a
# meaningful glyph in any system font and just show up as boxes.
_DROP_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1c\x1e-\x1f\x7f]")


def display_text(text: str) -> str:
    """Multi-line rendering for the banner and tooltips.

    FNC1 (0x1d) is rendered as a newline so each GS1 field gets its own
    visible row. CR/LF in the payload normalised to a single newline.
    Other control bytes are stripped.
    """
    if not text:
        return text
    text = text.replace("\x1d", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _DROP_CTRL.sub("", text)
    # Collapse runs of newlines — multiple consecutive separators look
    # noisy and almost always come from malformed payloads.
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def inline_text(text: str) -> str:
    """Single-line rendering for fixed-width contexts (history snippet).

    All separators become a single space so long payloads still fit a
    truncated row.
    """
    if not text:
        return text
    text = text.replace("\x1d", " ")
    text = _DROP_CTRL.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
