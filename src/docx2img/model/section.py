"""Section and page setup data models"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from .enums import SectionType


@dataclass
class ColumnDef:
    """Column definition for multi-column layout"""
    width: float = 0.0         # pt
    space: float = 0.0         # pt


@dataclass
class Section:
    """Section/page definition
    
    Attributes:
        page_w: Page width in points (A4 = 595pt)
        page_h: Page height in points (A4 = 842pt)
        margin_top: Top margin in points
        margin_bottom: Bottom margin in points
        margin_left: Left margin in points
        margin_right: Right margin in points
        header_distance: Header distance from edge
        footer_distance: Footer distance from edge
        gutter: Gutter margin for binding
        orientation: portrait / landscape
        columns: Column definitions
        col_equal_width: Use equal column widths
        col_count: Number of columns
        col_space: Space between columns
        col_sep: Show separator line between columns
        section_type: Section break type
        header_refs: Header references {type: rId}
        footer_refs: Footer references {type: rId}
        page_num_start: Starting page number
        line_numbers: Enable line numbering
    """
    # Page
    page_w: float = 595.0      # pt (A4)
    page_h: float = 842.0
    margin_top: float = 72.0
    margin_bottom: float = 72.0
    margin_left: float = 90.0
    margin_right: float = 90.0
    header_distance: float = 36.0
    footer_distance: float = 36.0
    gutter: float = 0.0
    orientation: str = "portrait"  # portrait / landscape
    # Columns
    columns: List[ColumnDef] = field(default_factory=list)
    col_equal_width: bool = True
    col_count: int = 1
    col_space: float = 36.0    # pt
    col_sep: bool = False      # 栏间分隔线
    # Section type
    section_type: SectionType = SectionType.NEXT_PAGE
    # Header/footer references
    header_refs: Dict[str, str] = field(default_factory=dict)  # type → rId
    footer_refs: Dict[str, str] = field(default_factory=dict)
    # Page numbering
    page_num_start: Optional[int] = None
    # Line numbers
    line_numbers: bool = False
