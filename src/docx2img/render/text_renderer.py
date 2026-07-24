"""Text rendering - Draw glyphs to canvas"""

from PIL import Image, ImageDraw
from typing import Optional

from ..config import Config


HIGHLIGHT_COLORS = {
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "blue": (0, 0, 255),
    "red": (255, 0, 0),
    "darkBlue": (0, 0, 139),
    "darkCyan": (0, 139, 139),
    "darkGreen": (0, 100, 0),
    "darkMagenta": (139, 0, 139),
    "darkRed": (139, 0, 0),
    "darkYellow": (128, 128, 0),
    "darkGray": (169, 169, 169),
    "lightGray": (211, 211, 211),
    "black": (0, 0, 0),
    "white": (255, 255, 255),
}


class TextRenderer:
    """Render text glyphs to canvas."""

    def __init__(self, draw: ImageDraw.ImageDraw, config: Config):
        self.draw = draw
        self.config = config
        self.image: Optional[Image.Image] = None  # canvas image for compositing

    def draw_glyph(self, glyph, draw: Optional[ImageDraw.ImageDraw] = None) -> None:
        """Draw a glyph box at its absolute coordinates."""
        if draw is None:
            draw = self.draw

        props = glyph.props
        x = glyph.x
        y = glyph.y
        text = glyph.text
        font = glyph.font

        if not text or not font:
            return

        # Apply text transforms
        if props:
            if props.all_caps:
                text = text.upper()
            elif props.small_caps:
                text = text.upper()  # approximate small-caps

        scale = 1.0
        spacing_px = 0.0
        if props:
            if props.scale and props.scale != 100:
                scale = props.scale / 100.0
            if props.spacing:
                spacing_px = props.spacing * self.config.px_per_pt

        # Highlight background
        if props and props.highlight:
            hl_color = HIGHLIGHT_COLORS.get(props.highlight, (255, 255, 0))
            w = glyph.width if glyph.width > 0 else self._text_width(text, font)
            draw.rectangle([x, y, x + w, y + max(glyph.height, 1)], fill=hl_color)

        fill_color = (0, 0, 0)
        if props and props.color:
            fill_color = props.color

        if scale == 1.0 and spacing_px == 0.0:
            draw.text((x, y), text, font=font, fill=fill_color)
        else:
            self._draw_shaped_text(draw, x, y, text, font, fill_color, scale, spacing_px)

        # Underline
        if props and props.underline:
            tw = glyph.width if glyph.width > 0 else self._text_width(text, font)
            try:
                ascent = font.getmetrics()[0]
            except Exception:
                ascent = int(glyph.height * 0.8)
            uy = y + ascent + 1
            line_width = max(1, int((props.font_size or 12) / 12))
            draw.line([(x, uy), (x + tw, uy)], fill=fill_color, width=line_width)

        # Strikethrough
        if props and props.strike:
            tw = glyph.width if glyph.width > 0 else self._text_width(text, font)
            try:
                ascent = font.getmetrics()[0]
            except Exception:
                ascent = int(glyph.height * 0.8)
            sy = y + ascent // 2
            draw.line([(x, sy), (x + tw, sy)], fill=fill_color, width=1)

    @staticmethod
    def _text_width(text: str, font) -> float:
        try:
            bbox = font.getbbox(text)
            return float(bbox[2] - bbox[0])
        except Exception:
            return 0.0

    def _draw_shaped_text(
        self,
        draw: ImageDraw.ImageDraw,
        x: float,
        y: float,
        text: str,
        font,
        fill,
        scale: float,
        spacing_px: float,
    ) -> None:
        """Draw text with character width scaling and/or letter spacing.

        Renders into a temporary RGBA surface (char-by-char advances) and
        composites it onto the canvas, optionally compressed horizontally.
        """
        try:
            ascent, descent = font.getmetrics()
        except Exception:
            ascent, descent = 12, 3
        height = max(1, int(ascent + descent) + 2)

        # Advance width per character
        advances = []
        for ch in text:
            try:
                adv = float(font.getlength(ch))
            except (AttributeError, TypeError):
                bbox = font.getbbox(ch)
                adv = float(bbox[2] - bbox[0])
            advances.append(adv)

        natural_w = sum(advances) + spacing_px * max(0, len(text) - 1)
        if natural_w <= 0:
            return
        tmp_w = max(1, int(natural_w + 2))
        tmp = Image.new("RGBA", (tmp_w, height), (0, 0, 0, 0))
        tmp_draw = ImageDraw.Draw(tmp)

        pen = 1.0
        for ch, adv in zip(text, advances):
            if ch != " ":
                tmp_draw.text((pen, 1), ch, font=font, fill=fill + (255,))
            pen += adv + spacing_px

        if scale != 1.0:
            scaled_w = max(1, int(round(tmp_w * scale)))
            tmp = tmp.resize((scaled_w, height), Image.LANCZOS)

        canvas = self.image
        if canvas is not None:
            canvas.paste(tmp, (int(round(x)), int(round(y)) - 1), tmp)
            # Caller keeps draw in sync via canvas refresh
        else:
            # Fallback: approximate with direct draw (no horizontal compression)
            draw.text((x, y), text, font=font, fill=fill)
