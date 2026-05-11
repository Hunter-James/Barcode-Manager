"""Helpers for rendering decoded barcode payloads in the UI."""

from __future__ import annotations

import re

# Control characters we silently drop (everything below 0x20 / 0x7f
# except the whitespace-ish ones, which we collapse into a single space).
_DROP_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1c\x1e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")


def display_text(text: str) -> str:
    """Make a decoded payload safe for single-line display.

    Real-world GS1 Data Matrix codes embed FNC1 (``\\x1d``) as a field
    separator between Application Identifiers, and some producers also
    insert literal CR/LF inside the payload. Both render as ragged
    line breaks inside ``QLabel`` — that is why a code containing two
    fields shows up as e.g.::

        (01)04620408890759(21)5hYA0h(93)J9oB
        Lo,0,

    Convert FNC1 to a visible ``|`` bullet, drop other control bytes
    and collapse whitespace runs so the result reads as one logical
    line. The label still wraps it naturally when it is long.
    """
    if not text:
        return text
    text = text.replace("\x1d", " | ")
    text = _DROP_CTRL.sub("", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip()
