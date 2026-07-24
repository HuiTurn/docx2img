"""Table data models"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any
from .paragraph import Paragraph
from .enums import BorderStyle, VerticalMerge


@dataclass
class BorderDef:
    """Border definition"""
    style: BorderStyle = BorderStyle.SINGLE
    width: float = 0.5  # pt
    color: tuple = (0, 0, 0)
    space: float = 0.0  # pt


@dataclass
class CellProps:
    """Table cell properties"""
    width: float = 0.0  # pt
    width_type: str = "dxa"  # dxa / pct / auto
    grid_span: int = 1
    v_merge: VerticalMerge = VerticalMerge.NONE
    shading: Optional[tuple] = None  # RGB
    borders: Dict[str, BorderDef] = field(default_factory=dict)
    vertical_align: str = "top"  # top / center / bottom
    margins: Dict[str, float] = field(default_factory=dict)  # pt
    no_wrap: bool = False


@dataclass
class Cell:
    """Table cell — content may include paragraphs and nested tables."""
    blocks: List[Any] = field(default_factory=list)  # Paragraph | Table
    props: CellProps = field(default_factory=CellProps)

    @property
    def paragraphs(self) -> List[Paragraph]:
        from .paragraph import Paragraph as P
        return [b for b in self.blocks if isinstance(b, P)]


@dataclass
class Row:
    """Table row"""
    cells: List[Cell] = field(default_factory=list)
    height: float = 0.0  # pt
    height_rule: str = "auto"  # auto / atLeast / exact
    is_header: bool = False
    cant_split: bool = False


@dataclass
class TableProps:
    """Table properties"""
    width: float = 0.0  # pt
    width_type: str = "auto"
    alignment: str = "left"
    indent: float = 0.0  # pt
    borders: Dict[str, BorderDef] = field(default_factory=dict)
    cell_spacing: float = 0.0  # pt
    layout: str = "autofit"  # fixed / autofit
    style_id: str = ""
    cell_margins: Dict[str, float] = field(default_factory=dict)  # default tcMar


@dataclass
class Table:
    """Table model"""
    rows: List[Row] = field(default_factory=list)
    col_widths: List[float] = field(default_factory=list)  # pt from tblGrid
    props: TableProps = field(default_factory=TableProps)
