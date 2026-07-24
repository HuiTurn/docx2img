"""Render laid-out math boxes."""

from __future__ import annotations

from PIL import ImageDraw


class MathRenderer:
    def draw(self, box, draw: ImageDraw.ImageDraw, ox: float, oy: float, fill=(0, 0, 0)) -> None:
        for t in box.texts:
            draw.text(
                (ox + t["x"], oy + t["y"]),
                t["text"],
                font=t.get("font"),
                fill=fill,
            )
        for ln in box.lines:
            w = max(1, int(round(ln.get("width", 1))))
            draw.line(
                [(ox + ln["x1"], oy + ln["y1"]), (ox + ln["x2"], oy + ln["y2"])],
                fill=fill,
                width=w,
            )
        for ch in box.children:
            self.draw(ch, draw, ox + ch.x, oy + ch.y, fill)
