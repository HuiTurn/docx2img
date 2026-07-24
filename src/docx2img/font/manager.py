"""Font manager - Load and cache fonts"""

import os
from pathlib import Path
from typing import Dict, Optional, Tuple
from PIL import ImageFont

from ..config import Config


class FontManager:
    """Manage font loading and caching
    
    Features:
    - Cache loaded fonts by (name, size, bold, italic)
    - Fallback chain for missing fonts
    - System font discovery
    - Built-in font support
    """
    
    # Common font fallbacks
    FONT_FALLBACKS = {
        "Times New Roman": ["Times", "DejaVu Serif", "serif"],
        "Arial": ["Helvetica", "DejaVu Sans", "sans-serif"],
        "SimSun": ["WenQuanYi Micro Hei", "AR PL UMing CN", "serif"],
        "SimHei": ["WenQuanYi Zen Hei", "AR PL UKai CN", "sans-serif"],
        "Calibri": ["Arial", "Helvetica", "sans-serif"],
    }
    
    def __init__(self, config: Config):
        self.config = config
        self._cache: Dict[Tuple[str, float, bool, bool], ImageFont.FreeTypeFont] = {}
        self._font_paths = self._discover_fonts()
    
    def _discover_fonts(self) -> Dict[str, str]:
        """Discover available fonts
        
        Search order:
        1. User-provided font paths from config
        2. ./fonts/ directory
        3. System font directories
        """
        font_paths = {}
        
        # Check config font paths
        for path in self.config.font_paths:
            if os.path.isfile(path):
                name = Path(path).stem
                font_paths[name] = path
        
        # Check local fonts directory
        local_fonts = Path(__file__).parent.parent.parent / "fonts"
        if local_fonts.exists():
            for f in local_fonts.iterdir():
                if f.suffix.lower() in ['.ttf', '.ttc', '.otf']:
                    font_paths[f.stem] = str(f)
        
        # Check system fonts (Linux)
        system_dirs = [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            os.path.expanduser("~/.fonts"),
        ]
        
        for sys_dir in system_dirs:
            if os.path.isdir(sys_dir):
                for root, _, files in os.walk(sys_dir):
                    for f in files:
                        if f.lower().endswith(('.ttf', '.ttc', '.otf')):
                            name = Path(f).stem
                            if name not in font_paths:
                                font_paths[name] = os.path.join(root, f)
        
        return font_paths
    
    def get_font(self, name: str, size: float, 
                 bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
        """Get font by name and properties
        
        Args:
            name: Font family name
            size: Font size in pixels
            bold: Bold weight
            italic: Italic style
            
        Returns:
            PIL ImageFont object
        """
        key = (name, size, bold, italic)
        
        if key in self._cache:
            return self._cache[key]
        
        font = self._load_font(name, size, bold, italic)
        self._cache[key] = font
        return font
    
    def _load_font(self, name: str, size: float,
                   bold: bool, italic: bool) -> ImageFont.FreeTypeFont:
        """Load font with fallback chain"""
        # Try exact match first
        if name in self._font_paths:
            try:
                return ImageFont.truetype(self._font_paths[name], int(size))
            except (IOError, OSError):
                pass
        
        # Try fallbacks
        fallbacks = self.FONT_FALLBACKS.get(name, [])
        for fallback in fallbacks:
            if fallback in self._font_paths:
                try:
                    return ImageFont.truetype(self._font_paths[fallback], int(size))
                except (IOError, OSError):
                    pass
        
        # Try to find any matching font
        for font_name, font_path in self._font_paths.items():
            if name.lower() in font_name.lower():
                try:
                    return ImageFont.truetype(font_path, int(size))
                except (IOError, OSError):
                    pass
        
        # Last resort: default font
        try:
            return ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                int(size)
            )
        except (IOError, OSError):
            # Ultimate fallback
            return ImageFont.load_default()
    
    def clear_cache(self):
        """Clear font cache"""
        self._cache.clear()
