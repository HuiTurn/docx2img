"""Layout engine - Converts IR to layout tree with pages"""

from dataclasses import dataclass, field
from typing import List, Any, Optional

from ..config import Config
from ..model.document import DocumentModel
from ..model.paragraph import Paragraph
from ..model.table import Table
from ..model.section import Section
from ..model.enums import Alignment
from ..font.manager import FontManager
from .line_breaker import LineBreaker
from .page_breaker import PageBreaker
from .table_layout import TableLayoutEngine
from .column_layout import column_geometries
from .list_layout import NumberingEngine
from .justify import apply_justification
from .float_layout import FloatBox, FloatLayoutEngine
from ..model.enums import Alignment
from ..parse.units import Units
from io import BytesIO
from PIL import Image as PILImage


@dataclass
class GlyphBox:
    """A rendered glyph segment (characters, image, or math)."""
    text: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    font: Any = None
    props: Any = None
    image: Any = None  # PIL.Image for inline images
    math_box: Any = None  # MathBox for formulas


@dataclass
class LineBox:
    """A line of text within a block."""
    glyphs: List[GlyphBox] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0


@dataclass
class BlockBox:
    """A block element (paragraph or table)."""
    lines: List[LineBox] = field(default_factory=list)
    cells: List[Any] = field(default_factory=list)
    table_box: Any = None  # TableBox when element is Table
    float_boxes: List[Any] = field(default_factory=list)  # FloatBox
    textbox_boxes: List[Any] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    element: Any = None
    space_before: float = 0.0
    space_after: float = 0.0
    page_break_before: bool = False


@dataclass
class PageBox:
    """A page of laid-out content."""
    blocks: List[BlockBox] = field(default_factory=list)
    header_blocks: List[BlockBox] = field(default_factory=list)
    footer_blocks: List[BlockBox] = field(default_factory=list)
    float_boxes: List[Any] = field(default_factory=list)
    textbox_boxes: List[Any] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    margin_top: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0
    margin_right: float = 0.0
    section: Optional[Section] = None
    page_number: int = 1
    total_pages: int = 1


class LayoutEngine:
    """Convert DocumentModel to a list of PageBox objects."""

    def __init__(self, document: DocumentModel, config: Config):
        self.document = document
        self.config = config
        self.font_manager = FontManager(config)
        self.line_breaker = LineBreaker(config, self.font_manager)
        self.page_breaker = PageBreaker(config)
        self.table_layout = TableLayoutEngine(
            config,
            self.line_breaker,
            layout_paragraph_fn=None,
            layout_table_fn=self._layout_table_inner,
        )
        self.numbering_engine = NumberingEngine(document.numbering)
        self.float_layout = FloatLayoutEngine()

    def layout(self) -> List[PageBox]:
        """Perform layout and return pages (supports multi-section)."""
        parts = self._split_sections()
        all_pages: List[PageBox] = []
        for section, elements in parts:
            pages = self._layout_section(section, elements)
            all_pages.extend(pages)

        total = len(all_pages) if all_pages else 1
        start = 1
        for i, page in enumerate(all_pages):
            if page.section and page.section.page_num_start is not None and i == 0:
                start = page.section.page_num_start
            # Per-section start: if section changes and has page_num_start
            page.page_number = start + i
            page.total_pages = total
            self._attach_header_footer(page, i, total)

        return all_pages if all_pages else [PageBox(width=595, height=842)]

    def _attach_header_footer(self, page: PageBox, page_index: int, total: int) -> None:
        import copy
        section = page.section or Section()
        px_per_pt = self.config.px_per_pt
        page_num = page.page_number

        def pick(bodies: dict, refs_prefer: list) -> list:
            for key in refs_prefer:
                if key in bodies and bodies[key]:
                    return bodies[key]
            return bodies.get("default") or []

        is_first = page_index == 0
        is_even = (page_num % 2 == 0)
        if section.title_page and is_first:
            h_pref = ["first", "default"]
            f_pref = ["first", "default"]
        elif is_even and ("even" in section.header_bodies or "even" in section.footer_bodies):
            h_pref = ["even", "default"]
            f_pref = ["even", "default"]
        else:
            h_pref = ["default"]
            f_pref = ["default"]

        header_elems = pick(section.header_bodies, h_pref)
        footer_elems = pick(section.footer_bodies, f_pref)

        content_width = page.width - page.margin_left - page.margin_right
        header_y = section.header_distance * px_per_pt

        for elem in header_elems:
            if isinstance(elem, Paragraph):
                para = copy.deepcopy(elem)
                self._expand_para_fields(para, page_num, total)
                blocks = self._layout_paragraph(
                    para, page.margin_left, content_width, px_per_pt
                )
                y = header_y
                for b in blocks:
                    b.y = y
                    self._finalize_block_coords(b)
                    page.header_blocks.append(b)
                    y += b.height

        footer_top = page.height - section.footer_distance * px_per_pt
        footer_blocks = []
        for elem in footer_elems:
            if isinstance(elem, Paragraph):
                para = copy.deepcopy(elem)
                self._expand_para_fields(para, page_num, total)
                blocks = self._layout_paragraph(
                    para, page.margin_left, content_width, px_per_pt
                )
                footer_blocks.extend(blocks)
        fh = sum(b.height for b in footer_blocks)
        y = footer_top - fh
        for b in footer_blocks:
            b.y = y
            self._finalize_block_coords(b)
            page.footer_blocks.append(b)
            y += b.height

    def _expand_para_fields(self, para: Paragraph, page_num: int, total: int) -> None:
        from ..parse.header_footer import HeaderFooterParser
        for run in para.runs:
            if run.text and run.text.text:
                run.text.text = HeaderFooterParser.expand_placeholders(
                    run.text.text, page_num, total
                )

    def _split_sections(self):
        """Split body into (Section, elements[]) using paragraph section breaks."""
        sections = list(self.document.sections) or [Section()]
        chunks: List[List] = [[]]
        sect_idx = 0

        for element in self.document.body:
            chunks[-1].append(element)
            if isinstance(element, Paragraph) and element.section_break is not None:
                # This paragraph ends current section; next content → next section
                chunks.append([])
                sect_idx += 1

        # Align sections: one section per chunk (last body sectPr covers last chunk)
        while len(sections) < len(chunks):
            sections.append(sections[-1] if sections else Section())
        # If trailing empty chunk after final mid-body break + final sectPr, drop it
        while len(chunks) > 1 and not chunks[-1]:
            chunks.pop()
        sections = sections[: len(chunks)]
        return list(zip(sections, chunks))

    def _layout_section(self, section: Section, elements: list) -> List[PageBox]:
        px_per_pt = self.config.px_per_pt
        page_width, page_height = self._page_size(section, px_per_pt)
        margin_top = section.margin_top * px_per_pt
        margin_bottom = section.margin_bottom * px_per_pt
        margin_left = section.margin_left * px_per_pt
        margin_right = section.margin_right * px_per_pt
        content_width = page_width - margin_left - margin_right

        cols = column_geometries(section, content_width, px_per_pt)
        n_cols = len(cols)

        if n_cols == 1:
            all_blocks: List[BlockBox] = []
            for element in elements:
                if isinstance(element, Paragraph):
                    all_blocks.extend(
                        self._layout_paragraph(
                            element, margin_left, content_width, px_per_pt
                        )
                    )
                elif isinstance(element, Table):
                    all_blocks.append(
                        self._layout_table(element, margin_left, content_width, px_per_pt)
                    )
            return self._paginate(
                all_blocks,
                page_width,
                page_height,
                margin_top,
                margin_bottom,
                margin_left,
                margin_right,
                section,
            )

        # Multi-column: fill column by column
        return self._layout_multicolumn(
            section,
            elements,
            page_width,
            page_height,
            margin_top,
            margin_bottom,
            margin_left,
            margin_right,
            cols,
            px_per_pt,
        )

    def _layout_multicolumn(
        self,
        section,
        elements,
        page_width,
        page_height,
        margin_top,
        margin_bottom,
        margin_left,
        margin_right,
        cols,
        px_per_pt,
    ) -> List[PageBox]:
        available = page_height - margin_top - margin_bottom
        pages: List[PageBox] = []

        def new_page() -> PageBox:
            return PageBox(
                width=page_width,
                height=page_height,
                margin_top=margin_top,
                margin_bottom=margin_bottom,
                margin_left=margin_left,
                margin_right=margin_right,
                section=section,
            )

        # Pre-layout all blocks at column 0 width (equal) — use first col width
        # For unequal cols, re-layout per column when placing (simplified: use each col width)
        page = new_page()
        col_idx = 0
        cursor_y = margin_top
        sep = section.col_sep

        for element in elements:
            col_x, col_w = cols[col_idx]
            abs_x = margin_left + col_x

            if isinstance(element, Paragraph):
                blocks = self._layout_paragraph(element, abs_x, col_w, px_per_pt)
            elif isinstance(element, Table):
                blocks = [self._layout_table(element, abs_x, col_w, px_per_pt)]
            else:
                continue

            for block in blocks:
                if cursor_y - margin_top + block.height > available + 0.5 and page.blocks:
                    col_idx += 1
                    cursor_y = margin_top
                    if col_idx >= len(cols):
                        # draw separators on finished page
                        if sep:
                            page._col_seps = [  # type: ignore[attr-defined]
                                margin_left + cols[i][0] + cols[i][1]
                                for i in range(len(cols) - 1)
                            ]
                        pages.append(page)
                        page = new_page()
                        col_idx = 0
                        cursor_y = margin_top
                    # Re-layout block for new column width
                    col_x, col_w = cols[col_idx]
                    abs_x = margin_left + col_x
                    if isinstance(block.element, Paragraph):
                        re_blocks = self._layout_paragraph(
                            block.element, abs_x, col_w, px_per_pt
                        )
                        block = re_blocks[0] if re_blocks else block
                    elif isinstance(block.element, Table):
                        block = self._layout_table(block.element, abs_x, col_w, px_per_pt)

                block.y = cursor_y
                self._finalize_block_coords(block)
                page.blocks.append(block)
                cursor_y += block.height

        if page.blocks or not pages:
            if sep and len(cols) > 1:
                page._col_seps = [  # type: ignore[attr-defined]
                    margin_left + cols[i][0] + cols[i][1]
                    for i in range(len(cols) - 1)
                ]
            pages.append(page)
        return pages

    def _page_size(self, section: Section, px_per_pt: float) -> tuple:
        """Resolve page dimensions, handling landscape orientation."""
        w = section.page_w * px_per_pt
        h = section.page_h * px_per_pt
        if section.orientation == "landscape" and w < h:
            w, h = h, w
        return w, h

    def _layout_paragraph(
        self,
        para: Paragraph,
        x_offset: float,
        content_width: float,
        px_per_pt: float,
    ) -> List[BlockBox]:
        """Layout a paragraph. May return multiple blocks if hard page breaks occur."""
        props = para.props
        # Character-unit indents take precedence over twip values; they are
        # relative to the paragraph mark font size (Word behaviour).
        mark_size = props.mark_font_size or 12.0
        if props.indent_left_chars is not None:
            indent_left = props.indent_left_chars / 100.0 * mark_size * px_per_pt
        else:
            indent_left = props.indent_left * px_per_pt
        indent_right = props.indent_right * px_per_pt

        # Numbering label
        list_label = ""
        list_level = None
        if props.num_id is not None:
            list_label, list_level = self.numbering_engine.next_label(
                props.num_id, props.num_level
            )
            if list_level:
                # Prefer numbering indents when present
                if list_level.left:
                    indent_left = list_level.left * px_per_pt
                if list_level.hanging:
                    props = para.props  # hanging applied via first_line_extra below

        first_line_extra = 0.0
        hanging_pt = 0.0
        if list_level and list_level.hanging:
            hanging_pt = list_level.hanging
            first_line_extra = -hanging_pt * px_per_pt
        elif props.hanging_chars is not None:
            hanging_pt = props.hanging_chars / 100.0 * mark_size
            first_line_extra = -hanging_pt * px_per_pt
        elif props.hanging_indent:
            first_line_extra = -props.hanging_indent * px_per_pt
        elif props.first_line_chars is not None:
            first_line_extra = props.first_line_chars / 100.0 * mark_size * px_per_pt
        elif props.first_line_indent:
            first_line_extra = props.first_line_indent * px_per_pt

        available_width = max(1.0, content_width - indent_left - indent_right)
        wrap_zones = self._para_wrap_zones(para, available_width, px_per_pt)

        lines = self.line_breaker.break_paragraph(
            para,
            available_width,
            px_per_pt,
            first_line_extra=first_line_extra,
            wrap_zones=wrap_zones,
        )

        # Prepend list label to first line
        if list_label and lines:
            label_props = None
            if para.runs and para.runs[0].text:
                label_props = para.runs[0].text.props
            from ..font.manager import FontManager
            font_size = (list_level.font_size if list_level and list_level.font_size else
                         (label_props.font_size if label_props else 12.0))
            font_name = (list_level.font_name if list_level and list_level.font_name else
                         (label_props.font_ascii if label_props else self.config.default_font_ascii))
            font = self.font_manager.get_font(font_name, font_size * px_per_pt, False, False)
            try:
                bbox = font.getbbox(list_label + " ")
                lw = float(bbox[2] - bbox[0])
                lh = float(bbox[3] - bbox[1])
            except Exception:
                lw, lh = len(list_label) * font_size * px_per_pt * 0.5, font_size * px_per_pt
            label_glyph = GlyphBox(
                text=list_label + " ",
                x=0.0,
                y=0.0,
                width=lw,
                height=lh,
                font=font,
                props=label_props,
            )
            # Shift existing glyphs and insert label at hanging position
            hang_px = hanging_pt * px_per_pt if hanging_pt else lw
            for g in lines[0].glyphs:
                g.x += hang_px
            label_glyph.x = 0.0
            lines[0].glyphs.insert(0, label_glyph)
            lines[0].width += hang_px

        # Split on hard page-break marker lines
        segments: List[List[LineBox]] = [[]]
        for line in lines:
            if getattr(line, "_page_break", False):
                segments.append([])
            else:
                segments[-1].append(line)

        blocks: List[BlockBox] = []
        for seg_idx, seg_lines in enumerate(segments):
            block = BlockBox(element=para)
            block.x = x_offset + indent_left
            block.width = available_width
            block.space_before = props.space_before * px_per_pt if seg_idx == 0 else 0.0
            block.space_after = props.space_after * px_per_pt if seg_idx == len(segments) - 1 else 0.0
            block.page_break_before = props.page_break_before if seg_idx == 0 else True

            content_x = block.x
            for i, line in enumerate(seg_lines):
                line_indent = first_line_extra if i == 0 else 0.0
                wrap_x = getattr(line, "_wrap_x", None)
                if wrap_x is not None:
                    line.x = content_x + wrap_x
                    line_avail = getattr(line, "_wrap_width", max(1.0, available_width - wrap_x))
                else:
                    line.x = content_x + line_indent
                    line_avail = available_width - line_indent
                if props.alignment in (Alignment.JUSTIFY, Alignment.DISTRIBUTE):
                    # TOC / tabbed lines: never stretch (Word keeps left text + right page#)
                    has_tab = bool(props.tab_stops) or any(
                        (g.text and g.text.startswith(".")) or (g.text == " " and g.width > 20)
                        for g in line.glyphs
                    )
                    has_tab = has_tab or any(r.tab for r in para.runs)
                    is_last = i == len(seg_lines) - 1
                    if has_tab:
                        pass
                    elif not (props.alignment == Alignment.JUSTIFY and is_last):
                        apply_justification(
                            [line],
                            max(1.0, line_avail),
                            props.alignment,
                            justify_last=True,
                        )
                else:
                    line.x += self._align_offset(props.alignment, line.width, line_avail)

            block.lines = seg_lines

            # Collect floating images / textboxes anchored to this paragraph
            self._collect_floats(para, block, px_per_pt)

            content_h = sum(line.height for line in seg_lines)
            if not seg_lines:
                # Empty paragraph: height of the paragraph mark (mark font size)
                # with the paragraph's line spacing rule applied (Word behaviour).
                font = self.font_manager.get_font(
                    self.config.default_font_east_asia,
                    mark_size * px_per_pt,
                    False,
                    False,
                )
                try:
                    metrics = font.getmetrics()
                    natural = float(metrics[0]) + float(metrics[1])
                except Exception:
                    natural = mark_size * px_per_pt
                content_h = self.line_breaker._line_height(props, natural, px_per_pt)
            block.height = content_h + block.space_before + block.space_after
            # Paragraph-relative floats that stick into/below this block reserve space
            for fb in block.float_boxes:
                if fb.relative_y in ("page", "margin", "topMargin", "bottomMargin"):
                    continue  # absolute — handled at pagination
                extent = fb.y + fb.height
                if extent <= 0:
                    continue
                if fb.wrap_type == "topAndBottom":
                    block.height = max(block.height, extent)
                elif fb.wrap_type == "inFrontOf":
                    # Cover header banners: push following text clear of the
                    # artwork. Pure-white padding at the bottom of the frame is
                    # not artwork — Word lets following text tuck underneath it,
                    # so reserve space only down to the visible content.
                    visible_h = fb.height * self._content_bottom_frac(fb.image)
                    block.height = max(block.height, fb.y + visible_h)
                elif fb.wrap_type in ("square", "tight") and not seg_lines:
                    block.height = max(block.height, extent)
                # behind: no flow impact
            blocks.append(block)

        return blocks if blocks else [BlockBox(element=para, height=12 * px_per_pt,
                                               x=x_offset, width=available_width)]

    def _para_wrap_zones(self, para: Paragraph, available_width: float, px_per_pt: float):
        """Build exclusion zones for floating images anchored to this paragraph."""
        from .float_layout import ExclusionZone
        from ..parse.units import Units

        zones = []
        for run in para.runs:
            if not run.image or run.image.wrap_type in ("inline", "behind", "inFrontOf"):
                continue
            img = run.image
            w = Units.emu_to_px(img.width_emu, self.config.dpi) if img.width_emu else 50
            h = Units.emu_to_px(img.height_emu, self.config.dpi) if img.height_emu else 50
            fx = (img.pos_x or 0.0) * px_per_pt
            fy = (img.pos_y or 0.0) * px_per_pt
            if img.wrap_type == "topAndBottom":
                zones.append(ExclusionZone(
                    y_start=fy, y_end=fy + h,
                    x_start=-1e9, x_end=1e9,
                    wrap_type="topAndBottom",
                ))
            else:
                zones.append(ExclusionZone(
                    y_start=fy, y_end=fy + h,
                    x_start=fx, x_end=fx + w,
                    wrap_type=img.wrap_type or "square",
                ))
        return zones

    def _collect_floats(self, para: Paragraph, block: BlockBox, px_per_pt: float) -> None:
        for run in para.runs:
            if run.image and run.image.wrap_type != "inline":
                img = run.image
                w = Units.emu_to_px(img.width_emu, self.config.dpi) if img.width_emu else 50
                h = Units.emu_to_px(img.height_emu, self.config.dpi) if img.height_emu else 50
                pil = None
                if img.data:
                    try:
                        pil = PILImage.open(BytesIO(img.data))
                    except Exception:
                        pil = None
                z = -1 if img.wrap_type == "behind" else (1 if img.wrap_type == "inFrontOf" else 0)
                fx = (img.pos_x or 0) * px_per_pt
                fy = (img.pos_y or 0) * px_per_pt
                block.float_boxes.append(FloatBox(
                    x=fx,
                    y=fy,
                    width=w,
                    height=h,
                    wrap_type=img.wrap_type,
                    image=pil,
                    z=z,
                    relative_x=img.relative_x or "column",
                    relative_y=img.relative_y or "paragraph",
                ))
            if run.textbox:
                tb = run.textbox
                w = Units.emu_to_px(tb.width_emu, self.config.dpi) if tb.width_emu else 120
                h = Units.emu_to_px(tb.height_emu, self.config.dpi) if tb.height_emu else 60
                inner_blocks = []
                for p in tb.paragraphs:
                    inner_blocks.extend(self._layout_paragraph(p, 0, max(1.0, w - 8), px_per_pt))
                block.textbox_boxes.append({
                    "x": tb.pos_x * px_per_pt,
                    "y": tb.pos_y * px_per_pt,
                    "width": w,
                    "height": h,
                    "blocks": inner_blocks,
                    "wrap_type": tb.wrap_type,
                    "fill": tb.fill,
                    "border": tb.border_color,
                })

    def _align_offset(self, alignment: Alignment, line_width: float, avail: float) -> float:
        """Horizontal offset for alignment."""
        if alignment == Alignment.CENTER:
            return max(0.0, (avail - line_width) / 2.0)
        if alignment == Alignment.RIGHT:
            return max(0.0, avail - line_width)
        # LEFT / JUSTIFY / DISTRIBUTE — justify expands in-place
        return 0.0

    def _content_bottom_frac(self, image) -> float:
        """Fraction of image height down to the last non-white row.

        Used for in-front cover banners: pure-white padding at the bottom of
        the frame should not push body text down. Returns 1.0 when unknown.
        """
        if image is None:
            return 1.0
        key = id(image)
        cached = getattr(self, "_content_frac_cache", None)
        if cached is None:
            cached = self._content_frac_cache = {}
        if key in cached:
            return cached[key]
        frac = 1.0
        try:
            rgba = image.convert("RGBA")
            white = PILImage.new("RGBA", rgba.size, (255, 255, 255, 255))
            white.paste(rgba, (0, 0), rgba)
            gray = white.convert("L")
            mask = gray.point(lambda p: 255 if p < 245 else 0)
            bbox = mask.getbbox()
            if bbox:
                frac = max(0.05, min(1.0, bbox[3] / float(image.size[1])))
            else:
                frac = 0.05  # fully white frame — keep a small sliver
        except Exception:
            frac = 1.0
        cached[key] = frac
        return frac

    def _layout_table(
        self, table: Table, x_offset: float, content_width: float, px_per_pt: float
    ) -> BlockBox:
        """Layout a table into a BlockBox wrapping TableBox."""
        indent = table.props.indent * px_per_pt
        avail = max(1.0, content_width - indent)
        table_box = self._layout_table_inner(table, avail, px_per_pt)

        # Table alignment
        x = x_offset + indent
        if table.props.alignment == "center":
            x = x_offset + indent + max(0.0, (avail - table_box.width) / 2.0)
        elif table.props.alignment == "right":
            x = x_offset + indent + max(0.0, avail - table_box.width)

        block = BlockBox(element=table, table_box=table_box)
        block.x = x
        block.width = table_box.width
        block.height = table_box.height
        return block

    def _layout_table_inner(self, table: Table, available_width: float, px_per_pt: float):
        return self.table_layout.layout(table, available_width, px_per_pt)

    def _paginate(
        self,
        blocks: List[BlockBox],
        page_width: float,
        page_height: float,
        margin_top: float,
        margin_bottom: float,
        margin_left: float,
        margin_right: float,
        section: Section,
    ) -> List[PageBox]:
        """Place blocks onto pages with absolute coordinates."""
        pages: List[PageBox] = []
        available = page_height - margin_top - margin_bottom

        def new_page() -> PageBox:
            return PageBox(
                width=page_width,
                height=page_height,
                margin_top=margin_top,
                margin_bottom=margin_bottom,
                margin_left=margin_left,
                margin_right=margin_right,
                section=section,
            )

        page = new_page()
        current_y = margin_top

        for i, block in enumerate(blocks):
            force_break = block.page_break_before and bool(page.blocks)

            # Soft overflow
            overflows = (current_y - margin_top + block.height) > available + 0.5

            # Orphan short block: fits alone but next block would be forced to a
            # new page — keep heading/caption with its following content.
            if (
                not force_break
                and not overflows
                and page.blocks
                and i + 1 < len(blocks)
                and not block.table_box
                and block.height <= 100
            ):
                next_b = blocks[i + 1]
                remain_after = available - (current_y - margin_top + block.height)
                if remain_after + 0.5 < next_b.height:
                    force_break = True

            if force_break or (overflows and page.blocks):
                pages.append(page)
                page = new_page()
                current_y = margin_top

            # All flow content (including empty spacers) skips past absolute
            # topAndBottom exclusion bands. Float host paragraphs are placed
            # before their floats are promoted, so they never jump below themselves.
            for fb in page.float_boxes:
                if fb.wrap_type != "topAndBottom":
                    continue
                band_top, band_bot = fb.y, fb.y + fb.height
                if current_y < band_bot and current_y + max(block.height, 1) > band_top:
                    current_y = max(current_y, band_bot)
            # May need a new page after skipping the band
            if (current_y - margin_top + block.height) > available + 0.5 and page.blocks:
                pages.append(page)
                page = new_page()
                current_y = margin_top
            # Re-check orphan rule after band skip
            elif (
                page.blocks
                and i + 1 < len(blocks)
                and not block.table_box
                and block.height <= 100
            ):
                next_b = blocks[i + 1]
                remain_after = available - (current_y - margin_top + block.height)
                if remain_after + 0.5 < next_b.height and (
                    current_y - margin_top + block.height
                ) <= available + 0.5:
                    pages.append(page)
                    page = new_page()
                    current_y = margin_top

            # Position block
            block.y = current_y
            self._finalize_block_coords(block)
            # Promote floats to page coordinates
            for fb in block.float_boxes:
                self._resolve_float_page_pos(
                    fb, block, page_width, page_height, margin_left, margin_top
                )
                page.float_boxes.append(fb)
            for tb in block.textbox_boxes:
                tb["x"] = block.x + tb["x"]
                tb["y"] = block.y + tb["y"]
                for ib in tb["blocks"]:
                    ib.y += tb["y"]
                    self._finalize_block_coords(ib)
                    for line in ib.lines:
                        for g in line.glyphs:
                            g.x += tb["x"]
                page.textbox_boxes.append(tb)
            page.blocks.append(block)
            current_y += block.height

        if page.blocks or not pages:
            pages.append(page)

        return pages

    def _resolve_float_page_pos(
        self,
        fb: FloatBox,
        block: BlockBox,
        page_width: float,
        page_height: float,
        margin_left: float,
        margin_top: float,
    ) -> None:
        """Convert float offsets to page-absolute coordinates based on relativeFrom."""
        rel_x = (fb.relative_x or "column").lower()
        rel_y = (fb.relative_y or "paragraph").lower()

        if rel_x in ("page",):
            # pos already page-absolute horizontally
            pass
        elif rel_x in ("margin", "leftmargin", "rightmargin"):
            fb.x = margin_left + fb.x
        else:
            # column / character / paragraph — relative to content/block
            fb.x = block.x + fb.x
        fb.abs_x = True

        if rel_y in ("page",):
            pass
        elif rel_y in ("margin", "topmargin", "bottommargin"):
            fb.y = margin_top + fb.y
        else:
            fb.y = block.y + fb.y
        fb.abs_y = True

    def _finalize_block_coords(self, block: BlockBox) -> None:
        """Set absolute glyph coordinates for rendering."""
        if block.table_box is not None:
            # Table content coordinates are relative to table; renderer adds block.x/y
            block.table_box.x = block.x
            block.table_box.y = block.y + block.space_before
            return

        y = block.y + block.space_before
        for line in block.lines:
            line.y = y
            baseline_y = y
            for glyph in line.glyphs:
                glyph.x = line.x + glyph.x
                offset = 0.0
                if glyph.props:
                    if glyph.props.vertical_align == "superscript":
                        offset = -line.ascent * 0.35
                    elif glyph.props.vertical_align == "subscript":
                        offset = line.ascent * 0.25
                    if glyph.props.position_offset:
                        offset -= glyph.props.position_offset * self.config.px_per_pt
                glyph.y = baseline_y + offset
            y += line.height
