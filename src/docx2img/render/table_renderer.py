"""Table rendering — backgrounds, borders, cell text / images."""

from __future__ import annotations

from PIL import ImageDraw

from ..config import Config
from ..model.enums import BorderStyle
from ..model.table import BorderDef
from .border_renderer import BorderRenderer
from .text_renderer import TextRenderer
from .image_renderer import ImageRenderer


class TableRenderer:
    """Render a TableBox onto the canvas."""

    def __init__(self, config: Config, text_renderer: TextRenderer, canvas_img=None):
        self.config = config
        self.text_renderer = text_renderer
        self.borders = BorderRenderer()
        self.image_renderer = ImageRenderer()
        self.canvas_img = canvas_img

    def draw_table(
        self,
        table_box,
        draw: ImageDraw.ImageDraw,
        origin_x: float,
        origin_y: float,
        canvas_img=None,
    ) -> ImageDraw.ImageDraw:
        if canvas_img is not None:
            self.canvas_img = canvas_img
        px_per_pt = self.config.px_per_pt

        for cell in table_box.cells:
            x1 = origin_x + cell.x
            y1 = origin_y + cell.y
            x2 = x1 + cell.width
            y2 = y1 + cell.height
            if cell.shading:
                draw.rectangle([x1, y1, x2, y2], fill=cell.shading)

        for cell in table_box.cells:
            x1 = origin_x + cell.x
            y1 = origin_y + cell.y
            x2 = x1 + cell.width
            y2 = y1 + cell.height
            b = cell.borders or {}
            self._edge(draw, x1, y1, x2, y1, b.get("top"), px_per_pt)
            self._edge(draw, x1, y2, x2, y2, b.get("bottom"), px_per_pt)
            self._edge(draw, x1, y1, x1, y2, b.get("left"), px_per_pt)
            self._edge(draw, x2, y1, x2, y2, b.get("right"), px_per_pt)

        for cell in table_box.cells:
            draw = self._draw_cell_content(cell, draw, origin_x, origin_y)
            for nested in cell.nested_blocks:
                draw = self.draw_table(
                    nested, draw, origin_x + nested.x, origin_y + nested.y, self.canvas_img
                )
        return draw

    def _draw_cell_content(self, cell, draw, ox, oy) -> ImageDraw.ImageDraw:
        for line in cell.lines:
            for glyph in line.glyphs:
                abs_x = ox + line.x + glyph.x
                abs_y = oy + line.y
                if glyph.image is not None and self.canvas_img is not None:
                    draw = self.image_renderer.draw_image(
                        self.canvas_img, glyph.image, abs_x, abs_y, glyph.width, glyph.height
                    )
                elif glyph.text:
                    old_x, old_y = glyph.x, glyph.y
                    glyph.x = abs_x
                    glyph.y = abs_y
                    self.text_renderer.draw = draw
                    self.text_renderer.draw_glyph(glyph, draw)
                    glyph.x, glyph.y = old_x, old_y
        return draw

    def _edge(self, draw, x1, y1, x2, y2, border, px_per_pt) -> None:
        if border is None:
            border = BorderDef(style=BorderStyle.SINGLE, width=0.5, color=(0, 0, 0))
        self.borders.draw_border(draw, x1, y1, x2, y2, border, px_per_pt)
