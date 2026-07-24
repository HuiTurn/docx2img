"""Text rendering - Draw glyphs to canvas"""

from PIL import Image, ImageDraw, ImageFont
from typing import Any

from ..config import Config


# Highlight color mapping
HIGHLIGHT_COLORS = {
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "blue": (0, 0, 255),
    "red": (255, 0, 0),
}


class TextRenderer:
    """Render text glyphs to canvas"""
    
    def __init__(self, draw: ImageDraw.ImageDraw, config: Config):
        self.draw = draw
        self.config = config
    
    def draw_glyph(self, glyph, draw: ImageDraw.ImageDraw = None):
        """Draw a glyph box
        
        Args:
            glyph: GlyphBox object
            draw: Optional ImageDraw (uses self.draw if not provided)
        """
        if draw is None:
            draw = self.draw
        
        props = glyph.props
        x = glyph.x
        y = glyph.y
        text = glyph.text
        font = glyph.font
        
        if not text or not font:
            return
        
        # Apply highlight background first
        if props and props.highlight:
            hl_color = HIGHLIGHT_COLORS.get(props.highlight, (255, 255, 0))
            bbox = font.getbbox(text)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.rectangle([x, y, x + w, y + h], fill=hl_color)
        
        # Get text color
        fill_color = (0, 0, 0)
        if props and props.color:
            fill_color = props.color
        
        # Draw text
        draw.text((x, y), text, font=font, fill=fill_color)
        
        # Draw underline
        if props and props.underline:
            bbox = font.getbbox(text)
            tw = bbox[2] - bbox[0]
            # baseline position ≈ ascent
            metrics = font.getmetrics()
            ascent = metrics[0] if metrics else int(glyph.height * 0.8)
            uy = y + ascent + 1
            line_width = max(1, int((props.font_size if props else 12) / 12))
            draw.line([(x, uy), (x + tw, uy)], fill=fill_color, width=line_width)
        
        # Draw strikethrough
        if props and props.strike:
            bbox = font.getbbox(text)
            tw = bbox[2] - bbox[0]
            metrics = font.getmetrics()
            ascent = metrics[0] if metrics else int(glyph.height * 0.8)
            sy = y + ascent // 2
            draw.line([(x, sy), (x + tw, sy)], fill=fill_color, width=1)
