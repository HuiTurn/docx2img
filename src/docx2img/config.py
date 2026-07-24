"""Global configuration for docx2img"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Config:
    """Global configuration
    
    Args:
        dpi: Output DPI (default 150)
        font_paths: List of font file paths to search
        default_font_ascii: Default font for ASCII characters
        default_font_east_asia: Default font for CJK characters
        color_mode: Output image mode ('RGB' or 'RGBA')
        background_color: Background color (R, G, B)
    """
    dpi: int = 150
    font_paths: List[str] = field(default_factory=list)
    default_font_ascii: str = "Times New Roman"
    default_font_east_asia: str = "SimSun"
    color_mode: str = "RGB"
    background_color: tuple = (255, 255, 255)
    
    # Unit conversion
    @property
    def px_per_pt(self) -> float:
        """Convert points to pixels"""
        return self.dpi / 72.0
    
    @property
    def px_per_twip(self) -> float:
        """Convert twips to pixels (1 twip = 1/20 pt)"""
        return self.px_per_pt / 20.0
