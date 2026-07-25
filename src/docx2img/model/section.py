"""Section and page setup data models"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .enums import SectionType


@dataclass
class ColumnDef:
    """Column definition for multi-column layout"""
    width: float = 0.0         # pt
    space: float = 0.0         # pt


@dataclass
class PageBorderDef:
    """Single side of a page border."""
    style: str = "none"        # none, single, double, dashed, dotted, etc.
    size: int = 0              # border width in 1/8 of pt
    space: int = 0             # spacing from edge in points
    color: Optional[str] = None  # hex color or "auto"


@dataclass
class PageBorders:
    """Page border settings (w:pgBorders)."""
    display: str = "allPages"  # allPages, notFirstPage, firstPage, none
    offset_from: str = "page"  # page, text
    top: PageBorderDef = field(default_factory=PageBorderDef)
    bottom: PageBorderDef = field(default_factory=PageBorderDef)
    left: PageBorderDef = field(default_factory=PageBorderDef)
    right: PageBorderDef = field(default_factory=PageBorderDef)


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
        doc_grid_type: Document grid mode
        doc_grid_line_pitch: Baseline grid pitch in points
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
    title_page: bool = False  # different first page
    # Page numbering
    page_num_start: Optional[int] = None
    # Document grid (w:docGrid).  linePitch only controls vertical flow when
    # type is "lines" or "linesAndChars"; the OOXML default mode is inactive.
    doc_grid_type: str = "default"
    doc_grid_line_pitch: Optional[float] = None
    # Line numbers
    line_numbers: bool = False
    # Cached parsed header/footer bodies (filled by DocumentParser)
    header_bodies: Dict[str, list] = field(default_factory=dict)  # type → blocks
    footer_bodies: Dict[str, list] = field(default_factory=dict)
    # Page borders
    page_borders: Optional[PageBorders] = None
