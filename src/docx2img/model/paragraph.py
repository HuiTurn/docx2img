"""Paragraph and Run data models"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Tuple
from .enums import Alignment, TabStopType

if TYPE_CHECKING:
    from .section import Section


@dataclass
class TabStop:
    """Tab stop definition"""
    position: float          # pt
    type: TabStopType = TabStopType.LEFT
    leader: str = "none"     # none / dot / hyphen / underscore


@dataclass
class RunProps:
    """Run properties (font, color, etc.)
    
    Attributes:
        font_ascii: Font for ASCII characters
        font_east_asia: Font for CJK characters
        font_h_ansi: Font for high-ANSI characters
        font_cs: Font for complex script
        font_size: Font size in points
        bold: Bold text
        italic: Italic text
        underline: Underline enabled
        underline_style: Underline style
        strike: Strikethrough
        double_strike: Double strikethrough
        color: RGB color tuple
        highlight: Highlight color name
        shading: Background color (hex)
        vertical_align: baseline / superscript / subscript
        position_offset: Vertical offset in points
        scale: Character scale percentage
        spacing: Character spacing in points
        small_caps: Small capitals
        all_caps: All capitals
        kern: Kerning in points
        rtl: Right-to-left text
    """
    # Font
    font_ascii: str = "Times New Roman"
    font_east_asia: str = "SimSun"
    font_h_ansi: str = "Times New Roman"
    font_cs: str = "Times New Roman"
    font_size: float = 12.0           # pt
    #字形
    bold: bool = False
    italic: bool = False
    underline: bool = False
    underline_style: str = "single"
    strike: bool = False
    double_strike: bool = False
    # Color
    color: Tuple[int, int, int] = (0, 0, 0)
    highlight: Optional[str] = None    # yellow / green / cyan ...
    shading: Optional[str] = None      # 背景色 hex
    # Position
    vertical_align: str = "baseline"   # baseline / superscript / subscript
    position_offset: float = 0.0       # pt, 正=上移 负=下移
    # Scale/Spacing
    scale: int = 100                   # 百分比
    spacing: float = 0.0              # pt, 字符间距
    # Other
    small_caps: bool = False
    all_caps: bool = False
    kern: float = 0.0                 # pt
    rtl: bool = False                 # 从右到左


@dataclass
class ParaProps:
    """Paragraph properties
    
    Attributes:
        alignment: Text alignment
        space_before: Space before paragraph in points
        space_after: Space after paragraph in points
        line_spacing: Line spacing multiplier
        line_spacing_exact: Exact line spacing in points
        line_spacing_rule: auto / exact / atLeast
        indent_left: Left indent in points
        indent_right: Right indent in points
        first_line_indent: First line indent in points
        hanging_indent: Hanging indent in points
        tab_stops: List of tab stops
        keep_next: Keep with next paragraph
        keep_lines: Keep lines together
        page_break_before: Page break before paragraph
        widow_control: Widow/orphan control
        outline_level: Outline level (for headings)
        num_id: Numbering ID
        num_level: Numbering level
        borders: Border definitions
        shading: Paragraph shading
        style_id: Style reference
        default_tab_stop: Default tab stop interval
    """
    alignment: Alignment = Alignment.LEFT
    space_before: float = 0.0         # pt
    space_after: float = 0.0          # pt
    line_spacing: float = 1.0         # 倍数 (auto)
    line_spacing_exact: Optional[float] = None  # pt (exact/atLeast)
    line_spacing_rule: str = "auto"   # auto / exact / atLeast
    indent_left: float = 0.0          # pt
    indent_right: float = 0.0         # pt
    first_line_indent: float = 0.0    # pt
    hanging_indent: float = 0.0       # pt
    # Character-unit indents (hundredths of a char; resolved against mark size)
    indent_left_chars: Optional[int] = None
    first_line_chars: Optional[int] = None
    hanging_chars: Optional[int] = None
    # Paragraph mark font size (from pPr/rPr/sz or style chain)
    mark_font_size: Optional[float] = None
    # True when space_after comes only from docDefaults (no style chain or
    # direct formatting set it).  LibreOffice suppresses docDefaults-only
    # after-spacing for paragraphs inside table cells.
    space_after_default_only: bool = False
    tab_stops: List[TabStop] = field(default_factory=list)
    keep_next: bool = False
    keep_lines: bool = False
    page_break_before: bool = False
    widow_control: bool = True
    outline_level: Optional[int] = None
    # Numbering
    num_id: Optional[int] = None
    num_level: int = 0
    # Borders
    borders: dict = field(default_factory=dict)
    shading: Optional[str] = None
    # Style reference
    style_id: str = ""
    # Tab stops
    default_tab_stop: float = 36.0    # pt


@dataclass
class TextRun:
    """Text run"""
    text: str
    props: RunProps = field(default_factory=RunProps)


@dataclass
class ImageRun:
    """Image run
    
    Attributes:
        media_ref: Media reference ID (rId)
        data: Image bytes
        width_emu: Width in EMU
        height_emu: Height in EMU
        wrap_type: Wrap type
        pos_x: X position for floating images
        pos_y: Y position for floating images
        relative_x: Relative positioning for X
        relative_y: Relative positioning for Y
    """
    media_ref: str                     # rId
    data: Optional[bytes] = None
    width_emu: int = 0
    height_emu: int = 0
    wrap_type: str = "inline"
    # Floating position (non-inline)
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    relative_x: str = "column"
    relative_y: str = "paragraph"


@dataclass
class TextBoxRun:
    """Floating / inline text box with nested paragraphs."""
    paragraphs: List["Paragraph"] = field(default_factory=list)
    width_emu: int = 0
    height_emu: int = 0
    pos_x: float = 0.0  # pt
    pos_y: float = 0.0  # pt
    wrap_type: str = "square"
    fill: Optional[tuple] = None
    border_color: Optional[tuple] = None


@dataclass
class MathRun:
    """Math formula run (OMML)"""
    ast: object = None                 # MathNode AST


@dataclass
class BreakRun:
    """Break (line/page/column)"""
    break_type: str = "line"           # line / page / column / textWrapping


@dataclass
class TabRun:
    """Tab character"""
    pass


@dataclass
class Run:
    """Run union type
    
    Contains one of: text, image, math, break, tab, or textbox
    """
    text: Optional[TextRun] = None
    image: Optional[ImageRun] = None
    math: Optional[MathRun] = None
    brk: Optional[BreakRun] = None
    tab: Optional[TabRun] = None
    textbox: Optional[TextBoxRun] = None


@dataclass
class Paragraph:
    """Paragraph model

    Attributes:
        runs: List of runs
        props: Paragraph properties
        section_break: If this paragraph ends a section (pPr/sectPr)
        group_items: Extra items from WordprocessingGroup (textboxes, lines)
            that are sibling to runs within the same paragraph area.
    """
    runs: List[Run] = field(default_factory=list)
    props: ParaProps = field(default_factory=ParaProps)
    section_break: Optional["Section"] = None
    group_items: List[dict] = field(default_factory=list)  # textbox/line dicts from wpg:wgp
