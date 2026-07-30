"""Justify / distribute alignment for line boxes."""

from __future__ import annotations

from typing import List, Any

from ..model.enums import Alignment


# East-Asian script ranges (mirrors LineBreaker.CJK_RANGES).
_CJK_RANGES = [
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x3000, 0x303F),
    (0xFF00, 0xFFEF),
    (0x3040, 0x309F),
    (0x30A0, 0x30FF),
    (0xAC00, 0xD7AF),
]


def _glyph_has_cjk(g) -> bool:
    text = getattr(g, "text", "") or ""
    return any(
        lo <= ord(ch) <= hi for ch in text for lo, hi in _CJK_RANGES
    )


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

    # Word East-Asian justification (w:jc="both" on CJK content): the slack
    # is spread uniformly across EVERY inter-glyph gap, not just spaces.
    # CJK characters are individual glyphs and Latin words are atomic
    # glyphs, so per-gap distribution never stretches inside a word and the
    # per-gap share stays invisible — matching Word's EA layout.
    if any(_glyph_has_cjk(g) for g in glyphs):
        n_gaps = len(glyphs) - 1
        if n_gaps <= 0:
            return
        # Span-based slack preserves existing auto-space / tab x offsets.
        extra = available_width - (glyphs[-1].x + glyphs[-1].width)
        if extra <= 0.5:
            return
        each = extra / n_gaps
        shift = 0.0
        for i, g in enumerate(glyphs):
            g.x += shift
            if i < n_gaps:
                shift += each
        line.width = available_width
        return

    content_w = sum(g.width for g in glyphs)
    extra = available_width - content_w
    if extra < -0.5:
        # Word/WPS use slight negative inter-character spacing to keep a
        # nearly-fitting justified CJK line on the current row.  The line
        # breaker normally permits at most 1.5% overflow.  A line with hanging
        # end punctuation needs a little more compression because only half of
        # that final glyph is allowed outside the text edge.
        max_ratio = 1.035 if getattr(line, "_hanging_end_width", 0.0) else 1.016
        if content_w <= available_width * max_ratio + 0.5:
            gaps = [
                i for i in range(len(glyphs) - 1)
                if _is_cjkish(glyphs[i].text) or _is_cjkish(glyphs[i + 1].text)
            ]
            if gaps:
                each = extra / len(gaps)
                gap_set = set(gaps)
                x = 0.0
                for i, glyph in enumerate(glyphs):
                    glyph.x = x
                    x += glyph.width
                    if i in gap_set:
                        x += each
                line.width = available_width
        return
    if extra <= 0.5:
        return

    # Pure-Latin lines: expand whitespace glyphs (Word behaviour).
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
        # No whitespace to expand: leave ragged.
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


def _is_cjkish(text: str) -> bool:
    if not text:
        return False
    cp = ord(text[-1])
    return (
        0x3000 <= cp <= 0x303F
        or 0x3400 <= cp <= 0x4DBF
        or 0x4E00 <= cp <= 0x9FFF
        or 0xFF00 <= cp <= 0xFFEF
    )
