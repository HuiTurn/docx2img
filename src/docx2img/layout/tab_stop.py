"""Tab stop resolution."""

from __future__ import annotations

from typing import List, Optional

from ..model.paragraph import TabStop
from ..model.enums import TabStopType


class TabStopResolver:
    """Resolve next tab position from current x."""

    def resolve_tab(
        self,
        current_x: float,
        tab_stops: List[TabStop],
        default_tab: float,
        scale: float,
        *,
        content_left: float = 0.0,
        content_right: Optional[float] = None,
    ) -> float:
        """Return absolute x for tab target (left-edge of following text for left tabs)."""
        pos, _ = self.resolve_tab_stop(
            current_x, tab_stops, default_tab, scale,
            content_left=content_left, content_right=content_right,
        )
        return pos

    def resolve_tab_stop(
        self,
        current_x: float,
        tab_stops: List[TabStop],
        default_tab: float,
        scale: float,
        *,
        content_left: float = 0.0,
        content_right: Optional[float] = None,
    ) -> tuple:
        """Return (target_x, TabStop|None). TabStop is None for default grid tabs."""
        stops = sorted(tab_stops, key=lambda t: t.position) if tab_stops else []
        stop_px = [(ts.position * scale, ts) for ts in stops]

        for pos, ts in stop_px:
            if content_right is not None:
                pos = min(pos, content_right)
            if pos > current_x + 0.5:
                return pos, ts

        default_px = max(1.0, default_tab * scale)
        next_pos = (int(current_x / default_px) + 1) * default_px
        if content_right is not None:
            next_pos = min(next_pos, content_right)
        return next_pos, None

    def align_offset(
        self,
        tab_type: TabStopType,
        text_width: float,
        tab_x: float,
        current_x: float,
    ) -> float:
        """For center/right/decimal tabs, return adjusted start x for following text.

        Simplified: left tab → tab_x; center → tab_x - text_width/2; right → tab_x - text_width.
        """
        if tab_type == TabStopType.CENTER:
            return max(current_x, tab_x - text_width / 2.0)
        if tab_type == TabStopType.RIGHT or tab_type == TabStopType.DECIMAL:
            return max(current_x, tab_x - text_width)
        return tab_x
