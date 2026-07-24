"""Canvas rendering - Convert layout tree to PIL images"""

from typing import List
from PIL import Image, ImageDraw

from ..config import Config
from .text_renderer import TextRenderer
from .table_renderer import TableRenderer
from .image_renderer import ImageRenderer
from .math_renderer import MathRenderer


class RenderCanvas:
    """Render pages to PIL images."""

    def __init__(self, config: Config):
        self.config = config
        self.text_renderer = None
        self.table_renderer = None
        self.image_renderer = ImageRenderer()
        self.math_renderer = MathRenderer()
        self._img = None
        self._draw = None

    def render_pages(self, pages) -> List[Image.Image]:
        return [self._render_page(page) for page in pages]

    def _render_page(self, page) -> Image.Image:
        width = max(1, int(round(page.width)))
        height = max(1, int(round(page.height)))

        if self.config.color_mode == "RGBA":
            bg = self.config.background_color
            if len(bg) == 3:
                bg = bg + (255,)
            img = Image.new("RGBA", (width, height), bg)
        else:
            img = Image.new("RGB", (width, height), self.config.background_color)

        self._img = img
        draw = ImageDraw.Draw(img)
        self._draw = draw
        self.text_renderer = TextRenderer(draw, self.config)
        self.text_renderer.image = img
        self.table_renderer = TableRenderer(self.config, self.text_renderer)

        # Behind floats
        for fb in getattr(page, "float_boxes", []) or []:
            if fb.z < 0 and fb.image is not None:
                self._draw = self.image_renderer.draw_image(
                    self._img,
                    fb.image,
                    fb.x,
                    fb.y,
                    fb.width,
                    fb.height,
                    knockout_white=True,
                )

        for block in page.header_blocks:
            self._render_block(block)
        for block in page.blocks:
            self._render_block(block)
        for block in page.footer_blocks:
            self._render_block(block)

        # Text boxes
        for tb in getattr(page, "textbox_boxes", []) or []:
            x, y, w, h = tb["x"], tb["y"], tb["width"], tb["height"]
            fill = tb.get("fill")
            if fill:
                self._draw.rectangle([x, y, x + w, y + h], fill=fill)
            border = tb.get("border") or (0, 0, 0)
            self._draw.rectangle([x, y, x + w, y + h], outline=border, width=1)
            for ib in tb.get("blocks", []):
                self._render_block(ib)

        # In-front / wrapping floats. Knock out white only for overlay
        # decorations (inFrontOf); photos (topAndBottom etc.) stay opaque.
        for fb in getattr(page, "float_boxes", []) or []:
            if fb.z >= 0 and fb.image is not None:
                self._draw = self.image_renderer.draw_image(
                    self._img,
                    fb.image,
                    fb.x,
                    fb.y,
                    fb.width,
                    fb.height,
                    knockout_white=(fb.wrap_type == "inFrontOf"),
                )

        seps = getattr(page, "_col_seps", None)
        if seps:
            for x in seps:
                self._draw.line(
                    [(x, page.margin_top), (x, page.height - page.margin_bottom)],
                    fill=(160, 160, 160),
                    width=1,
                )

        return img

    def _render_block(self, block) -> None:
        if getattr(block, "table_box", None) is not None:
            self._draw = self.table_renderer.draw_table(
                block.table_box, self._draw, block.table_box.x, block.table_box.y, self._img
            )
            self.text_renderer.draw = self._draw
            return

        for line in block.lines:
            self._render_line(line)

    def _render_line(self, line) -> None:
        for glyph in line.glyphs:
            if glyph.image is not None:
                self._draw = self.image_renderer.draw_image(
                    self._img, glyph.image, glyph.x, glyph.y, glyph.width, glyph.height
                )
                self.text_renderer.draw = self._draw
            elif getattr(glyph, "math_box", None) is not None:
                self.math_renderer.draw(glyph.math_box, self._draw, glyph.x, glyph.y)
            else:
                self.text_renderer.draw_glyph(glyph, self._draw)
