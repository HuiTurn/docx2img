"""Document model - Top-level IR container"""

from dataclasses import dataclass, field
from typing import List, Dict, Union, Optional
from .paragraph import Paragraph, RunProps, ParaProps
from .table import Table
from .section import Section
from .style import StyleTable
from .numbering import NumberingTable


@dataclass
class DocumentModel:
    """Complete document intermediate representation
    
    Attributes:
        body: List of block elements (paragraphs and tables)
        sections: List of sections
        styles: Style table
        numbering: Numbering table
        media: Media files {rId: bytes}
        headers: Headers {rId: body elements}
        footers: Footers {rId: body elements}
        default_run_props: Default run properties
        default_para_props: Default paragraph properties
        theme_colors: Theme color definitions
        theme_fonts: Theme font definitions
    """
    body: List[Union[Paragraph, Table]] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    styles: StyleTable = field(default_factory=StyleTable)
    numbering: NumberingTable = field(default_factory=NumberingTable)
    media: Dict[str, bytes] = field(default_factory=dict)
    headers: Dict[str, List] = field(default_factory=dict)  # rId → body
    footers: Dict[str, List] = field(default_factory=dict)
    default_run_props: Optional[RunProps] = None
    default_para_props: Optional[ParaProps] = None
    theme_colors: dict = field(default_factory=dict)
    theme_fonts: dict = field(default_factory=dict)
