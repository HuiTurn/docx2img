"""Justify / distribute alignment for line boxes."""

from __future__ import annotations

from typing import List, Any

from ..model.enums import Alignment


def apply_justification(
    lines: List[Any],
    available_width: float,
    alignment: Alignment,
    *,
    justify_last: bool = False,
) -> None:
    """Distribute extra space across glyphs on each line.

    - JUSTIFY (both): expand spaces / CJK gaps on all but last line
    - DISTRIBUTE: expand including last line
    """
    if alignment not in (Alignment.JUSTIFY, Alignment.DISTRIBUTE):
        return
    if available_width <= 0 or not lines:
        return

    n = len(lines)
    for idx, line in enumerate(lines):
        if getattr(line, "_page_break", False):
            continue
        is_last = idx == n - 1
        if alignment == Alignment.JUSTIFY and is_last and not justify_last:
            continue
        _justify_line(line, available_width)


def _justify_line(line, available_width: float) -> None:
    glyphs = line.glyphs
    if not glyphs:
        return

    # Never stretch tabbed lines (TOC title .... page#)
    if any(getattr(g, "text", None) and len(g.text) > 2 and set(g.text) <= set("._—－…") for g in glyphs):
        return
    if any((g.text == " " or g.text == "") and g.width > 24 and not g.image for g in glyphs):
        # wide spacer likely a tab
        pass

    content_w = sum(g.width for g in glyphs)
    extra = available_width - content_w
    if extra <= 0.5:
        return

    # Prefer expanding whitespace glyphs; else expand between CJK/all glyphs
    space_idxs = [
        i for i, g in enumerate(glyphs)
        if g.text and g.text.strip() == "" and not g.image and g.width < 24
    ]
    # Exclude trailing spaces
    while space_idxs and space_idxs[-1] == len(glyphs) - 1:
        space_idxs.pop()

    gaps: List[int] = []
    if space_idxs:
        gaps = space_idxs
    else:
        # CJK-only lines: do NOT distribute (looks like letter-spacing); leave ragged
        return

    if not gaps:
        return

    each = extra / len(gaps)
    # Rebuild x positions
    x = 0.0
    gap_set = set(gaps)
    for i, g in enumerate(glyphs):
        g.x = x
        w = g.width
        if i in gap_set and g.text and g.text.strip() == "":
            g.width = w + each
            w = g.width
        x += w
        if i in gap_set and not (g.text and g.text.strip() == ""):
            x += each

    line.width = available_width
