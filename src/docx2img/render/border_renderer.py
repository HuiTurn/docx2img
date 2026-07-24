"""Border drawing helpers."""

from __future__ import annotations

from PIL import ImageDraw

from ..model.table import BorderDef
from ..model.enums import BorderStyle


# Compound styles that render as two parallel strokes
_COMPOUND = {
    BorderStyle.DOUBLE,
    BorderStyle.THIN_THICK_SMALL_GAP,
    BorderStyle.THICK_THIN_SMALL_GAP,
    BorderStyle.THIN_THICK_MEDIUM_GAP,
    BorderStyle.THICK_THIN_MEDIUM_GAP,
    BorderStyle.THIN_THICK_LARGE_GAP,
    BorderStyle.THICK_THIN_LARGE_GAP,
}


class BorderRenderer:
    """Draw OOXML border styles onto a Pillow ImageDraw."""

    def draw_border(
        self,
        draw: ImageDraw.ImageDraw,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        border: BorderDef,
        px_per_pt: float = 1.0,
    ) -> None:
        if border is None or border.style in (BorderStyle.NONE,):
            return

        w = max(1, int(round(border.width * px_per_pt)))
        color = border.color or (0, 0, 0)
        style = border.style

        if style == BorderStyle.SINGLE:
            draw.line([(x1, y1), (x2, y2)], fill=color, width=w)
        elif style == BorderStyle.THICK:
            draw.line([(x1, y1), (x2, y2)], fill=color, width=max(w, 2))
        elif style in _COMPOUND:
            self._draw_compound(draw, x1, y1, x2, y2, color, w, style, px_per_pt)
        elif style == BorderStyle.DASHED:
            self._draw_dashed(draw, x1, y1, x2, y2, color, w, dash=6, gap=4)
        elif style == BorderStyle.DOTTED:
            self._draw_dashed(draw, x1, y1, x2, y2, color, w, dash=2, gap=3)
        elif style == BorderStyle.TRIPLE:
            gap = max(1, w)
            if abs(y1 - y2) < 0.5:
                draw.line([(x1, y1 - gap), (x2, y2 - gap)], fill=color, width=1)
                draw.line([(x1, y1), (x2, y2)], fill=color, width=1)
                draw.line([(x1, y1 + gap), (x2, y2 + gap)], fill=color, width=1)
            else:
                draw.line([(x1 - gap, y1), (x2 - gap, y2)], fill=color, width=1)
                draw.line([(x1, y1), (x2, y2)], fill=color, width=1)
                draw.line([(x1 + gap, y1), (x2 + gap, y2)], fill=color, width=1)
        elif style == BorderStyle.WAVE:
            self._draw_wave(draw, x1, y1, x2, y2, color, w)
        else:
            draw.line([(x1, y1), (x2, y2)], fill=color, width=w)

    def _draw_compound(
        self,
        draw,
        x1,
        y1,
        x2,
        y2,
        color,
        w,
        style: BorderStyle,
        px_per_pt: float,
    ) -> None:
        """Draw double / thin-thick / thick-thin compound borders.

        OOXML names put the *outer* stroke first (away from cell interior).
        Corpus tables use thinThick* on top/left and thickThin* on bottom/right.
        """
        name = style.value if isinstance(style, BorderStyle) else str(style)
        if "large" in name:
            gap = max(2, int(round(1.5 * px_per_pt)))
        elif "medium" in name:
            gap = max(2, int(round(1.0 * px_per_pt)))
        else:
            gap = max(1, int(round(0.75 * px_per_pt)))

        if style == BorderStyle.DOUBLE:
            outer_w = inner_w = max(1, w // 2) if w > 1 else 1
        elif name.startswith("thinThick"):
            outer_w, inner_w = 1, max(2, w)
        elif name.startswith("thickThin"):
            outer_w, inner_w = max(2, w), 1
        else:
            outer_w = inner_w = max(1, w // 2) if w > 1 else 1

        horizontal = abs(y1 - y2) < 0.5
        if horizontal:
            if name.startswith("thickThin"):
                # outer below (bottom edge), inner above
                draw.line([(x1, y1 + gap), (x2, y2 + gap)], fill=color, width=outer_w)
                draw.line([(x1, y1 - gap), (x2, y2 - gap)], fill=color, width=inner_w)
            else:
                # thinThick / double: outer above (top edge), inner below
                draw.line([(x1, y1 - gap), (x2, y2 - gap)], fill=color, width=outer_w)
                draw.line([(x1, y1 + gap), (x2, y2 + gap)], fill=color, width=inner_w)
        else:
            if name.startswith("thickThin"):
                # outer right, inner left
                draw.line([(x1 + gap, y1), (x2 + gap, y2)], fill=color, width=outer_w)
                draw.line([(x1 - gap, y1), (x2 - gap, y2)], fill=color, width=inner_w)
            else:
                # thinThick / double: outer left, inner right
                draw.line([(x1 - gap, y1), (x2 - gap, y2)], fill=color, width=outer_w)
                draw.line([(x1 + gap, y1), (x2 + gap, y2)], fill=color, width=inner_w)

    def _draw_dashed(self, draw, x1, y1, x2, y2, color, width, dash=6, gap=4):
        import math

        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        pos = 0.0
        drawing = True
        while pos < length:
            seg = dash if drawing else gap
            end = min(pos + seg, length)
            if drawing:
                sx, sy = x1 + ux * pos, y1 + uy * pos
                ex, ey = x1 + ux * end, y1 + uy * end
                draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
            pos = end
            drawing = not drawing

    def _draw_wave(self, draw, x1, y1, x2, y2, color, width):
        import math

        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        # Perpendicular
        px, py = -uy, ux
        amp = max(1.5, width)
        step = 4.0
        points = []
        pos = 0.0
        sign = 1
        while pos <= length:
            cx = x1 + ux * pos + px * amp * sign
            cy = y1 + uy * pos + py * amp * sign
            points.append((cx, cy))
            pos += step
            sign = -sign
        if len(points) >= 2:
            draw.line(points, fill=color, width=1)
