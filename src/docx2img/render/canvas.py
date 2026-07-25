"""Canvas rendering - Convert layout tree to PIL images"""

from typing import List, Optional
from PIL import Image, ImageDraw

from ..config import Config
from ..model.enums import BorderStyle
from ..model.table import BorderDef
from .text_renderer import TextRenderer
from .table_renderer import TableRenderer
from .image_renderer import ImageRenderer
from .math_renderer import MathRenderer
from .border_renderer import BorderRenderer


class RenderCanvas:
    """Render pages to PIL images."""

    def __init__(self, config: Config):
        self.config = config
        self.text_renderer = None
        self.table_renderer = None
        self.image_renderer = ImageRenderer()
        self.math_renderer = MathRenderer()
        self.border_renderer = BorderRenderer()
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

            # Check if this is a line shape from WordprocessingGroup
            line_shape = tb.get("line_shape")
            if line_shape:
                # Render as a horizontal or vertical line
                lw_emu = line_shape.get("line_width_emu", 12700)
                color = line_shape.get("color", (0, 0, 0))
                # Convert EMU line width to pixels (approximate: 1pt = 12700 EMU)
                line_w_px = max(
                    1, round(lw_emu / 12700 * self.config.px_per_pt)
                )
                self._draw.line([(x, y), (x + w, y + h)], fill=color, width=line_w_px)
                continue

            fill = tb.get("fill")
            if fill:
                self._draw.rectangle([x, y, x + w, y + h], fill=fill)
            # Only draw an outline when the shape explicitly supplies one.
            border = tb.get("border")
            if border is not None:
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

        # Page borders
        self._draw_page_borders(page)

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

    def _draw_page_borders(self, page) -> None:
        """Draw page borders from section properties."""
        # Get borders from page's section
        sec = getattr(page, "section", None)
        if sec is None:
            return
        borders = getattr(sec, "page_borders", None)
        if borders is None or borders.display == "none":
            return

        # Display is section-local and independent of a restarted page label.
        section_page_index = getattr(page, "section_page_index", 0)
        if borders.display == "notFirstPage" and section_page_index == 0:
            return
        if borders.display == "firstPage" and section_page_index != 0:
            return

        px_per_pt = self.config.px_per_pt

        # Each side owns its own distance from the selected reference box.
        top_space = borders.top.space * px_per_pt
        bottom_space = borders.bottom.space * px_per_pt
        left_space = borders.left.space * px_per_pt
        right_space = borders.right.space * px_per_pt
        if borders.offset_from == "page":
            x1 = left_space
            y1 = top_space
            x2 = page.width - right_space
            y2 = page.height - bottom_space
        else:
            x1 = page.margin_left - left_space
            y1 = page.margin_top - top_space
            x2 = page.width - page.margin_right + right_space
            y2 = page.height - page.margin_bottom + bottom_space

        sides = [
            (borders.top, (x1, y1, x2, y1)),
            (borders.bottom, (x1, y2, x2, y2)),
            (borders.left, (x1, y1, x1, y2)),
            (borders.right, (x2, y1, x2, y2)),
        ]
        for side_def, coords in sides:
            style = BorderStyle.from_ooxml(side_def.style)
            if style == BorderStyle.NONE:
                continue
            border = BorderDef(
                style=style,
                width=max(0.125, side_def.size / 8.0),
                color=self._parse_border_color(side_def.color),
                space=float(side_def.space),
            )
            self.border_renderer.draw_border(
                self._draw, *coords, border, px_per_pt
            )

    @staticmethod
    def _parse_border_color(val: Optional[str]) -> tuple:
        """Parse OOXML border color to RGB tuple. 'auto' → black."""
        if not val or val == "auto":
            return (0, 0, 0)
        val = val.lstrip("#")
        if len(val) == 6:
            try:
                return (int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))
            except ValueError:
                pass
        return (0, 0, 0)
