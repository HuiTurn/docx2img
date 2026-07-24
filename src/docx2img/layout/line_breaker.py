"""Line breaking algorithm for paragraphs"""

import re
from typing import List, Tuple, Any
from PIL import ImageFont

from ..config import Config
from ..model.paragraph import Paragraph, Run, TextRun, ParaProps


# Import these here to avoid circular dependency
def _get_line_box_classes():
    """Lazy import to avoid circular dependency"""
    from .engine import LineBox, GlyphBox
    return LineBox, GlyphBox


class LineBreaker:
    """Line breaking algorithm
    
    Rules:
    1. English: Break at spaces/hyphens (word-level)
    2. CJK: Can break between any characters (char-level)
    3. Mixed: CJK chars can break, Latin words cannot break internally
    4. Punctuation restrictions:
       - Line start cannot have: ，。、；：！？）】》
       - Line end cannot have: （【《
    """
    
    # CJK Unicode ranges
    CJK_RANGES = [
        (0x4E00, 0x9FFF),    # CJK Unified Ideographs
        (0x3400, 0x4DBF),    # CJK Extension A
        (0x3000, 0x303F),    # CJK Symbols and Punctuation
        (0xFF00, 0xFFEF),    # Fullwidth Forms
        (0x3040, 0x309F),    # Hiragana
        (0x30A0, 0x30FF),    # Katakana
        (0xAC00, 0xD7AF),    # Hangul Syllables
    ]
    
    # Characters that cannot appear at line start
    NO_START_CHARS = set("，。、；：！？）】》」』〉,.;:!?)")
    
    # Characters that cannot appear at line end
    NO_END_CHARS = set("（【《「『〈(")
    
    def __init__(self, config: Config):
        self.config = config
    
    def is_cjk(self, ch: str) -> bool:
        """Check if character is CJK"""
        if not ch:
            return False
        cp = ord(ch[0])
        return any(lo <= cp <= hi for lo, hi in self.CJK_RANGES)
    
    def can_break_before(self, ch: str) -> bool:
        """Check if we can break before this character (not at line start)"""
        return ch not in self.NO_START_CHARS
    
    def can_break_after(self, ch: str) -> bool:
        """Check if we can break after this character (not at line end)"""
        return ch not in self.NO_END_CHARS
    
    def break_paragraph(self, para: Paragraph, available_width: float, 
                        px_per_pt: float) -> List[Any]:
        """Break paragraph into lines
        
        Args:
            para: Paragraph to break
            available_width: Available width in pixels
            px_per_pt: Pixels per point conversion factor
            
        Returns:
            List of LineBox objects
        """
        LineBox, _ = _get_line_box_classes()
        lines = []
        
        # Collect all text runs
        text_segments = []
        for run in para.runs:
            if run.text:
                text_segments.append((run.text.text, run.text.props))
            elif run.tab:
                text_segments.append(("\t", None))
            elif run.brk:
                if run.brk.break_type == "line":
                    # Force line break
                    if text_segments:
                        line = self._create_line(text_segments, available_width, px_per_pt)
                        if line:
                            lines.append(line)
                        text_segments = []
        
        # Create final line from remaining segments
        if text_segments:
            line = self._create_line(text_segments, available_width, px_per_pt)
            if line:
                lines.append(line)
        
        return lines
    
    def _create_line(self, segments: List[Tuple[str, Any]], 
                     available_width: float, px_per_pt: float) -> Any:
        """Create a line box from text segments
        
        This is a simplified implementation for P0.
        Full implementation will handle word wrapping and justification.
        """
        LineBox, GlyphBox = _get_line_box_classes()
        line = LineBox()
        
        # For P0, just create a simple line with all text
        full_text = ''.join(seg[0] for seg in segments if seg[0])
        
        if not full_text:
            return line
        
        # Get font from first segment
        props = segments[0][1] if segments[0][1] else None
        font_size = props.font_size if props else 12.0
        font = self._get_font(props, px_per_pt)
        
        # Measure text width
        bbox = font.getbbox(full_text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Create glyph box
        glyph = GlyphBox(
            text=full_text,
            width=text_width,
            height=text_height,
            font=font,
            props=props
        )
        
        line.glyphs.append(glyph)
        line.width = text_width
        line.height = text_height * 1.2  # Include line spacing
        line.ascent = font.getmetrics()[0] if hasattr(font, 'getmetrics') else text_height * 0.8
        line.descent = font.getmetrics()[1] if hasattr(font, 'getmetrics') else text_height * 0.2
        
        return line
    
    def _get_font(self, props, px_per_pt: float) -> ImageFont.FreeTypeFont:
        """Get font for run properties"""
        from ..font.manager import FontManager
        
        font_manager = FontManager(self.config)
        
        if props:
            # Try East Asia font for CJK text
            return font_manager.get_font(
                props.font_east_asia,
                props.font_size * px_per_pt,
                props.bold,
                props.italic
            )
        else:
            return font_manager.get_font(
                self.config.default_font_ascii,
                12.0 * px_per_pt,
                False,
                False
            )
