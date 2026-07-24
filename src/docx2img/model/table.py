"""Table data models"""

from dataclasses import dataclass, field
from typing import List, Optional
from .paragraph import Paragraph
from .enums import BorderStyle, VerticalMerge


@dataclass
class BorderDef:
    """Border definition"""
    style: BorderStyle = BorderStyle.SINGLE
    width: float = 0.5         # pt (sz/8)
    color: tuple = (0, 0, 0)
    space: float = 0.0         # pt


@dataclass
class CellProps:
    """Table cell properties"""
    width: float = 0.0         # pt
    width_type: str = "dxa"    # dxa / pct / auto
    grid_span: int = 1
    v_merge: VerticalMerge = VerticalMerge.NONE
    shading: Optional[str] = None
    borders: dict = field(default_factory=dict)  # top/bottom/left/right
    vertical_align: str = "top"  # top / center / bottom
    margins: dict = field(default_factory=dict)  # top/bottom/left/right pt
    no_wrap: bool = False


@dataclass
class Cell:
    """Table cell"""
    paragraphs: List[Paragraph] = field(default_factory=list)
    props: CellProps = field(default_factory=CellProps)


@dataclass
class Row:
    """Table row"""
    cells: List[Cell] = field(default_factory=list)
    height: float = 0.0        # pt
    height_rule: str = "atLeast"  # auto / atLeast / exact
    is_header: bool = False
    cant_split: bool = False


@dataclass
class TableProps:
    """Table properties"""
    width: float = 0.0         # pt
    width_type: str = "dxa"
    alignment: str = "left"
    indent: float = 0.0        # pt
    borders: dict = field(default_factory=dict)
    cell_spacing: float = 0.0  # pt
    layout: str = "fixed"      # fixed / autofit
    style_id: str = ""


@dataclass
class Table:
    """Table model"""
    rows: List[Row] = field(default_factory=list)
    col_widths: List[float] = field(default_factory=list)  # pt
    props: TableProps = field(default_factory=TableProps)
