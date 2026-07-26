# DocX → Image Pure Python Rendering Engine · Complete Technical Design

> **Version**: v1.0 | **Date**: 2026-07-24
> **Constraint**: Only supports `.docx` (OOXML), not `.doc` (OLE2)
> **Dependencies**: `Pillow` (rendering) + Python standard library (`zipfile` / `xml.etree` / `struct` / `io` / `re`)

---

## 1. Overall Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        docx2img CLI / API                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌──────────┐  │
│  │ ① Unpack  │──▶│ ② Parse   │──▶│ ③ Layout  │──▶│ ④ Render │  │
│  │  Layer    │   │  Layer    │   │  Engine   │   │  Layer   │  │
│  └───────────┘   └───────────┘   └───────────┘   └──────────┘  │
│       │               │               │               │         │
│   zipfile         xml.etree      custom engine     Pillow       │
│   unzip ZIP       XML → IR       IR → pixels      pixels → PNG  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  ⑤ Font Manager                                                 │
│  ⑥ Style Resolver                                               │
│  ⑦ Numbering Engine                                             │
│  ⑧ Image / Graphics Resolver                                    │
│  ⑨ Math Engine (OMML)                                           │
├─────────────────────────────────────────────────────────────────┤
│  ⑩ Config & Logging & Test Framework                            │
└─────────────────────────────────────────────────────────────────┘
```

### Core Data Flow

```
.docx (ZIP)
  │
  ▼
DocumentModel (IR - Intermediate Representation)
  │  ├── Section[]        page/section
  │  ├── StyleTable       style table
  │  ├── NumberingTable   numbering definitions
  │  ├── MediaStore       images/resources
  │  └── Body[]           content block sequence
  │       ├── Paragraph
  │       │    ├── ParaProps (align/indent/spacing/line-spacing)
  │       │    └── Run[]
  │       │         ├── TextRun (text + RunProps)
  │       │         ├── ImageRun (media_ref + size)
  │       │         ├── MathRun (OMML AST)
  │       │         └── BreakRun (tab / br / page_break)
  │       ├── Table
  │       │    ├── TableProps (width/align/borders)
  │       │    ├── ColGrid[]
  │       │    └── Row[] → Cell[] → Paragraph[]
  │       └── SdtBlock (structured document tags)
  │
  ▼
LayoutTree (layout tree)
  │  ├── Page[]
  │  │    ├── Block[]
  │  │    │    ├── LineBox[]  (paragraph lines)
  │  │    │    │    └── GlyphBox[] (chars/images/math)
  │  │    │    └── TableBox
  │  │    │         └── CellBox[] → LineBox[]
  │  │    ├── HeaderBox
  │  │    └── FooterBox
  │
  ▼
Pixel Canvas (Pillow Image)
  │
  ▼
PNG / JPEG / TIFF
```

---

## 2. Project Structure

```
docx2img/
├── pyproject.toml
├── requirements.txt              # Pillow>=10.0
├── README.md
│
├── src/
│   └── docx2img/
│       ├── __init__.py
│       ├── cli.py                # CLI entry point
│       ├── api.py                # Python API
│       ├── config.py             # Global config (DPI/font paths/color maps)
│       │
│       ├── unpack/               # ① Unpack layer
│       │   ├── __init__.py
│       │   └── unpacker.py       # ZIP extraction + file manifest
│       │
│       ├── parse/                # ② Parse layer (XML → IR)
│       │   ├── __init__.py
│       │   ├── namespaces.py     # OOXML namespace constants
│       │   ├── units.py          # Unit conversion (twips/EMU/half-pt/pt/px)
│       │   ├── document.py       # document.xml main parser
│       │   ├── paragraph.py      # paragraph/run parser
│       │   ├── table.py          # table parser
│       │   ├── drawing.py        # DrawingML / images / shapes
│       │   ├── math_omml.py      # OMML math parser
│       │   ├── styles.py         # styles.xml parser
│       │   ├── theme.py          # theme1.xml parser
│       │   ├── numbering.py      # numbering.xml parser
│       │   ├── section.py        # sectPr page/section parser
│       │   ├── header_footer.py  # header/footer XML parser
│       │   ├── rels.py           # .rels relationship mapping
│       │   └── sdt.py            # Structured Document Tags
│       │
│       ├── model/                # IR data model
│       │   ├── __init__.py
│       │   ├── document.py       # DocumentModel
│       │   ├── paragraph.py      # Paragraph / Run / RunProps / ParaProps
│       │   ├── table.py          # Table / Row / Cell
│       │   ├── drawing.py        # Image / Shape / Chart
│       │   ├── math_ast.py       # Math AST nodes
│       │   ├── style.py          # Style / StyleTable
│       │   ├── numbering.py      # NumberingDef / LevelDef
│       │   ├── section.py        # Section / PageSetup
│       │   └── enums.py          # Enums (align/border/numbering format/...)
│       │
│       ├── layout/               # ③ Layout layer
│       │   ├── __init__.py
│       │   ├── engine.py         # layout main engine
│       │   ├── line_breaker.py   # line breaking algorithm
│       │   ├── page_breaker.py   # pagination algorithm
│       │   ├── table_layout.py   # table grid calculation
│       │   ├── list_layout.py    # list numbering layout
│       │   ├── column_layout.py  # multi-column layout
│       │   ├── float_layout.py   # floating elements / text wrap
│       │   ├── textbox_layout.py # text box layout
│       │   ├── math_layout.py    # math layout
│       │   ├── tab_stop.py       # tab stop calculation
│       │   └── justify.py        # justify algorithm
│       │
│       ├── render/               # ④ Render layer
│       │   ├── __init__.py
│       │   ├── canvas.py         # Pillow canvas wrapper
│       │   ├── text_renderer.py  # text rendering (with glyph selection)
│       │   ├── table_renderer.py # table rendering (borders/bg/merge)
│       │   ├── image_renderer.py # image rendering
│       │   ├── shape_renderer.py # shape rendering (rect/ellipse/line/arrow)
│       │   ├── math_renderer.py  # math rendering
│       │   ├── border_renderer.py# border rendering (single/double/dashed/dotted)
│       │   ├── bullet_renderer.py# list bullet rendering
│       │   └── effects.py        # shadow/highlight/shading
│       │
│       ├── font/                 # ⑤ Font management
│       │   ├── __init__.py
│       │   ├── manager.py        # font lookup/loading/caching
│       │   ├── fallback.py       # font fallback chain
│       │   ├── metrics.py        # font metrics (ascent/descent/linegap)
│       │   └── embedded.py       # embedded font extraction (fontTable.xml)
│       │
│       ├── style/                # ⑥ Style system
│       │   ├── __init__.py
│       │   ├── resolver.py       # style inheritance chain resolution
│       │   ├── defaults.py       # docDefaults / implicit defaults
│       │   └── theme_resolver.py # theme color/font resolution
│       │
│       └── utils/
│           ├── __init__.py
│           ├── color.py          # color parsing (hex/theme/auto)
│           ├── cache.py          # LRU cache
│           └── log.py            # logging
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/                 # test .docx files
│   │   ├── basic_text.docx
│   │   ├── styled_text.docx
│   │   ├── tables.docx
│   │   ├── images.docx
│   │   ├── headers_footers.docx
│   │   ├── lists.docx
│   │   ├── columns.docx
│   │   ├── math.docx
│   │   ├── textboxes.docx
│   │   └── complex_mixed.docx
│   ├── test_parse/
│   ├── test_layout/
│   ├── test_render/
│   └── test_e2e/
│
├── fonts/                        # bundled fonts
│   ├── simsun.ttc
│   ├── simhei.ttf
│   ├── times.ttf
│   └── arial.ttf
│
└── docs/
    ├── architecture.md
    ├── ooxml_reference.md        # OOXML structure quick reference
    └── iteration_plan.md         # iteration plan
```

---

## 3. IR Data Model (Complete Definition)

```python
# model/enums.py
from enum import Enum

class Alignment(Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"
    DISTRIBUTE = "distribute"

class BorderStyle(Enum):
    NONE = "none"
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    THICK = "thick"
    DASHED = "dashed"
    DOTTED = "dotted"
    WAVE = "wave"

class NumberFormat(Enum):
    DECIMAL = "decimal"           # 1, 2, 3
    UPPER_LETTER = "upperLetter"  # A, B, C
    LOWER_LETTER = "lowerLetter"  # a, b, c
    UPPER_ROMAN = "upperRoman"    # I, II, III
    LOWER_ROMAN = "lowerRoman"    # i, ii, iii
    BULLET = "bullet"             # •
    CHINESE_COUNTING = "chineseCounting"  # CJK counting
    IDEOGRAPH_DIGITAL = "ideographDigital"
    NONE = "none"

class TabStopType(Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    DECIMAL = "decimal"

class VerticalMerge(Enum):
    RESTART = "restart"
    CONTINUE = "continue"
    NONE = "none"

class WrapType(Enum):
    INLINE = "inline"
    SQUARE = "square"
    TIGHT = "tight"
    TOP_BOTTOM = "topAndBottom"
    BEHIND = "behind"
    IN_FRONT = "inFrontOf"

class SectionType(Enum):
    NEXT_PAGE = "nextPage"
    CONTINUOUS = "continuous"
    EVEN_PAGE = "evenPage"
    ODD_PAGE = "oddPage"
```

```python
# model/paragraph.py
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from .enums import Alignment, TabStopType

@dataclass
class TabStop:
    position: float          # pt
    type: TabStopType = TabStopType.LEFT
    leader: str = "none"     # none / dot / hyphen / underscore

@dataclass
class RunProps:
    # Font
    font_ascii: str = "Times New Roman"
    font_east_asia: str = "SimSun"
    font_h_ansi: str = "Times New Roman"
    font_cs: str = "Times New Roman"
    font_size: float = 12.0           # pt
    # Glyph style
    bold: bool = False
    italic: bool = False
    underline: bool = False
    underline_style: str = "single"
    strike: bool = False
    double_strike: bool = False
    # Color
    color: Tuple[int, int, int] = (0, 0, 0)
    highlight: Optional[str] = None    # yellow / green / cyan ...
    shading: Optional[str] = None      # background color hex
    # Position
    vertical_align: str = "baseline"   # baseline / superscript / subscript
    position_offset: float = 0.0       # pt, positive=raise, negative=lower
    # Scale / spacing
    scale: int = 100                   # percentage
    spacing: float = 0.0              # pt, character spacing
    # Other
    small_caps: bool = False
    all_caps: bool = False
    kern: float = 0.0                 # pt
    rtl: bool = False                 # right-to-left

@dataclass
class ParaProps:
    alignment: Alignment = Alignment.LEFT
    space_before: float = 0.0         # pt
    space_after: float = 0.0          # pt
    line_spacing: float = 1.0         # multiplier (auto)
    line_spacing_exact: Optional[float] = None  # pt (exact/atLeast)
    line_spacing_rule: str = "auto"   # auto / exact / atLeast
    indent_left: float = 0.0          # pt
    indent_right: float = 0.0         # pt
    first_line_indent: float = 0.0    # pt
    hanging_indent: float = 0.0       # pt
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
    text: str
    props: RunProps = field(default_factory=RunProps)

@dataclass
class ImageRun:
    media_ref: str                     # rId
    data: Optional[bytes] = None
    width_emu: int = 0
    height_emu: int = 0
    wrap_type: str = "inline"
    # Float positioning (when not inline)
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    relative_x: str = "column"
    relative_y: str = "paragraph"

@dataclass
class MathRun:
    ast: object = None                 # MathNode AST

@dataclass
class BreakRun:
    break_type: str = "line"           # line / page / column / textWrapping

@dataclass
class TabRun:
    pass

@dataclass
class Run:
    """Run union type"""
    text: Optional[TextRun] = None
    image: Optional[ImageRun] = None
    math: Optional[MathRun] = None
    brk: Optional[BreakRun] = None
    tab: Optional[TabRun] = None

@dataclass
class Paragraph:
    runs: List[Run] = field(default_factory=list)
    props: ParaProps = field(default_factory=ParaProps)
```

```python
# model/table.py
from dataclasses import dataclass, field
from typing import List, Optional
from .paragraph import Paragraph
from .enums import BorderStyle, VerticalMerge

@dataclass
class BorderDef:
    style: BorderStyle = BorderStyle.SINGLE
    width: float = 0.5         # pt (sz/8)
    color: tuple = (0, 0, 0)
    space: float = 0.0         # pt

@dataclass
class CellProps:
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
    paragraphs: List[Paragraph] = field(default_factory=list)
    props: CellProps = field(default_factory=CellProps)

@dataclass
class Row:
    cells: List[Cell] = field(default_factory=list)
    height: float = 0.0        # pt
    height_rule: str = "atLeast"  # auto / atLeast / exact
    is_header: bool = False
    cant_split: bool = False

@dataclass
class TableProps:
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
    rows: List[Row] = field(default_factory=list)
    col_widths: List[float] = field(default_factory=list)  # pt
    props: TableProps = field(default_factory=TableProps)
```

```python
# model/section.py
from dataclasses import dataclass, field
from typing import List, Optional
from .enums import SectionType
from .paragraph import Paragraph

@dataclass
class ColumnDef:
    width: float = 0.0         # pt
    space: float = 0.0         # pt

@dataclass
class Section:
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
    col_sep: bool = False      # column separator line
    # Section type
    section_type: SectionType = SectionType.NEXT_PAGE
    # Header/footer references
    header_refs: dict = field(default_factory=dict)  # type → rId
    footer_refs: dict = field(default_factory=dict)
    # Page number
    page_num_start: Optional[int] = None
    # Line numbers
    line_numbers: bool = False
```

```python
# model/document.py
from dataclasses import dataclass, field
from typing import List, Dict, Union
from .paragraph import Paragraph
from .table import Table
from .section import Section
from .style import StyleTable
from .numbering import NumberingTable

@dataclass
class DocumentModel:
    body: List[Union[Paragraph, Table]] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    styles: StyleTable = field(default_factory=StyleTable)
    numbering: NumberingTable = field(default_factory=NumberingTable)
    media: Dict[str, bytes] = field(default_factory=dict)
    headers: Dict[str, List] = field(default_factory=dict)  # rId → body
    footers: Dict[str, List] = field(default_factory=dict)
    default_run_props: object = None
    default_para_props: object = None
    theme_colors: dict = field(default_factory=dict)
    theme_fonts: dict = field(default_factory=dict)
```

---

## 4. Iteration Roadmap (8 Phases)

```
P0 ─── P1 ─── P2 ─── P3 ─── P4 ─── P5 ─── P6 ─── P7
Basic   Style  Table  Image  Header List   Adv.   Math
Text    System Full   Graph  Footer Num.   Layout OMML
                      Sect.
                      Cols.

Each phase ≈ 1–2 weeks (single developer, full-time)
```

---

### P0 · Basic Text Rendering (Week 1–2)

**Goal**: Correctly render plain-text `.docx` files to PNG.

#### OOXML Structures Involved

```xml
word/document.xml
├── w:body
│   ├── w:p                        paragraph
│   │   ├── w:pPr                  paragraph properties
│   │   │   ├── w:jc               alignment
│   │   │   ├── w:spacing          spacing/line-spacing
│   │   │   ├── w:ind              indent
│   │   │   └── w:pStyle           style reference (P0: record only, no resolve)
│   │   └── w:r                    run
│   │       ├── w:rPr              run properties
│   │       │   ├── w:rFonts       font
│   │       │   ├── w:sz / w:szCs  font size
│   │       │   ├── w:b / w:i      bold/italic
│   │       │   ├── w:u            underline
│   │       │   ├── w:strike       strikethrough
│   │       │   ├── w:color        color
│   │       │   ├── w:highlight    highlight
│   │       │   ├── w:vertAlign    superscript/subscript
│   │       │   ├── w:smallCaps    small caps
│   │       │   ├── w:spacing      character spacing
│   │       │   └── w:position     baseline offset
│   │       ├── w:t                text
│   │       ├── w:tab              tab
│   │       └── w:br               line/page break
│   └── w:sectPr                   page setup
│       ├── w:pgSz                 paper size
│       └── w:pgMar                margins
```

#### Core Algorithm: Line Breaking

```python
# layout/line_breaker.py

class LineBreaker:
    """
    Line breaking strategy:
    1. Latin: break at spaces/hyphens (word-level)
    2. CJK (Chinese/Japanese/Korean): break between any characters (char-level)
    3. Mixed: CJK chars allow breaks between them; Latin words do not break internally
    4. Punctuation rules: certain punctuation cannot start/end a line
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

    NO_START_CHARS = set(",.;:!?)")]}>")
    NO_END_CHARS = set("([{<")

    def is_cjk(self, ch: str) -> bool:
        cp = ord(ch)
        return any(lo <= cp <= hi for lo, hi in self.CJK_RANGES)

    def can_break_before(self, ch: str) -> bool:
        """Whether this character can appear at the start of a line"""
        return ch not in self.NO_START_CHARS

    def can_break_after(self, ch: str) -> bool:
        """Whether a line can break after this character"""
        return ch not in self.NO_END_CHARS

    def break_line(self, runs: list, max_width: int,
                   font_mgr, measure_fn) -> list:
        """
        Input: Run sequence + available width
        Output: [Line] list

        Algorithm:
        1. Expand runs into (char, font, props) sequence
        2. Greedy scan, accumulate width
        3. Break at allowed break points when width exceeded
        4. Handle punctuation rules (backtrack/forward)
        """
        ...
```

#### Core Algorithm: Pagination

```python
# layout/page_breaker.py

class PageBreaker:
    """
    Pagination rules:
    1. Content exceeds page available height → page break
    2. w:pageBreakBefore → forced page break before paragraph
    3. w:br type="page" → inline forced page break
    4. w:keepNext → paragraph stays on same page as next
    5. w:keepLines → all lines in paragraph stay on same page
    6. w:widowControl → widow/orphan control (at least 2 lines on same page)
    7. Table rows: w:cantSplit → row cannot split across pages
    """

    def paginate(self, blocks: list, page_height: int,
                 margin_top: int, margin_bottom: int) -> list:
        ...
```

#### Rendering: Text Drawing

```python
# render/text_renderer.py
from PIL import Image, ImageDraw, ImageFont

class TextRenderer:
    def __init__(self, canvas: Image.Image):
        self.draw = ImageDraw.Draw(canvas)

    def draw_run(self, run, x: int, y: int, font: ImageFont):
        """
        Draw a single run:
        1. Highlight background → draw rectangle first
        2. Text → draw.text()
        3. Underline → draw.line() at baseline + descent
        4. Strikethrough → draw.line() at x-height/2
        5. Superscript/subscript → y offset
        """
        props = run.props

        # Highlight
        if props.highlight:
            hl_color = HIGHLIGHT_COLORS.get(props.highlight, (255, 255, 0))
            bbox = font.getbbox(run.text)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            self.draw.rectangle([x, y, x + w, y + h], fill=hl_color)

        # Text
        self.draw.text((x, y), run.text, font=font, fill=props.color)

        # Underline
        if props.underline:
            bbox = font.getbbox(run.text)
            tw = bbox[2] - bbox[0]
            # baseline position ≈ ascent
            ascent = font.getmetrics()[0]
            uy = y + ascent + 1
            self.draw.line([(x, uy), (x + tw, uy)],
                          fill=props.color, width=max(1, int(props.font_size / 12)))

        # Strikethrough
        if props.strike:
            bbox = font.getbbox(run.text)
            tw = bbox[2] - bbox[0]
            ascent = font.getmetrics()[0]
            sy = y + ascent // 2
            self.draw.line([(x, sy), (x + tw, sy)],
                          fill=props.color, width=1)
```

#### P0 Acceptance Criteria

| Test Item | Expected |
|-----------|----------|
| Plain English paragraph | Correct wrapping, alignment |
| Bold/italic/underline/strikethrough | Visually correct |
| Font size 8pt–72pt | Correct dimensions |
| Color/highlight | Correct colors |
| Superscript/subscript | Correct position offset |
| Left/center/right alignment | Correct positions |
| First-line indent (2 chars) | Correct indent |
| Space before/after | Correct spacing |
| Line spacing 1.0/1.5/2.0/fixed | Correct line height |
| Forced page break (Ctrl+Enter) | Correct pagination |
| A4 / Letter / custom paper | Correct page dimensions |
| Landscape page | Swapped width/height |

---

### P1 · Style System (Week 3)

**Goal**: Fully support `styles.xml` + `theme1.xml` style inheritance.

#### Files Involved

```
word/styles.xml
├── w:docDefaults
│   ├── w:rPrDefault → w:rPr     global default run properties
│   └── w:pPrDefault → w:pPr     global default paragraph properties
├── w:style (type="paragraph")    paragraph style
│   ├── w:styleId
│   ├── w:name
│   ├── w:basedOn                 inherit parent style
│   ├── w:next                    next paragraph default style
│   ├── w:pPr
│   └── w:rPr
├── w:style (type="character")    character style
├── w:style (type="table")        table style
└── w:style (type="numbering")    numbering style

word/theme/theme1.xml
├── a:clrScheme                   theme colors (dk1/lt1/dk2/lt2/accent1~6/hlink/folHlink)
├── a:fontScheme                  theme fonts (majorFont/minorFont)
└── a:fmtScheme                   format scheme
```

#### Style Resolution Priority (low to high)

```
docDefaults (global defaults)
  ↓ overrides
basedOn chain (grandparent → parent)
  ↓ overrides
current style (w:pStyle / w:rStyle reference)
  ↓ overrides
direct formatting (w:pPr / w:rPr on paragraph/run)
```

#### Core Implementation

```python
# style/resolver.py

class StyleResolver:
    def __init__(self, style_table: StyleTable, theme: dict,
                 default_rpr: RunProps, default_ppr: ParaProps):
        self.styles = style_table
        self.theme = theme
        self.default_rpr = default_rpr
        self.default_ppr = default_ppr
        self._cache = {}

    def resolve_para(self, style_id: str, direct: ParaProps) -> ParaProps:
        """Resolve final paragraph properties"""
        chain = self._build_chain(style_id)
        result = self._clone(self.default_ppr)
        for sid in chain:
            style = self.styles.get(sid)
            if style and style.ppr:
                result = self._merge_ppr(result, style.ppr)
        result = self._merge_ppr(result, direct)
        return result

    def resolve_run(self, style_id: str, para_style_id: str,
                    direct: RunProps) -> RunProps:
        """Resolve final run properties"""
        result = self._clone(self.default_rpr)
        # rPr from paragraph style chain
        chain = self._build_chain(para_style_id)
        for sid in chain:
            style = self.styles.get(sid)
            if style and style.rpr:
                result = self._merge_rpr(result, style.rpr)
        # Character style
        if style_id:
            chain2 = self._build_chain(style_id)
            for sid in chain2:
                style = self.styles.get(sid)
                if style and style.rpr:
                    result = self._merge_rpr(result, style.rpr)
        # Direct formatting
        result = self._merge_rpr(result, direct)
        # Theme font substitution
        result = self._apply_theme_fonts(result)
        return result

    def _build_chain(self, style_id: str) -> list:
        """Build basedOn inheritance chain (root to leaf)"""
        chain = []
        visited = set()
        sid = style_id
        while sid and sid not in visited:
            visited.add(sid)
            chain.append(sid)
            style = self.styles.get(sid)
            sid = style.based_on if style else None
        chain.reverse()
        return chain

    def _apply_theme_fonts(self, props: RunProps) -> RunProps:
        """Replace +mj-lt / +mn-lt / +mj-ea / +mn-ea with theme fonts"""
        theme_map = {
            "+mj-lt": self.theme.get("major_latin", "Cambria"),
            "+mn-lt": self.theme.get("minor_latin", "Calibri"),
            "+mj-ea": self.theme.get("major_ea", ""),
            "+mn-ea": self.theme.get("minor_ea", ""),
        }
        if props.font_ascii in theme_map:
            props.font_ascii = theme_map[props.font_ascii]
        if props.font_east_asia in theme_map:
            props.font_east_asia = theme_map[props.font_east_asia]
        return props
```

#### Theme Color Resolution

```python
# style/theme_resolver.py

class ThemeResolver:
    """
    Parse a:clrScheme from theme1.xml
    Color reference methods:
    - Direct hex: w:color val="FF0000"
    - Theme color: w:color w:themeColor="accent1"
    - Theme color + tint: w:color w:themeColor="accent1" w:themeTint="BF"
    - Theme color + shade: w:color w:themeColor="dk1" w:themeShade="80"
    """

    def resolve_color(self, hex_val=None, theme_color=None,
                      tint=None, shade=None) -> tuple:
        if hex_val and hex_val != 'auto':
            return self._hex_to_rgb(hex_val)
        if theme_color:
            base = self.theme_colors.get(theme_color, (0, 0, 0))
            if tint:
                base = self._apply_tint(base, int(tint, 16) / 255.0)
            if shade:
                base = self._apply_shade(base, int(shade, 16) / 255.0)
            return base
        return (0, 0, 0)

    def _apply_tint(self, rgb, factor):
        """Blend toward white"""
        return tuple(int(c + (255 - c) * factor) for c in rgb)

    def _apply_shade(self, rgb, factor):
        """Blend toward black"""
        return tuple(int(c * factor) for c in rgb)
```

#### P1 Acceptance Criteria

| Test Item | Expected |
|-----------|----------|
| Heading 1–9 styles | Correct font size/bold/color/spacing |
| Normal style modification | Global default font changes |
| basedOn three-level inheritance | Properties correctly inherited + overridden |
| Theme colors accent1–6 | Correct colors |
| Theme fonts majorFont/minorFont | Correct fonts |
| Character styles (e.g. Emphasis) | Correct italic etc. |
| Direct format overrides style | Priority correct |

---

### P2 · Full Table Support (Week 4–5)

**Goal**: Support complex tables including merged cells, nested tables, table styles.

#### OOXML Structures Involved

```xml
w:tbl
├── w:tblPr
│   ├── w:tblW              table width
│   ├── w:jc                table alignment
│   ├── w:tblInd            table indent
│   ├── w:tblBorders        table borders (6 sides)
│   ├── w:tblCellSpacing    cell spacing
│   ├── w:tblLayout         fixed / autofit
│   ├── w:tblStyle          table style reference
│   └── w:tblLook           conditional formatting flags
├── w:tblGrid
│   └── w:gridCol[]         column definitions
├── w:tr
│   ├── w:trPr
│   │   ├── w:trHeight      row height
│   │   ├── w:tblHeader     header row
│   │   ├── w:cantSplit     cannot split across pages
│   │   └── w:trStyle
│   └── w:tc
│       ├── w:tcPr
│       │   ├── w:tcW       cell width
│       │   ├── w:gridSpan  horizontal merge
│       │   ├── w:vMerge    vertical merge
│       │   ├── w:tcBorders cell borders
│       │   ├── w:shd       background color
│       │   ├── w:vAlign    vertical alignment
│       │   ├── w:tcMar     cell margins
│       │   └── w:noWrap    no wrap
│       ├── w:p[]           cell content (paragraphs)
│       └── w:tbl           nested table!
```

#### Core Algorithm: Table Grid Calculation

```python
# layout/table_layout.py

class TableLayoutEngine:
    """
    Table layout algorithm (based on CSS table layout + OOXML spec):

    1. Determine column widths
       - fixed layout: use gridCol widths from tblGrid directly
       - autofit layout: compute from content (similar to CSS auto)
       - percentage width: convert based on total table width

    2. Handle merges
       - gridSpan: horizontal merge, spans multiple columns
       - vMerge restart/continue: vertical merge
       - Build logical grid → physical grid mapping

    3. Calculate row heights
       - Each row height = max(all cell content heights, trHeight)
       - heightRule: auto / atLeast / exact

    4. Cross-page splitting
       - cantSplit rows do not split
       - tblHeader rows repeat on each page
       - Other rows can split between rows
    """

    def layout(self, table: Table, available_width: int,
               font_mgr, para_layout_fn) -> TableBox:
        # Step 1: column width calculation
        col_widths = self._calc_col_widths(table, available_width)

        # Step 2: build grid (handle merges)
        grid = self._build_grid(table, col_widths)

        # Step 3: layout each cell
        for row_idx, row in enumerate(table.rows):
            for cell_idx, cell in enumerate(row.cells):
                cell_box = self._layout_cell(
                    cell, col_widths, grid, para_layout_fn)
                grid[row_idx][cell_idx].content = cell_box

        # Step 4: calculate row heights
        row_heights = self._calc_row_heights(grid, table.rows)

        # Step 5: vertical alignment
        self._apply_vertical_align(grid, row_heights)

        return TableBox(grid=grid, col_widths=col_widths,
                       row_heights=row_heights)

    def _build_grid(self, table, col_widths):
        """
        Handle gridSpan and vMerge, build 2D grid
        Returns grid[row][col] = CellBox | None (covered by merge)
        """
        n_rows = len(table.rows)
        n_cols = len(col_widths)
        grid = [[None] * n_cols for _ in range(n_rows)]

        for r, row in enumerate(table.rows):
            c = 0
            for cell in row.cells:
                # Skip positions occupied by vertical merge
                while c < n_cols and grid[r][c] is not None:
                    c += 1
                if c >= n_cols:
                    break

                span = cell.props.grid_span
                # Horizontal merge
                for sc in range(span):
                    if c + sc < n_cols:
                        grid[r][c + sc] = CellBox(
                            cell=cell, col_start=c, col_span=span,
                            is_origin=(sc == 0))

                # Vertical merge
                if cell.props.v_merge == VerticalMerge.RESTART:
                    # Scan downward for continue
                    rr = r + 1
                    while rr < n_rows:
                        next_cell = self._get_cell_at(table, rr, c)
                        if next_cell and next_cell.props.v_merge == VerticalMerge.CONTINUE:
                            for sc in range(span):
                                if c + sc < n_cols:
                                    grid[rr][c + sc] = CellBox(
                                        cell=next_cell, col_start=c,
                                        col_span=span, is_origin=False,
                                        v_merged=True)
                            rr += 1
                        else:
                            break

                c += span

        return grid
```

#### Table Border Rendering

```python
# render/border_renderer.py

class BorderRenderer:
    """
    Supported border styles:
    - single:  single line ─
    - double:  double line ═
    - triple:  triple line
    - thick:   thick line ━
    - dashed:  dashed line - - -
    - dotted:  dotted line · · ·
    - wave:    wavy line
    - nil:     no border

    Border conflict resolution (high to low priority):
    1. Cell border > table border
    2. Wider border > narrower
    3. Explicitly set > inherited
    """

    def draw_border(self, draw, x1, y1, x2, y2, border: BorderDef):
        if border.style == BorderStyle.NONE:
            return
        w = max(1, int(border.width))
        color = border.color

        if border.style == BorderStyle.SINGLE:
            draw.line([(x1, y1), (x2, y2)], fill=color, width=w)

        elif border.style == BorderStyle.DOUBLE:
            gap = max(1, w)
            if y1 == y2:  # horizontal line
                draw.line([(x1, y1 - gap), (x2, y2 - gap)], fill=color, width=1)
                draw.line([(x1, y1 + gap), (x2, y2 + gap)], fill=color, width=1)
            else:  # vertical line
                draw.line([(x1 - gap, y1), (x2 - gap, y2)], fill=color, width=1)
                draw.line([(x1 + gap, y1), (x2 + gap, y2)], fill=color, width=1)

        elif border.style == BorderStyle.DASHED:
            self._draw_dashed(draw, x1, y1, x2, y2, color, w, dash=6, gap=4)

        elif border.style == BorderStyle.DOTTED:
            self._draw_dashed(draw, x1, y1, x2, y2, color, w, dash=2, gap=3)
        ...
```

#### P2 Acceptance Criteria

| Test Item | Expected |
|-----------|----------|
| Basic table (3×3) | Correct grid |
| Horizontal merge (gridSpan) | Correct column span |
| Vertical merge (vMerge) | Correct row span |
| Combined merge (L-shape/T-shape) | Correct |
| Nested table | Recursive rendering |
| Table borders (6 styles) | Visually correct |
| Cell background color | Correct |
| Cell vertical alignment | top/center/bottom |
| Table alignment (left/center/right) | Correct position |
| Table cross-page | Correct pagination |
| Header row repeat | Shown on each page |
| Non-splittable row | Moves as whole |
| Table style (TableGrid etc.) | Style correct |
| Cell margins | Correct inner padding |

---

### P3 · Images & Graphics + Sections & Columns (Week 6–7)

#### 3A: Images

```xml
w:r → w:drawing
├── wp:inline                    inline image
│   ├── wp:extent cx/cy         size (EMU)
│   └── a:graphic
│       └── pic:pic
│           └── pic:blipFill
│               └── a:blip r:embed="rId5"
├── wp:anchor                    floating image
│   ├── wp:positionH / V        positioning
│   ├── wp:wrapSquare           wrap mode
│   ├── wp:wrapTight
│   ├── wp:wrapTopAndBottom
│   └── wp:wrapNone
```

```python
# parse/drawing.py

class DrawingParser:
    def parse(self, drawing_el) -> ImageRun:
        # 1. Determine inline / anchor
        inline = drawing_el.find(f"{{{NS['wp']}}}inline")
        anchor = drawing_el.find(f"{{{NS['wp']}}}anchor")

        if inline is not None:
            return self._parse_inline(inline)
        elif anchor is not None:
            return self._parse_anchor(anchor)

    def _parse_inline(self, el) -> ImageRun:
        extent = el.find(f"{{{NS['wp']}}}extent")
        cx = int(extent.get('cx', 0))
        cy = int(extent.get('cy', 0))

        blip = el.find(f".//{{{NS['a']}}}blip")
        rid = blip.get(f"{{{NS['r']}}}embed", '')

        return ImageRun(
            media_ref=rid,
            width_emu=cx, height_emu=cy,
            wrap_type="inline",
        )

    def _parse_anchor(self, el) -> ImageRun:
        # Parse floating positioning + wrap mode
        pos_h = el.find(f"{{{NS['wp']}}}positionH")
        pos_v = el.find(f"{{{NS['wp']}}}positionV")
        # ... parse relativeFrom, align, posOffset
        # ... parse wrapSquare / wrapTight / wrapTopAndBottom / wrapNone
        ...
```

#### 3B: Sections and Columns

```xml
w:sectPr
├── w:type val="continuous"      section type
├── w:pgSz / w:pgMar            page setup
├── w:cols                       columns
│   ├── w:col                   column definition
│   │   ├── w:w                 column width
│   │   └── w:space             column spacing
│   ├── w:num                   column count
│   ├── w:space                 default column spacing
│   ├── w:sep                   column separator line
│   └── w:equalWidth            equal width
├── w:headerReference           header reference
├── w:footerReference           footer reference
└── w:lnNumType                 line numbers
```

```python
# layout/column_layout.py

class ColumnLayoutEngine:
    """
    Multi-column layout algorithm:
    1. Calculate each column width = (available width - (n-1)*column spacing) / n
    2. Fill first column first, then second when full...
    3. Column separator line (w:sep)
    4. Continuous section: switch column count within same page
    5. Balance columns: distribute content evenly in last column (optional)
    """

    def layout_columns(self, blocks, section, page_area):
        n = section.col_count
        col_w = (page_area.width - (n - 1) * section.col_space) / n
        columns = [[] for _ in range(n)]
        col_idx = 0
        cursor_y = page_area.top

        for block in blocks:
            block_height = block.total_height
            if cursor_y + block_height > page_area.bottom:
                col_idx += 1
                cursor_y = page_area.top
                if col_idx >= n:
                    # Need new page
                    yield columns
                    columns = [[] for _ in range(n)]
                    col_idx = 0

            columns[col_idx].append((block, cursor_y))
            cursor_y += block_height

        yield columns
```

#### P3 Acceptance Criteria

| Test Item | Expected |
|-----------|----------|
| Inline image | Correct size, flows with text |
| Floating image (square wrap) | Text wraps around |
| Floating image (top/bottom) | No wrapping, top/bottom spacing |
| Floating image (behind/inFront) | Correct z-order |
| Image positioning (absolute/relative) | Correct position |
| Multi-section document | Each section has independent page setup |
| 2/3 column layout | Correct column widths |
| Column separator line | Displayed correctly |
| Continuous section | Switch column count on same page |
| Different paper sizes per section | Correct |

---

### P4 · Headers & Footers + Page Numbers (Week 8)

```xml
word/header1.xml / footer1.xml
├── w:p[]                       same paragraph structure as document.xml
├── w:fldSimple                 simple field
│   └── w:instr " PAGE "       page number
├── w:r → w:fldChar            complex field
│   ├── w:fldChar type="begin"
│   ├── w:instrText " PAGE "
│   └── w:fldChar type="end"
└── w:sdt                       structured document tag

References (sectPr):
├── w:headerReference type="default" r:id="rId7"
├── w:headerReference type="first" r:id="rId8"
├── w:headerReference type="even" r:id="rId9"
├── w:footerReference type="default" r:id="rId10"
└── w:titlePg                   different first page
```

```python
# parse/header_footer.py

class HeaderFooterParser:
    """
    Header/footer types:
    - default: default (odd pages)
    - first:   first page
    - even:    even pages

    Field code support:
    - PAGE:    current page number
    - NUMPAGES: total pages
    - DATE:    date
    - AUTHOR:  author
    - TITLE:   title
    - SECTION: section number
    """

    def parse_field(self, instr_text: str) -> str:
        instr = instr_text.strip().upper()
        if instr == "PAGE":
            return "{page_num}"       # placeholder, replaced at render time
        elif instr == "NUMPAGES":
            return "{total_pages}"
        elif instr.startswith("DATE"):
            return "{{DATE}}"  # expanded from Config.reference_datetime
        ...
```

#### P4 Acceptance Criteria

| Test Item | Expected |
|-----------|----------|
| Default header/footer | Shown on every page |
| Different first page | First page has independent header/footer |
| Different odd/even pages | Alternating display |
| Page number (PAGE) | Correct number |
| Total pages (NUMPAGES) | Correct number |
| "Page X of Y" format | Correct format |
| Images in header | Displayed correctly |
| Tables in header | Displayed correctly |
| Different headers per section | Correct switching |

---

### P5 · List Numbering (Week 9)

```xml
word/numbering.xml
├── w:abstractNum abstractNumId="0"
│   ├── w:multiLevelType val="hybridMultilevel"
│   └── w:lvl ilvl="0"
│       ├── w:start val="1"
│       ├── w:numFmt val="decimal"
│       ├── w:lvlText val="%1."
│       ├── w:lvlJc val="left"
│       ├── w:pPr
│       │   ├── w:ind w:left="720" w:hanging="360"
│       │   └── w:tabs
│       └── w:rPr
│           └── w:rFonts w:hint="default"
├── w:num numId="1"
│   └── w:abstractNumId val="0"

Referenced in document.xml:
w:pPr → w:numPr
├── w:ilvl val="0"              level
└── w:numId val="1"             numbering instance
```

```python
# layout/list_layout.py

class NumberingEngine:
    """
    Numbering format support:
    - decimal:        1. 2. 3.
    - upperLetter:    A. B. C.
    - lowerLetter:    a. b. c.
    - upperRoman:     I. II. III.
    - lowerRoman:     i. ii. iii.
    - bullet:         • / ○ / ■ / ➤
    - chineseCounting: CJK counting
    - ideographDigital: CJK ideograph digital
    - decimalZero:    01. 02. 03.

    Multi-level lists:
    - lvlText="%1.%2" → 1.1, 1.2, 2.1
    - Each level has independent indent

    Numbering counters:
    - Each numId has independent counter
    - Sub-levels reset when parent level changes
    """

    def __init__(self, numbering_table: NumberingTable):
        self.table = numbering_table
        self.counters = {}  # numId → {level: current_count}

    def get_label(self, num_id: int, level: int) -> str:
        defn = self.table.get_definition(num_id)
        if not defn:
            return ""

        lvl = defn.levels.get(level)
        if not lvl:
            return ""

        # Update counter
        if num_id not in self.counters:
            self.counters[num_id] = {}
        ctr = self.counters[num_id]
        ctr[level] = ctr.get(level, lvl.start - 1) + 1
        # Reset deeper levels
        for l in list(ctr.keys()):
            if l > level:
                del ctr[l]

        # Format
        num = ctr[level]
        fmt = lvl.num_fmt

        if fmt == NumberFormat.DECIMAL:
            text = str(num)
        elif fmt == NumberFormat.UPPER_LETTER:
            text = self._to_letter(num).upper()
        elif fmt == NumberFormat.LOWER_LETTER:
            text = self._to_letter(num).lower()
        elif fmt == NumberFormat.UPPER_ROMAN:
            text = self._to_roman(num).upper()
        elif fmt == NumberFormat.LOWER_ROMAN:
            text = self._to_roman(num).lower()
        elif fmt == NumberFormat.BULLET:
            text = lvl.bullet_char or "•"
        elif fmt == NumberFormat.CHINESE_COUNTING:
            text = self._to_chinese(num)
        else:
            text = str(num)

        # Replace %1, %2 ... in lvlText
        result = lvl.lvl_text
        for i in range(level + 1):
            placeholder = f"%{i + 1}"
            if placeholder in result:
                n = ctr.get(i, 1)
                result = result.replace(placeholder, self._format_num(n, defn.levels[i].num_fmt))

        return result

    def _to_roman(self, num: int) -> str:
        vals = [1000,900,500,400,100,90,50,40,10,9,5,4,1]
        syms = ['m','cm','d','cd','c','xc','l','xl','x','ix','v','iv','i']
        result = ''
        for v, s in zip(vals, syms):
            while num >= v:
                result += s
                num -= v
        return result

    def _to_chinese(self, num: int) -> str:
        chars = '零一二三四五六七八九十'
        if num <= 10:
            return chars[num]
        # Simplified handling...
        return str(num)
```

#### P5 Acceptance Criteria

| Test Item | Expected |
|-----------|----------|
| Ordered list 1. 2. 3. | Correct numbering |
| Unordered list • | Correct bullet |
| Multi-level list 1.1 / 1.1.1 | Correct hierarchy |
| Roman numerals I. II. III. | Correct |
| Letters A. B. C. | Correct |
| CJK counting | Correct |
| Hanging indent | Text aligns correctly |
| Custom numbering font/color | Correct |
| List restart | Counter resets |

---

### P6 · Advanced Layout (Week 10–11)

#### 6A: Justify

```python
# layout/justify.py

class JustifyEngine:
    """
    Justify algorithm:
    1. Calculate total width of all characters in line
    2. Calculate remaining space = available width - total width
    3. Distribute remaining space evenly between characters
    4. Both CJK character gaps and Latin word gaps receive distribution
    5. Last line is not justified (left-aligned)
    6. Single-word lines are not justified

    Distribute alignment:
    - Similar to justify, but space is also distributed after the last character
    """

    def distribute(self, runs: list, available_width: int,
                   is_last_line: bool) -> list:
        if is_last_line or len(runs) <= 1:
            return runs  # skip

        total_w = sum(r.width for r in runs)
        gap = available_width - total_w
        if gap <= 0:
            return runs

        n_gaps = len(runs) - 1
        extra_per_gap = gap / n_gaps

        x = runs[0].x
        for i, r in enumerate(runs):
            r.x = int(x)
            x += r.width + extra_per_gap

        return runs
```

#### 6B: Tab Stops

```python
# layout/tab_stop.py

class TabStopEngine:
    """
    Tab stop types:
    - left:    text extends right from tab stop
    - center:  text centered on tab stop
    - right:   text ends at tab stop
    - decimal: decimal point aligned at tab stop

    Default tab stops: one left tab every 36pt (0.5 inch)

    Leaders:
    - none / dot / hyphen / underscore / heavy
    """

    def resolve_tab(self, current_x: int, tab_stops: list,
                    default_tab: float, scale: float) -> int:
        # Find next tab stop greater than current_x
        stops = sorted([ts.position * scale for ts in tab_stops])
        if not stops:
            # Use default tab stops
            default_px = default_tab * scale
            return int((current_x // default_px + 1) * default_px)

        for s in stops:
            if s > current_x:
                return int(s)
        return int(stops[-1] + default_tab * scale)
```

#### 6C: Text Boxes and Floating Elements

```xml
w:r → w:pict → v:shape           VML text box
w:r → w:drawing → wp:anchor      DrawingML text box
├── w:txbxContent                text box content
│   └── w:p[]                    paragraphs
├── wp:wrapSquare                wrap
└── a:xfrm                       position/size/rotation
```

```python
# layout/float_layout.py

class FloatLayoutEngine:
    """
    Floating element layout:
    1. Parse anchor position (relativeFrom: page/margin/column/paragraph)
    2. Calculate absolute coordinates of floating element
    3. Calculate text exclusion zone based on wrap type
    4. Skip exclusion zone during line breaking
    5. Z-order: behind < text < inFront

    Wrap types:
    - square:      rectangular wrap
    - tight:       tight to outline (simplified to rectangle)
    - topAndBottom: no wrapping, top/bottom spacing only
    - behind:      behind text
    - inFrontOf:   in front of text
    """

    def compute_exclusion_zones(self, floats: list,
                                page_area) -> list:
        """Calculate available width per line (excluding float zones)"""
        zones = []
        for f in floats:
            if f.wrap_type in ('square', 'tight'):
                zones.append({
                    'y_start': f.y,
                    'y_end': f.y + f.height,
                    'x_start': f.x,
                    'x_end': f.x + f.width,
                })
        return zones
```

#### P6 Acceptance Criteria

| Test Item | Expected |
|-----------|----------|
| Justify | Even character/word spacing |
| Distribute alignment | Includes trailing space |
| Tab stops (left/center/right/decimal) | Correct alignment |
| Tab stop leaders (dot/underscore) | Displayed correctly |
| Text box (fixed position) | Correct position |
| Text box with multiple paragraphs | Content correct |
| Text wrap (square) | Wrap correct |
| Text wrap (top/bottom) | Top/bottom spacing |
| Z-order (behind/inFront) | Layer order correct |

---

### P7 · Math OMML (Week 12–13)

```xml
m:oMath
├── m:r → m:t "x"              plain character
├── m:f (fraction)
│   ├── m:num → m:r → m:t "a"
│   └── m:den → m:r → m:t "b"
├── m:rad (radical)
│   ├── m:deg                   degree
│   └── m:e → m:r → m:t "x"
├── m:sSup (superscript)
│   ├── m:e → m:r → m:t "x"
│   └── m:sup → m:r → m:t "2"
├── m:sSub (subscript)
├── m:sSubSup (sub-superscript)
├── m:nary (summation/integral)
│   ├── m:sub / m:sup          lower/upper limits
│   └── m:e                    operand expression
├── m:d (delimiter/brackets)
│   ├── m:dPr → m:begChr / m:endChr
│   └── m:e
├── m:m (matrix)
│   └── m:mr → m:e
├── m:bar (overline/underline)
├── m:acc (accent)
├── m:func (function sin/cos/log)
├── m:eqArr (equation array)
└── m:limUpp / m:limLow        upper/lower limits
```

```python
# parse/math_omml.py → model/math_ast.py

# AST node definitions
@dataclass
class MathNode:
    pass

@dataclass
class MathChar(MathNode):
    char: str
    style: str = "p"  # p=plain, i=italic, b=bold

@dataclass
class MathFrac(MathNode):
    numerator: MathNode = None
    denominator: MathNode = None

@dataclass
class MathRad(MathNode):
    degree: MathNode = None     # None = square root
    radicand: MathNode = None

@dataclass
class MathSup(MathNode):
    base: MathNode = None
    superscript: MathNode = None

@dataclass
class MathSub(MathNode):
    base: MathNode = None
    subscript: MathNode = None

@dataclass
class MathNary(MathNode):
    char: str = "∑"            # ∑ ∫ ∏ ∮
    lower: MathNode = None
    upper: MathNode = None
    body: MathNode = None

@dataclass
class MathDelim(MathNode):
    open_chr: str = "("
    close_chr: str = ")"
    body: MathNode = None

@dataclass
class MathMatrix(MathNode):
    rows: list = field(default_factory=list)  # [[MathNode]]

# layout/math_layout.py

class MathLayoutEngine:
    """
    Math layout algorithm:
    1. Recursively traverse AST
    2. Each node computes (width, height, ascent, descent)
    3. Fraction: numerator and denominator stacked, line drawn between
    4. Radical: draw √ symbol + overline
    5. Super/subscript: reduce font size (~70%), offset position
    6. Large operators (∑∫): enlarge font, place limits above/below
    7. Brackets: stretch based on content height
    """

    def layout(self, node: MathNode, font_mgr, base_size: float):
        if isinstance(node, MathChar):
            return self._layout_char(node, font_mgr, base_size)
        elif isinstance(node, MathFrac):
            return self._layout_frac(node, font_mgr, base_size)
        elif isinstance(node, MathRad):
            return self._layout_rad(node, font_mgr, base_size)
        elif isinstance(node, MathSup):
            return self._layout_sup(node, font_mgr, base_size)
        elif isinstance(node, MathNary):
            return self._layout_nary(node, font_mgr, base_size)
        elif isinstance(node, MathDelim):
            return self._layout_delim(node, font_mgr, base_size)
        ...

    def _layout_frac(self, node, fm, size):
        num_box = self.layout(node.numerator, fm, size * 0.85)
        den_box = self.layout(node.denominator, fm, size * 0.85)
        w = max(num_box.width, den_box.width) + 8
        h = num_box.height + den_box.height + 6  # 6=fraction line+spacing
        return MathBox(width=w, height=h, ...)
```

```python
# render/math_renderer.py

class MathRenderer:
    """
    Math rendering:
    - Fraction: draw.line() for fraction bar
    - Radical: draw.polygon() for √ shape + draw.line() for overline
    - Brackets: render with font or draw.arc() based on height
    - Large operators: render ∑ ∫ ∏ with large font
    - Super/subscript: small font + y offset
    """

    def render(self, draw, box: MathBox, x: int, y: int):
        ...

    def _draw_radical(self, draw, x, y, w, h):
        """Draw radical √"""
        # √ shape: short vertical → diagonal → long vertical → overline
        points = [
            (x, y + h * 0.6),
            (x + 3, y + h),
            (x + 8, y),
            (x + 8, y),
        ]
        draw.line(points, fill=(0, 0, 0), width=1)
        draw.line([(x + 8, y), (x + w, y)], fill=(0, 0, 0), width=1)
```

#### P7 Acceptance Criteria

| Test Item | Expected |
|-----------|----------|
| Inline math $x^2$ | Superscript correct |
| Fraction $\frac{a}{b}$ | Stacked + fraction line |
| Radical $\sqrt{x}$ | √ shape correct |
| N-th root $\sqrt[3]{x}$ | Degree displayed |
| Summation $\sum_{i=1}^{n}$ | Upper/lower limits correct |
| Integral $\int_0^1$ | Correct |
| Auto-sizing brackets $(...)$ | Height matches |
| Matrix | Grid arrangement |
| Functions sin/cos/log | Upright |
| Equation array (multi-line) | Alignment correct |

---

## 5. Font Management (Across All Phases)

```python
# font/manager.py

class FontManager:
    """
    Font management strategy:

    1. Lookup order:
       ① Document embedded fonts (word/fonts/)
       ② Project fonts/ directory
       ③ System font directories
       ④ Fallback fonts

    2. Font fallback chain:
       Specified font → same-family font → system default → DejaVu Sans

    3. ASCII / East Asian font selection:
       - ASCII characters → font_ascii (e.g. Times New Roman)
       - CJK characters → font_east_asia (e.g. SimSun)
       - Per-character font selection

    4. Font metrics:
       - Use fontTools to read OS/2 table
       - ascent / descent / lineGap
       - Used for precise line height calculation

    5. Caching:
       - LRU cache for loaded ImageFont objects
       - key = (font_path, size_px)
    """

    SYSTEM_FONT_DIRS = {
        'linux': ['/usr/share/fonts', '/usr/local/share/fonts'],
        'darwin': ['/System/Library/Fonts', '/Library/Fonts',
                   os.path.expanduser('~/Library/Fonts')],
        'win32': ['C:/Windows/Fonts'],
    }

    FALLBACK_CHAIN = [
        'DejaVu Sans',
        'Noto Sans CJK SC',
        'WenQuanYi Micro Hei',
        'Arial',
    ]

    def get_font_for_char(self, ch: str, props: RunProps,
                          size_px: int) -> ImageFont:
        """Select font based on character"""
        if self._is_cjk(ch):
            name = props.font_east_asia
        else:
            name = props.font_ascii

        font = self._load(name, size_px, props.bold, props.italic)
        if font and self._has_glyph(font, ch):
            return font

        # Fallback
        for fb in self.FALLBACK_CHAIN:
            font = self._load(fb, size_px, props.bold, props.italic)
            if font and self._has_glyph(font, ch):
                return font

        return ImageFont.load_default()

    def _has_glyph(self, font: ImageFont, ch: str) -> bool:
        """Check whether font contains glyph for this character"""
        try:
            cmap = font.font.charmap if hasattr(font.font, 'charmap') else {}
            return ord(ch) in cmap
        except Exception:
            return True  # assume supported when unable to determine
```

---

## 6. Rendering Engine (Across All Phases)

```python
# render/canvas.py

class Canvas:
    """Pillow canvas wrapper"""

    def __init__(self, width: int, height: int, dpi: int = 150):
        self.dpi = dpi
        self.img = Image.new("RGB", (width, height), (255, 255, 255))
        self.draw = ImageDraw.Draw(self.img)

    def draw_text(self, x, y, text, font, fill, **kwargs):
        self.draw.text((x, y), text, font=font, fill=fill, **kwargs)

    def draw_line(self, x1, y1, x2, y2, fill, width=1, style="solid"):
        if style == "solid":
            self.draw.line([(x1, y1), (x2, y2)], fill=fill, width=width)
        elif style == "dashed":
            self._draw_dashed_line(x1, y1, x2, y2, fill, width, 6, 4)
        elif style == "dotted":
            self._draw_dashed_line(x1, y1, x2, y2, fill, width, 2, 3)

    def draw_rect(self, x1, y1, x2, y2, outline=None, fill=None, width=1):
        self.draw.rectangle([x1, y1, x2, y2], outline=outline, fill=fill, width=width)

    def draw_image(self, img: Image.Image, x, y, w, h):
        resized = img.resize((w, h), Image.LANCZOS)
        self.img.paste(resized, (x, y))
        self.draw = ImageDraw.Draw(self.img)  # refresh draw

    def save(self, path, fmt="PNG", quality=95):
        self.img.save(path, fmt, dpi=(self.dpi, self.dpi), quality=quality)
```

---

## 7. CLI and API

```python
# cli.py
import argparse
from .api import convert

def main():
    parser = argparse.ArgumentParser(description="DocX → Image (Pure Python)")
    parser.add_argument("input", help="Input .docx file")
    parser.add_argument("-o", "--output", default="./output", help="Output directory")
    parser.add_argument("--dpi", type=int, default=150, help="DPI (72-600)")
    parser.add_argument("--format", choices=["PNG", "JPEG", "TIFF"], default="PNG")
    parser.add_argument("--pages", help="Specify pages, e.g. 1,3,5-8")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality")
    parser.add_argument("--font-dir", help="Additional font directory")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    paths = convert(
        args.input, args.output,
        dpi=args.dpi, fmt=args.format,
        pages=args.pages, quality=args.quality,
        font_dir=args.font_dir, verbose=args.verbose,
    )
    for p in paths:
        print(f"✅ {p}")

# api.py
def convert(input_path, output_dir="./output", dpi=150,
            fmt="PNG", pages=None, quality=95,
            font_dir=None, verbose=False) -> list:
    """
    Main conversion function

    >>> from docx2img import convert
    >>> convert("report.docx", dpi=300)
    ['output/page_000.png', 'output/page_001.png']
    """
    ...
```

```bash
# Usage
$ docx2img report.docx -o ./images --dpi 300 --format PNG
$ docx2img report.docx --pages 1,3,5-8
$ python -c "from docx2img import convert; convert('a.docx')"
```

---

## 8. Test Strategy

```
tests/
├── unit/                        unit tests
│   ├── test_units.py            unit conversion
│   ├── test_parse_paragraph.py  paragraph parsing
│   ├── test_parse_table.py      table parsing
│   ├── test_parse_drawing.py    image parsing
│   ├── test_parse_math.py       math parsing
│   ├── test_style_resolver.py   style inheritance
│   ├── test_line_breaker.py     line breaking
│   ├── test_page_breaker.py     pagination
│   ├── test_table_layout.py     table layout
│   ├── test_numbering.py        numbering engine
│   └── test_justify.py          justify
│
├── integration/                 integration tests
│   ├── test_parse_full.py       full document parsing
│   └── test_layout_full.py      full layout
│
├── e2e/                         end-to-end tests
│   ├── test_basic_text.py       basic text → image
│   ├── test_tables.py
│   ├── test_images.py
│   ├── test_headers_footers.py
│   ├── test_lists.py
│   ├── test_columns.py
│   ├── test_math.py
│   └── test_complex.py          mixed complex document
│
├── visual providers (scripts/, not runtime)
│   ├── generate_office_golden.py   Word COM → PDF → tests/golden/office/
│   ├── generate_lo_golden.py       LibreOffice → PDF → tests/golden/libreoffice/
│   ├── run_visual_regression.py    --provider office|libreoffice
│   └── visual_compare.py           strict page metrics (no free resize)
│
│ Word is the fidelity authority; LibreOffice goldens are diagnostic only.
│ First office baseline records MAE/RMSE/diff%/SSIM without a global pass gate.
│
├── visual/                      (design target; office provider is the live path)
│   ├── baseline/                baseline images (manually verified)
│   ├── test_visual_diff.py      pixel-level comparison (SSIM / MSE)
│   └── generate_baseline.py
│
└── fixtures/                    test documents
    ├── generated/               script-generated .docx
    │   └── gen_fixtures.py      generate test files using stdlib
    └── real_world/              real-world documents
```

```python
# Office provider baseline (scripts/run_visual_regression.py --provider office)
# Records MAE / RMSE / changed-pixel ratio / downscaled SSIM.
# Size or page-count mismatch is a hard_diff; images are never freely resized.
#
# Office golden cases (Word 16.0, 150 dpi):
#   basic_text  2/2 pages  MAE 2.16  SSIM 0.95
#   date_field  1/1 page  MAE 0.308  SSIM 0.982710  diff% 0.159%
#   drawingml_text  1/1 page  MAE 0.554  SSIM 0.889565  diff% 0.317%
#   math_accent  1/1 page  MAE 0.010  SSIM 0.999180  diff% ~0.006%
#   math_bar  1/1 page  MAE 0.013  SSIM 0.998945  diff% ~0.006%
#   math_border_box  1/1 page  MAE 0.013  SSIM 0.997239  diff% ~0.007%
#   page_break  3/3 pages  MAE 0.565  SSIM 0.955725  diff% 0.284%
#   shape_fill  1/1 pages  MAE 0.84  SSIM 0.97  diff% 0.6%
```

DATE determinism: header/footer `w:fldSimple` and complex DATE fields are
stored as `{{DATE}}` until page attachment. `LayoutEngine` expands the
placeholder from `Config.reference_datetime`; its fixed default is
`2000-01-01`, and callers must explicitly inject a current time when desired.
The office provider stores `reference_datetime` in golden metadata and passes
that exact value to both renderer/determinism passes. The one-page
`date_field` fixture contains a stale `2000-01-01` cached field result; Word
16.0 updates its read-only copy to `2026-07-26`. At 150 dpi the configured
renderer is deterministic and matches page count/size with MAE 0.308, RMSE
8.215, changed pixels 0.159%, and SSIM 0.982710. A controlled old-code run
with the system clock advanced to `2099-12-31` measures MAE 0.323, RMSE 8.438,
changed pixels 0.165%, and SSIM 0.980758, demonstrating the eliminated
clock-dependent drift.

OMML bar fidelity: `m:bar` maps to a native `MathBar` AST containing its body
and top/bottom `m:pos`. `MathLayoutEngine` retains the body metrics and emits
an explicit horizontal rule on the requested side, so unknown-node
flattening no longer drops the bar. The centered, single-structure
`math_bar.docx` fixture improves against Word 16.0 from MAE 0.019, RMSE 2.056,
changed pixels 0.009%, SSIM 0.993927 to MAE 0.013, RMSE 1.671, changed pixels
approximately 0.006%, SSIM 0.998945 at 150 dpi (1/1 page, exact size,
deterministic). This does not extend the claim to `eqArr` or limit
structures.

OMML accent fidelity: `m:acc` maps to a native `MathAccent` AST with the
explicit `m:accPr/m:chr` character and parsed `m:e` body. The layout centers
the accent over the body while retaining the body's height and baseline;
rendering the mark in the existing ascender area avoids the vertical shift
introduced by stacking two independent text boxes. A missing `m:e` logs the
stable `omml_acc_missing_body` warning and remains non-fatal. The centered
`math_accent.docx` fixture improves against Word 16.0 from the flattened
body's RMSE 1.410 and SSIM 0.998550 to RMSE 1.396 and SSIM 0.999180 at 150
dpi (MAE 0.010, changed pixels approximately 0.006%, 1/1 page, exact size,
deterministic). This is a basic single-character accent path; font-specific
stretching/combining behavior and `eqArr`/limit structures remain unsupported
or approximate.

OMML border-box fidelity: `m:borderBox` maps to a native `MathBorderBox` AST
containing its `m:e` body, `hideTop`/`hideBot`/`hideLeft`/`hideRight`, and
the `strikeH`/`strikeV`/`strikeBLTR`/`strikeTLBR` properties. Layout derives
the visible body ink bounds, adds Word-measured padding and emits explicit
side/strike rules without shifting the paragraph origin. A missing body logs
`omml_border_box_missing_body` and remains non-fatal. The centered
`math_border_box.docx` fixture improves against Word 16.0 from MAE 0.034,
RMSE 2.848, changed pixels 0.015%, SSIM 0.983195 to MAE 0.013, RMSE 1.633,
changed pixels approximately 0.007%, SSIM 0.997239 at 150 dpi (1/1 page,
exact size, deterministic). Nested/stretchy contents and font-specific rule
metrics remain approximate.

Manual page break fidelity: a paragraph whose only content is `w:br
w:type="page"` keeps its mark-line height and trailing paragraph spacing
during page-fit checks. When their combined box overflows a full page, the
invisible paragraph lands alone on the next page — reproducing the blank
intermediate page Word emits before the break fires. Verified by the
`page_break` office golden (3/3 pages and sizes, deterministic, blank page 2
pixel-identical in docx2img and Word; mean MAE 0.565, SSIM 0.955725, changed
pixels 0.284% at 150 dpi). Spilled real content on that page (Word behaviour
when the page is not exactly full) is likewise preserved instead of forcing a
blank.

Shape fill & outline fidelity: standalone DrawingML text boxes / autoshapes
(`wps:wsp`/`w:txbxContent` inside `wp:anchor`) previously rendered as bare
text — the shape's `a:solidFill` background and `a:ln` outline were dropped
because only the group-shape path (`parse_group`) extracted them.
`DrawingParser.parse_textbox` now reads `wps:wsp/wps:spPr` via the shared
`_shape_fill_and_border` helper and forwards `fill`/`border_color` to the
`TextBoxRun`; `RenderCanvas` already draws the filled rectangle + outline. The
`shape_fill` office golden quantifies this at MAE ≈ 0.84, SSIM ≈ 0.97 against
Word 16.0 (150 dpi): the yellow/blue fills and red outline match, with only
the border weight (1px canvas vs Word's 2pt) contributing residual diff.

Native DrawingML shape text is supported as a deliberately bounded subset.
`DrawingParser.parse_textbox` recognizes `a:sp/a:txSp/a:txBody` in addition
to `w:txbxContent`, converts `a:p`, `a:r`, cached `a:fld` text and `a:br` to
the existing paragraph/run IR, and maps paragraph alignment plus common font,
size, emphasis, underline/strike and sRGB color properties. `a:bodyPr`
left/top/right/bottom insets and top/center/bottom anchors are stored on
`TextBoxRun`; the layout engine applies those insets, stacks nested paragraphs,
centers against text ink height, and does not reserve body-flow height for
`wrapNone`/in-front text boxes. Visible content under unknown child nodes logs
`drawingml_txbody_unsupported`; cached fields and non-sRGB colors log
`drawingml_txbody_field_cached` and `drawingml_txbody_unsupported_color`
respectively instead of degrading silently.

The code-generated `drawingml_text.docx` fixture contains only
`a:sp/a:txSp/a:txBody` (no `wps:txbx` fallback). Against Word 16.0 at 150 dpi,
the clean implementation produces 1/1 page at the exact reference size and is
byte-deterministic. Relative to the unmodified parser, MAE improves
0.631→0.554, RMSE 11.400→10.552, changed pixels 0.339%→0.317%, and SSIM
0.652430→0.889565. This remains basic support: DrawingML bullets, autofit,
vertical/warped text, theme-color resolution and arbitrary effects are not
claimed complete.

---

## 9. Performance Targets and Optimization

| Metric | Target | Optimization |
|--------|--------|-------------|
| 10-page plain text | < 2s | Font caching, batch drawing |
| 50-page with tables | < 10s | Lazy parsing, page-by-page rendering |
| 100-page complex doc | < 30s | Multi-process (ProcessPool) |
| Memory usage | < 500MB | Per-page rendering, timely release |
| Font loading | First load < 1s | LRU cache, preloading |

```python
# Parallel multi-page rendering
from concurrent.futures import ProcessPoolExecutor

def render_parallel(pages, section, dpi, max_workers=4):
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_render_single_page, page, section, dpi)
            for page in pages
        ]
        return [f.result() for f in futures]
```

---

## 10. Iteration Milestones Overview

| Phase | Period | Deliverable | Fidelity |
|-------|--------|-------------|----------|
| **P0** Basic text | W1-W2 | Plain text docx → PNG | ~60% |
| **P1** Style system | W3 | Styles/theme/inheritance | ~70% |
| **P2** Tables | W4-W5 | Complex tables/merge/nested | ~78% |
| **P3** Images + sections/columns | W6-W7 | Images/wrap/multi-section/columns | ~83% |
| **P4** Headers & footers | W8 | Headers/footers/page numbers/fields | ~86% |
| **P5** List numbering | W9 | Multi-level lists/numbering formats | ~89% |
| **P6** Advanced layout | W10-W11 | Justify/tab stops/text boxes/floats | ~93% |
| **P7** Math | W12-W13 | OMML math rendering | ~95% |
| **Ongoing** Optimization + fixes | W14+ | Performance/visual regression/edge cases | →97% |

> **Expected final fidelity**: ~97% for simple documents, ~90–93% for complex documents. The remaining gap mainly comes from undocumented Word layout details and font rendering engine differences, which is the theoretical ceiling for a pure Python solution.

---
