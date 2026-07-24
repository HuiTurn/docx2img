"""Multi-column layout helpers."""

from __future__ import annotations

from typing import List, Tuple

from ..model.section import Section


def column_geometries(
    section: Section, content_width_px: float, px_per_pt: float
) -> List[Tuple[float, float]]:
    """Return list of (x_offset_within_content, column_width) in pixels.

    x_offset is relative to the left content margin.
    """
    n = max(1, section.col_count)
    if n == 1:
        return [(0.0, content_width_px)]

    gap = section.col_space * px_per_pt

    if section.columns and not section.col_equal_width:
        widths = [c.width * px_per_pt for c in section.columns]
        # Pad / trim to n
        while len(widths) < n:
            widths.append(content_width_px / n)
        widths = widths[:n]
        total = sum(widths) + gap * (n - 1)
        if total > 0 and abs(total - content_width_px) > 1:
            scale = (content_width_px - gap * (n - 1)) / sum(widths)
            widths = [w * scale for w in widths]
    else:
        usable = content_width_px - gap * (n - 1)
        widths = [usable / n] * n

    result = []
    x = 0.0
    for i, w in enumerate(widths):
        result.append((x, w))
        x += w + gap
    return result
