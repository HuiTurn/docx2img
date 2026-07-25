"""Multi-column layout helpers."""

from __future__ import annotations

import logging
from typing import List, Tuple

from ..model.section import Section

logger = logging.getLogger(__name__)

# Maximum column gap in points beyond which we assume the document generator
# wrote an incorrect value (e.g., EMU units in a twips field).
# Word/LibreOffice clamp column spacing to fit within the page; we follow suit.
_MAX_REASONABLE_GAP_PT = 144.0  # 2 inches — generous upper bound
_DEFAULT_COL_GAP_PT = 36.0     # Section default (~0.5 inch)


def column_geometries(
    section: Section, content_width_px: float, px_per_pt: float
) -> List[Tuple[float, float]]:
    """Return list of (x_offset_within_content, column_width) in pixels.

    x_offset is relative to the left content margin.
    """
    n = max(1, section.col_count)
    if n == 1:
        return [(0.0, content_width_px)]

    gap_pt = max(0.0, section.col_space)

    # Guard against absurdly large col_space values (e.g., EMU mistakenly
    # stored as twips).  When gap * (n-1) >= content_width_px the
    # computed column width goes negative → one-word-per-line + phantom
    # pages.  Replace with a sensible default instead of clamping to a
    # sliver.
    if gap_pt > _MAX_REASONABLE_GAP_PT:
        logger.warning(
            "col_space=%.1fpt exceeds reasonable maximum (%.0fpt); "
            "falling back to default %.0fpt for %d-column layout",
            gap_pt, _MAX_REASONABLE_GAP_PT, _DEFAULT_COL_GAP_PT, n,
        )
        gap_pt = _DEFAULT_COL_GAP_PT

    gap = gap_pt * px_per_pt
    # Always leave at least one pixel per column.  The default fallback can
    # itself be wider than a deliberately tiny page or test canvas.
    max_gap = max(0.0, (content_width_px - float(n)) / (n - 1))
    if gap > max_gap:
        logger.warning(
            "column gap %.1fpx does not fit %.1fpx content width; "
            "clamping to %.1fpx",
            gap,
            content_width_px,
            max_gap,
        )
        gap = max_gap

    if section.columns and not section.col_equal_width:
        widths = [c.width * px_per_pt for c in section.columns]
        # Pad / trim to n
        while len(widths) < n:
            widths.append(content_width_px / n)
        widths = widths[:n]
        width_total = sum(widths)
        total = width_total + gap * (n - 1)
        if width_total <= 0:
            usable = max(float(n), content_width_px - gap * (n - 1))
            widths = [usable / n] * n
        elif abs(total - content_width_px) > 1:
            scale = max(0.0, content_width_px - gap * (n - 1)) / width_total
            widths = [max(1.0, w * scale) for w in widths]
    else:
        usable = max(float(n), content_width_px - gap * (n - 1))
        widths = [usable / n] * n

    result = []
    x = 0.0
    for i, w in enumerate(widths):
        result.append((x, w))
        x += w + gap
    return result
