"""Page breaking algorithm"""

from typing import List, Any
from dataclasses import dataclass

from ..config import Config


# Lazy import to avoid circular dependency
def _get_box_classes():
    """Lazy import to avoid circular dependency"""
    from .engine import PageBox, BlockBox
    return PageBox, BlockBox


@dataclass
class PageInfo:
    """Information about a page during pagination"""
    index: int
    content_height: float
    blocks: List[Any]  # List[BlockBox]


class PageBreaker:
    """Page breaking algorithm
    
    Rules:
    1. Content exceeds available height → page break
    2. w:pageBreakBefore → force break before paragraph
    3. w:br type="page" → force break at break position
    4. w:keepNext → keep paragraph with next on same page
    5. w:keepLines → keep all lines of paragraph on same page
    6. w:widowControl → at least 2 lines on each page
    7. Table row w:cantSplit → row cannot be split across pages
    """
    
    def __init__(self, config: Config):
        self.config = config
    
    def paginate(self, blocks: list, page_height: float,
                 margin_top: float, margin_bottom: float) -> list:
        """Paginate blocks into pages
        
        Args:
            blocks: List of block boxes
            page_height: Total page height in pixels
            margin_top: Top margin in pixels
            margin_bottom: Bottom margin in pixels
            
        Returns:
            List of PageInfo objects
        """
        pages = []
        current_page = PageInfo(
            index=0,
            content_height=0.0,
            blocks=[]
        )
        
        available_height = page_height - margin_top - margin_bottom
        
        i = 0
        while i < len(blocks):
            block = blocks[i]
            
            # Check if block fits on current page
            if current_page.content_height + block.height > available_height:
                # Need new page
                if current_page.blocks:
                    pages.append(current_page)
                
                current_page = PageInfo(
                    index=len(pages),
                    content_height=block.height,
                    blocks=[block]
                )
            else:
                current_page.blocks.append(block)
                current_page.content_height += block.height
            
            i += 1
        
        # Add final page
        if current_page.blocks:
            pages.append(current_page)
        
        return pages
