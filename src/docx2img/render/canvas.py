"""Canvas rendering - Convert layout tree to PIL images"""

from typing import List
from PIL import Image, ImageDraw

from ..config import Config
from .text_renderer import TextRenderer


class RenderCanvas:
    """Render pages to PIL images"""
    
    def __init__(self, config: Config):
        self.config = config
        self.text_renderer = None
    
    def render_pages(self, pages) -> List[Image.Image]:
        """Render list of PageBox objects to PIL images
        
        Args:
            pages: List of PageBox from layout engine
            
        Returns:
            List of PIL.Image objects
        """
        images = []
        
        for page in pages:
            img = self._render_page(page)
            images.append(img)
        
        return images
    
    def _render_page(self, page) -> Image.Image:
        """Render single page to image"""
        # Create canvas
        width = int(page.width)
        height = int(page.height)
        
        if self.config.color_mode == "RGBA":
            img = Image.new("RGBA", (width, height), self.config.background_color + (255,))
        else:
            img = Image.new("RGB", (width, height), self.config.background_color)
        
        draw = ImageDraw.Draw(img)
        self.text_renderer = TextRenderer(draw, self.config)
        
        # Render each block
        for block in page.blocks:
            self._render_block(block, draw)
        
        return img
    
    def _render_block(self, block, draw: ImageDraw.ImageDraw):
        """Render a block element"""
        # Render lines
        for line in block.lines:
            self._render_line(line, draw)
    
    def _render_line(self, line, draw: ImageDraw.ImageDraw):
        """Render a line box"""
        for glyph in line.glyphs:
            self.text_renderer.draw_glyph(glyph, draw)
