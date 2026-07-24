"""Layout engine - Converts IR to layout tree with pages"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from PIL import ImageFont

from ..config import Config
from ..model.document import DocumentModel
from ..model.paragraph import Paragraph, Run, TextRun, BreakRun, TabRun, ParaProps
from ..model.table import Table, Row, Cell
from ..model.section import Section
from .line_breaker import LineBreaker
from .page_breaker import PageBreaker


@dataclass
class GlyphBox:
    """Represents a rendered glyph (character or run segment)
    
    Attributes:
        text: Text content
        x: X position in pixels
        y: Y position in pixels (baseline)
        width: Width in pixels
        height: Height in pixels
        font: Font object
        props: Run properties
    """
    text: str
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    font: Any = None
    props: Any = None


@dataclass
class LineBox:
    """Represents a line of text
    
    Attributes:
        glyphs: List of glyph boxes
        x: X position
        y: Y position (baseline of first line)
        width: Total width
        height: Line height
        ascent: Ascent from baseline
        descent: Descent from baseline
    """
    glyphs: List[GlyphBox] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0


@dataclass
class BlockBox:
    """Represents a block element (paragraph or table)
    
    Attributes:
        lines: List of line boxes (for paragraphs)
        cells: List of cell boxes (for tables)
        x: X position
        y: Y position
        width: Width
        height: Height
        element: Original paragraph or table
    """
    lines: List[LineBox] = field(default_factory=list)
    cells: List[Any] = field(default_factory=list)  # CellBox
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    element: Any = None  # Paragraph or Table


@dataclass
class PageBox:
    """Represents a page
    
    Attributes:
        blocks: List of block boxes on this page
        width: Page width in pixels
        height: Page height in pixels
        margin_top: Top margin in pixels
        margin_bottom: Bottom margin in pixels
        margin_left: Left margin in pixels
        margin_right: Right margin in pixels
        section: Source section
    """
    blocks: List[BlockBox] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    margin_top: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0
    margin_right: float = 0.0
    section: Section = None


class LayoutEngine:
    """Main layout engine
    
    Converts DocumentModel to list of PageBox objects
    """
    
    def __init__(self, document: DocumentModel, config: Config):
        self.document = document
        self.config = config
        self.line_breaker = LineBreaker(config)
        self.page_breaker = PageBreaker(config)
    
    def layout(self) -> List[PageBox]:
        """Perform layout and return list of pages"""
        pages = []
        
        # Get first section for now (multi-section support later)
        section = self.document.sections[0] if self.document.sections else Section()
        
        # Convert section to page dimensions in pixels
        px_per_pt = self.config.px_per_pt
        
        page_width = section.page_w * px_per_pt
        page_height = section.page_h * px_per_pt
        margin_top = section.margin_top * px_per_pt
        margin_bottom = section.margin_bottom * px_per_pt
        margin_left = section.margin_left * px_per_pt
        margin_right = section.margin_right * px_per_pt
        
        content_width = page_width - margin_left - margin_right
        available_height = page_height - margin_top - margin_bottom
        
        # Create page box
        page = PageBox(
            width=page_width,
            height=page_height,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            margin_right=margin_right,
            section=section
        )
        
        current_y = margin_top
        
        # Process each block element
        for block in self.document.body:
            if isinstance(block, Paragraph):
                block_box = self._layout_paragraph(block, margin_left, content_width, px_per_pt)
            elif isinstance(block, Table):
                block_box = self._layout_table(block, margin_left, content_width, px_per_pt)
            else:
                continue
            
            block_box.y = current_y
            
            # Check for page break
            if current_y + block_box.height > page_height - margin_bottom:
                # Need new page (simplified - full page break logic in PageBreaker)
                pages.append(page)
                page = PageBox(
                    width=page_width,
                    height=page_height,
                    margin_top=margin_top,
                    margin_bottom=margin_bottom,
                    margin_left=margin_left,
                    margin_right=margin_right,
                    section=section
                )
                current_y = margin_top
                block_box.y = current_y
            
            page.blocks.append(block_box)
            current_y += block_box.height
        
        # Add final page if it has content
        if page.blocks:
            pages.append(page)
        
        # If no pages created, add empty page
        if not pages:
            pages.append(page)
        
        return pages
    
    def _layout_paragraph(self, para: Paragraph, x_offset: float, 
                          content_width: float, px_per_pt: float) -> BlockBox:
        """Layout a paragraph into line boxes"""
        block = BlockBox(element=para)
        
        # Convert paragraph properties to pixels
        props = para.props
        indent_left = props.indent_left * px_per_pt
        indent_right = props.indent_right * px_per_pt
        first_line_indent = props.first_line_indent * px_per_pt
        
        available_width = content_width - indent_left - indent_right
        
        # Break paragraph into lines
        lines = self.line_breaker.break_paragraph(para, available_width, px_per_pt)
        
        # Calculate line positions
        current_x = x_offset + indent_left
        current_y = 0.0  # Will be set by page breaker
        
        # Handle first line indent
        if lines:
            lines[0].x = current_x + first_line_indent * px_per_pt
        
        for i, line in enumerate(lines):
            if i > 0:
                line.x = current_x
            
            line.y = current_y
            current_y += line.height
        
        block.lines = lines
        
        # Calculate block dimensions
        if lines:
            block.width = max(line.width + line.x - current_x for line in lines)
            block.height = current_y
        else:
            # Empty paragraph still has some height
            block.height = 12 * px_per_pt  # Default line height
        
        # Add spacing
        block.height += props.space_before * px_per_pt
        block.height += props.space_after * px_per_pt
        
        return block
    
    def _layout_table(self, table: Table, x_offset: float,
                      content_width: float, px_per_pt: float) -> BlockBox:
        """Layout a table (simplified for P0)"""
        block = BlockBox(element=table)
        
        # For P0, just create a placeholder block
        # Full table layout in P2
        block.x = x_offset
        block.width = content_width
        block.height = 20 * px_per_pt  # Placeholder
        
        return block
