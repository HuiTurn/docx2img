"""Floating element exclusion zones for text wrap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class ExclusionZone:
    y_start: float
    y_end: float
    x_start: float
    x_end: float
    wrap_type: str = "square"
    z: int = 0  # behind=-1, text=0, inFront=1


@dataclass
class FloatBox:
    x: float
    y: float
    width: float
    height: float
    wrap_type: str = "square"
    image: object = None
    z: int = 0
    # OOXML positionH/V relativeFrom — resolved to page coords at pagination
    relative_x: str = "column"
    relative_y: str = "paragraph"
    abs_x: bool = False  # True once x/y are page-absolute
    abs_y: bool = False


class FloatLayoutEngine:
    """Compute text exclusion zones around floating images."""

    def compute_exclusion_zones(self, floats: List[FloatBox]) -> List[ExclusionZone]:
        zones = []
        for f in floats:
            if f.wrap_type in ("square", "tight"):
                zones.append(ExclusionZone(
                    y_start=f.y,
                    y_end=f.y + f.height,
                    x_start=f.x,
                    x_end=f.x + f.width,
                    wrap_type=f.wrap_type,
                    z=f.z,
                ))
            elif f.wrap_type == "topAndBottom":
                # Full-width exclusion between y_start and y_end
                zones.append(ExclusionZone(
                    y_start=f.y,
                    y_end=f.y + f.height,
                    x_start=-1e9,
                    x_end=1e9,
                    wrap_type=f.wrap_type,
                    z=f.z,
                ))
            # behind / inFrontOf: no exclusion
        return zones

    def available_segments(
        self,
        y: float,
        line_height: float,
        content_left: float,
        content_right: float,
        zones: List[ExclusionZone],
    ) -> List[Tuple[float, float]]:
        """Return list of (x_start, x_end) segments free of exclusions at this y band."""
        y1, y2 = y, y + line_height
        blockers = []
        for z in zones:
            if z.y_end <= y1 or z.y_start >= y2:
                continue
            left = max(content_left, z.x_start)
            right = min(content_right, z.x_end)
            if right > left:
                blockers.append((left, right))

        if not blockers:
            return [(content_left, content_right)]

        blockers.sort()
        merged = [blockers[0]]
        for a, b in blockers[1:]:
            if a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))

        segs = []
        cursor = content_left
        for a, b in merged:
            if a > cursor:
                segs.append((cursor, a))
            cursor = max(cursor, b)
        if cursor < content_right:
            segs.append((cursor, content_right))
        return [(a, b) for a, b in segs if b - a > 1.0]
