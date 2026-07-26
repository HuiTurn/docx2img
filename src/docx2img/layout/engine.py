"""Layout engine - Converts IR to layout tree with pages"""

from dataclasses import dataclass, field
from typing import List, Any, Optional, Tuple

from ..config import Config
from ..model.document import DocumentModel
from ..model.paragraph import Paragraph
from ..model.table import Table
from ..model.section import Section
from ..model.enums import Alignment, SectionType
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
    page_break_after: bool = False


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
    # Zero-based physical page index within the owning section.  This is
    # distinct from page_number because numbering can restart at any value.
    section_page_index: int = 0
    # True when this page was created because of an explicit w:br type="page"
    # or w:pageBreakBefore.  Sparse-page merging must never fold such pages
    # into their predecessor — the author demanded a page break here.
    had_hard_break: bool = False


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
        self._grid_line_pitch_px: Optional[float] = None

    def layout(self) -> List[PageBox]:
        """Perform layout and return pages (supports multi-section)."""
        parts = self._split_sections()
        all_pages: List[PageBox] = []
        for idx, (section, elements) in enumerate(parts):
            # A `continuous` section break keeps flowing on the current page
            # instead of forcing a new one (matches Word/LibreOffice).  Only
            # possible when the physical page geometry is unchanged.
            cont_page = None
            cont_y = None
            if (
                idx > 0
                and section.section_type == SectionType.CONTINUOUS
                and all_pages
                and self._same_page_geometry(all_pages[-1], section)
            ):
                cont_page = all_pages[-1]
                cont_y = self._page_content_bottom(cont_page)
            # LibreOffice/Word balance the columns of a multi-column section
            # that ends with a continuous break into the next section.
            next_is_continuous = (
                idx + 1 < len(parts)
                and parts[idx + 1][0].section_type == SectionType.CONTINUOUS
            )
            pages = self._layout_section(
                section,
                elements,
                start_page=cont_page,
                start_y=cont_y,
                balance=next_is_continuous,
            )
            if cont_page is not None:
                # First returned page is the page we continued on; it is
                # already in all_pages.
                all_pages.extend(pages[1:])
            else:
                all_pages.extend(pages)

        # Attach once before sparse-page merging so decorated pages are not
        # accidentally absorbed.  We rebuild headers/footers after the merge,
        # because PAGE/NUMPAGES fields depend on the final page list.
        self._stamp_and_attach_pages(all_pages)

        # Merge trailing/sparse pages back into the previous page when:
        # - same physical page (identical width/height/margins)
        # - target page is sparse (<8% content height used)
        # - target page has no page-level floats, header, footer, or textboxes
        #   that would be lost by absorbing its blocks into the prior page.
        # This eliminates the small "stub" pages that LibreOffice does not
        # generate when a section ends mid-document.  Must run after
        # _attach_header_footer so we can detect header/footer presence.
        all_pages = self._merge_sparse_pages(all_pages)

        for page in all_pages:
            page.header_blocks.clear()
            page.footer_blocks.clear()
        self._stamp_and_attach_pages(all_pages)

        return all_pages if all_pages else [PageBox(width=595, height=842)]

    def _stamp_and_attach_pages(self, pages: List[PageBox]) -> None:
        """Apply final page labels, section-local indices, and decorations."""
        total = len(pages) if pages else 1
        previous_section = None
        current_number = 0
        section_page_index = 0

        for page in pages:
            section = page.section
            new_section = section is not previous_section
            if new_section:
                section_page_index = 0
                if section and section.page_num_start is not None:
                    current_number = section.page_num_start
                else:
                    current_number += 1
            else:
                section_page_index += 1
                current_number += 1

            page.page_number = current_number
            page.total_pages = total
            page.section_page_index = section_page_index
            self._attach_header_footer(page, section_page_index, total)
            previous_section = section

    @staticmethod
    def _block_has_ink(block: BlockBox) -> bool:
        """True when the block renders anything visible (text/image/table)."""
        if block.table_box is not None:
            return True
        for line in block.lines:
            for g in line.glyphs:
                if (g.text and g.text.strip()) or g.image is not None \
                        or g.math_box is not None:
                    return True
        return bool(block.float_boxes or block.textbox_boxes)

    @staticmethod
    def _is_invisible_section_break(element) -> bool:
        """Empty paragraph that only carries a sectPr.

        Word/LibreOffice do not render a blank line for the paragraph mark
        that ends a section when it has no visible content of its own, so
        laying it out as an empty line pushes everything below downwards.
        """
        if not isinstance(element, Paragraph) or element.section_break is None:
            return False
        for run in element.runs:
            if run.text is not None and run.text.text:
                return False
            if run.image is not None or run.math is not None \
                    or run.textbox is not None:
                return False
        return not element.group_items

    def _same_page_geometry(self, page: PageBox, section: Section) -> bool:
        """True when `section` uses the same physical page as `page`."""
        px_per_pt = self.config.px_per_pt
        w, h = self._page_size(section, px_per_pt)
        return abs(page.width - w) < 0.5 and abs(page.height - h) < 0.5

    @staticmethod
    def _page_content_bottom(page: PageBox) -> float:
        """Y coordinate where new flow content may start on `page`."""
        if not page.blocks:
            return page.margin_top
        return max(b.y + b.height for b in page.blocks)

    @staticmethod
    def _translate_block(block: BlockBox, dx: float, dy: float) -> None:
        """Shift an already-finalized block (and its content) by dx/dy."""
        block.x += dx
        block.y += dy
        if block.table_box is not None:
            block.table_box.x += dx
            block.table_box.y += dy
        for line in block.lines:
            line.x += dx
            line.y += dy
            for g in line.glyphs:
                g.x += dx
                g.y += dy
        for fb in block.float_boxes:
            fb.x += dx
            fb.y += dy
        for tb in block.textbox_boxes:
            tb["x"] += dx
            tb["y"] += dy
            for ib in tb["blocks"]:
                ib.y += dy
                for line in ib.lines:
                    line.x += dx
                    line.y += dy
                    for g in line.glyphs:
                        g.x += dx
                        g.y += dy

    @staticmethod
    def _merge_sparse_pages(pages: List["PageBox"]) -> List["PageBox"]:
        """Fold sparse trailing pages into the previous one when safe.

        Section boundaries in OOXML sometimes force a new page even when only
        a few small paragraphs are left over. LibreOffice visually appends
        those onto the prior page; we mirror that here to avoid emitting a
        near-empty page purely because of section bookkeeping.

        We only walk *trailing* sparse pages: a page is only a merge candidate
        when the pages after it are not also sparse (avoids cascading merges
        in fixtures that legitimately produce many sparse pages).
        """
        if len(pages) < 2:
            return pages

        result: List[PageBox] = list(pages)
        # Fold at most one trailing page into its predecessor. A cascade would
        # collapse fixtures that legitimately emit multiple short pages.
        if len(result) >= 2:
            prev = result[-2]
            cur = result[-1]
            usable_h = prev.height - prev.margin_top - prev.margin_bottom
            prev_bottom = (
                max((b.y + b.height for b in prev.blocks), default=prev.margin_top)
            )
            cur_top = min((b.y for b in cur.blocks), default=cur.margin_top)
            cur_bottom = max(
                (b.y + b.height for b in cur.blocks), default=cur.margin_top
            )
            cur_used = max(0.0, cur_bottom - cur_top)

            same_geometry = (
                abs(prev.width - cur.width) < 0.5
                and abs(prev.height - cur.height) < 0.5
                and abs(prev.margin_top - cur.margin_top) < 0.5
                and abs(prev.margin_bottom - cur.margin_bottom) < 0.5
                and abs(prev.margin_left - cur.margin_left) < 0.5
                and abs(prev.margin_right - cur.margin_right) < 0.5
            )
            cur_is_tiny = usable_h > 0 and cur_used / usable_h < 0.15
            prev_has_room = (
                usable_h > 0
                and prev_bottom + cur_used <= prev.height - prev.margin_bottom + 0.5
            )
            no_page_decoration = (
                not cur.header_blocks
                and not cur.footer_blocks
                and not cur.float_boxes
                and not cur.textbox_boxes
                and not prev.float_boxes
                and not prev.textbox_boxes
            )

            if not (same_geometry and cur_is_tiny and prev_has_room
                    and no_page_decoration
                    and not cur.had_hard_break):
                return result

            y = prev_bottom
            dy = y - cur_top
            for b in cur.blocks:
                # Lines, glyphs and table origins are already absolute at this
                # stage, so every descendant must move with its parent block.
                LayoutEngine._translate_block(b, 0.0, dy)
                prev.blocks.append(b)
            result.pop()
        return result

    def _attach_header_footer(
        self, page: PageBox, section_page_index: int, total: int
    ) -> None:
        import copy
        section = page.section or Section()
        px_per_pt = self.config.px_per_pt
        self._grid_line_pitch_px = (
            section.doc_grid_line_pitch * px_per_pt
            if section.doc_grid_line_pitch
            and section.doc_grid_type in ("lines", "linesAndChars")
            else None
        )
        page_num = page.page_number

        def pick(bodies: dict, refs_prefer: list) -> list:
            for key in refs_prefer:
                if key in bodies and bodies[key]:
                    return bodies[key]
            return bodies.get("default") or []

        is_first = section_page_index == 0
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

    def _layout_section(
        self,
        section: Section,
        elements: list,
        start_page: Optional[PageBox] = None,
        start_y: Optional[float] = None,
        balance: bool = False,
    ) -> List[PageBox]:
        px_per_pt = self.config.px_per_pt
        self._grid_line_pitch_px = (
            section.doc_grid_line_pitch * px_per_pt
            if section.doc_grid_line_pitch
            and section.doc_grid_type in ("lines", "linesAndChars")
            else None
        )
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
                if self._is_invisible_section_break(element):
                    continue
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
                start_page=start_page,
                start_y=start_y,
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
            start_page=start_page,
            start_y=start_y,
            balance=balance,
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
        start_page: Optional[PageBox] = None,
        start_y: Optional[float] = None,
        balance: bool = False,
    ) -> List[PageBox]:
        bottom_limit = page_height - margin_bottom
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

        def set_seps(p: PageBox) -> None:
            if sep and len(cols) > 1:
                p._col_seps = [  # type: ignore[attr-defined]
                    margin_left + cols[i][0] + cols[i][1]
                    for i in range(len(cols) - 1)
                ]

        # Pre-layout all blocks at column 0 width (equal) — use first col width
        # For unequal cols, re-layout per column when placing (simplified: use each col width)
        if start_page is not None:
            page = start_page
            col_top = start_y if start_y is not None else margin_top
        else:
            page = new_page()
            col_top = margin_top
        col_idx = 0
        cursor_y = col_top
        col_block_count = 0  # blocks placed in the current column
        region_blocks: List[BlockBox] = []  # this page's column-region blocks
        sep = section.col_sep

        for element in elements:
            if self._is_invisible_section_break(element):
                continue
            col_x, col_w = cols[col_idx]
            abs_x = margin_left + col_x

            if isinstance(element, Paragraph):
                blocks = self._layout_paragraph(element, abs_x, col_w, px_per_pt)
            elif isinstance(element, Table):
                blocks = [self._layout_table(element, abs_x, col_w, px_per_pt)]
            else:
                continue

            for block in blocks:
                if cursor_y + block.height > bottom_limit + 0.5 and col_block_count:
                    col_idx += 1
                    cursor_y = col_top
                    col_block_count = 0
                    if col_idx >= len(cols):
                        # draw separators on finished page
                        set_seps(page)
                        pages.append(page)
                        page = new_page()
                        col_idx = 0
                        col_top = margin_top
                        cursor_y = margin_top
                        region_blocks = []
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
                region_blocks.append(block)
                cursor_y += block.height
                col_block_count += 1
                # A hard page-break inside a paragraph also opens a new
                # logical page even within a multi-column section.  Mark it
                # so the merge pass leaves it alone.
                if getattr(block.element, "page_break_marker", False):
                    set_seps(page)
                    pages.append(page)
                    page = new_page()
                    page.had_hard_break = True
                    col_idx = 0
                    col_top = margin_top
                    cursor_y = margin_top
                    col_block_count = 0
                    region_blocks = []

        if balance and len(cols) > 1 and region_blocks:
            self._balance_columns(
                region_blocks, cols, margin_left, col_top
            )

        if page.blocks or not pages:
            set_seps(page)
            pages.append(page)
        return pages

    def _balance_columns(
        self,
        blocks: List[BlockBox],
        cols,
        margin_left: float,
        col_top: float,
    ) -> None:
        """Redistribute the final column region so columns end evenly.

        Word/LibreOffice balance the columns of a multi-column section that
        flows into a following `continuous` section.  Blocks were filled
        column-by-column; here we re-assign them (equal-width columns only)
        so each column carries roughly total_height / n_cols.
        """
        widths = {round(w, 2) for _, w in cols}
        if len(widths) > 1:
            return  # unequal columns: keep sequential fill
        n = len(cols)
        total_h = sum(b.height for b in blocks)
        target = total_h / n

        col_idx = 0
        used = 0.0
        for block in blocks:
            # Move to next column once the current one reached its share
            # (never on the first block of a column, never past last column).
            if used > 0 and used + block.height / 2 > target and col_idx < n - 1:
                col_idx += 1
                used = 0.0
            new_x = margin_left + cols[col_idx][0]
            new_y = col_top + used
            self._translate_block(block, new_x - block.x, new_y - block.y)
            used += block.height

    def _page_size(self, section: Section, px_per_pt: float) -> tuple:
        """Resolve page dimensions, handling landscape orientation.

        Layout keeps fractional pt→px sizes. Final bitmap ceil happens in
        ``RenderCanvas`` so Word PDF→pdftoppm page pixels match without
        perturbing pagination.
        """
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
        apply_doc_grid: bool = True,
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
            grid_line_pitch_px=(
                self._grid_line_pitch_px if apply_doc_grid else None
            ),
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

        def _segment_has_ink(seg_lines: List[LineBox]) -> bool:
            for line in seg_lines:
                for g in line.glyphs:
                    if g.image is not None or getattr(g, "math_box", None) is not None:
                        return True
                    if g.text and g.text.strip():
                        return True
            return False

        # Empty segments only arise around manual page-break markers.  Drop them
        # so they do not create blank pages, but preserve the break intent via
        # page_break_after on the preceding displayed segment or by forcing the
        # following displayed segment to start a new page.
        first_displayed_idx: Optional[int] = None
        kept_segments: List[Tuple[int, List[LineBox]]] = []
        for seg_idx, seg_lines in enumerate(segments):
            if seg_lines and _segment_has_ink(seg_lines):
                if first_displayed_idx is None:
                    first_displayed_idx = seg_idx
                kept_segments.append((seg_idx, seg_lines))
            else:
                # Empty/inkless segment after a manual break: force the previous
                # kept block to break after itself.  If there is no previous
                # block, the break intent is carried by the next displayed segment.
                if kept_segments:
                    kept_segments[-1][1].append("__page_break_after__")  # marker

        # A paragraph may consist solely of anchored drawings/textboxes.  It
        # still needs a block so _collect_floats/group_items can promote those
        # objects to page coordinates; otherwise an inkless text line causes
        # the entire drawing group to disappear.
        has_anchored_content = bool(getattr(para, "group_items", None)) or any(
            (run.image is not None and run.image.wrap_type != "inline")
            or run.textbox is not None
            for run in para.runs
        )
        if not kept_segments and has_anchored_content:
            first_displayed_idx = 0
            kept_segments.append((0, []))
        has_leading_break = first_displayed_idx is not None and first_displayed_idx > 0

        blocks: List[BlockBox] = []
        for kidx, (seg_idx, seg_lines) in enumerate(kept_segments):
            is_first_displayed = seg_idx == first_displayed_idx
            is_last_segment = seg_idx == len(segments) - 1
            has_break_after = "__page_break_after__" in seg_lines
            if has_break_after:
                seg_lines = [ln for ln in seg_lines if ln != "__page_break_after__"]

            block = BlockBox(element=para)
            block.x = x_offset + indent_left
            block.width = available_width
            block.space_before = props.space_before * px_per_pt if is_first_displayed else 0.0
            block.space_after = props.space_after * px_per_pt if is_last_segment else 0.0
            if is_first_displayed:
                block.page_break_before = bool(props.page_break_before) or has_leading_break
            else:
                block.page_break_before = True
            block.page_break_after = has_break_after or (not is_last_segment)

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

            # Anchored objects belong to the paragraph, not to every segment
            # produced by a manual page break. Promote them exactly once.
            if kidx == 0:
                self._collect_floats(para, block, px_per_pt)

            # Process group_items from WordprocessingGroup (wpg:wgp).
            if kidx == 0 and getattr(para, "group_items", None):
                for gi in para.group_items:
                    gi_type = gi.get("type")
                    gi_data = gi.get("data")
                    if gi_type == "textbox" and gi_data:
                        tb = gi_data
                        w = Units.emu_to_px(tb.width_emu, self.config.dpi) if tb.width_emu else 120
                        h = Units.emu_to_px(tb.height_emu, self.config.dpi) if tb.height_emu else 60
                        inner_blocks = []
                        for p in tb.paragraphs:
                            inner_blocks.extend(
                                self._layout_paragraph(
                                    p,
                                    0,
                                    max(1.0, w - 8),
                                    px_per_pt,
                                    apply_doc_grid=False,
                                )
                            )
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
                    elif gi_type == "line" and gi_data:
                        block.textbox_boxes.append({
                            "x": gi_data["x"] * px_per_pt,
                            "y": gi_data["y"] * px_per_pt,
                            "width": gi_data["width"] * px_per_pt,
                            "height": max(gi_data["height"] * px_per_pt, 1.0),
                            "blocks": [],
                            "line_shape": {
                                "line_width_emu": gi_data.get("line_width", 12700),
                                "color": gi_data.get("color", (0, 0, 0)),
                            },
                            "wrap_type": "inFrontOf",
                        })

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
                content_h = self.line_breaker._line_height(
                    props,
                    natural,
                    px_per_pt,
                    grid_line_pitch_px=(
                        self._grid_line_pitch_px if apply_doc_grid else None
                    ),
                )
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
            # Group items (textboxes/lines from wpg:wgp) can extend beyond the
            # inline content area — expand block height so following paragraphs
            # don't overlap them.
            for tb in block.textbox_boxes:
                gi_bottom = tb["y"] + tb["height"]
                if gi_bottom > block.height:
                    block.height = gi_bottom
            blocks.append(block)

        # Paragraph consisting solely of manual page-break(s): emit a marker
        # block so the break is not lost.  LibreOffice still gives such an
        # empty paragraph its paragraph-mark line height — when that line does
        # not fit on the current page, the whole (invisible) paragraph moves
        # to the next page and the break fires from there, producing a blank
        # page.  A zero-height marker would instead always "fit", losing that
        # blank page (tracked-changes golden page 2).
        if not blocks and len(segments) > 1:
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
            mark_h = self.line_breaker._line_height(
                props,
                natural,
                px_per_pt,
                grid_line_pitch_px=(
                    self._grid_line_pitch_px if apply_doc_grid else None
                ),
            )
            block = BlockBox(
                element=para,
                x=x_offset + indent_left,
                width=available_width,
                height=mark_h,
            )
            block.page_break_before = bool(props.page_break_before)
            block.page_break_after = True
            block.space_before = 0.0
            block.space_after = props.space_after * px_per_pt
            block.height += block.space_after
            blocks.append(block)

        if blocks:
            return blocks

        # Ordinary empty paragraph: retain the paragraph-mark line.  LibreOffice
        # collapses the paragraph spacing on an otherwise empty body paragraph
        # (important for DOCX files whose defaults add 8–10pt after every
        # paragraph), but still applies a real document grid to the mark line.
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
        mark_h = self.line_breaker._line_height(
            props,
            natural,
            px_per_pt,
            grid_line_pitch_px=(
                self._grid_line_pitch_px if apply_doc_grid else None
            ),
        )
        return [
            BlockBox(
                element=para,
                height=mark_h,
                x=x_offset + indent_left,
                width=available_width,
                page_break_before=bool(props.page_break_before),
            )
        ]

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
                    inner_blocks.extend(
                        self._layout_paragraph(
                            p,
                            0,
                            max(1.0, w - 8),
                            px_per_pt,
                            apply_doc_grid=False,
                        )
                    )
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
        start_page: Optional[PageBox] = None,
        start_y: Optional[float] = None,
    ) -> List[PageBox]:
        """Place blocks onto pages with absolute coordinates.

        When `start_page` is given (continuous section break), content keeps
        flowing on that page starting at `start_y`; the page is returned as
        the first element of the result.
        """
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

        if start_page is not None:
            page = start_page
            current_y = start_y if start_y is not None else margin_top
        else:
            page = new_page()
            current_y = margin_top

        def _apply_spacing_constraints(block: BlockBox, at_top: bool) -> None:
            """Adjust block height for page-top space_before suppression and
            bottom-of-page space_after truncation."""
            # Suppress space_before at the top of a page/column.
            if at_top and block.space_before > 0:
                block.height -= block.space_before
                block.space_before = 0.0
            # Truncate trailing space_after if only the whitespace overflows.
            # A break-only paragraph is the exception: Word keeps its
            # paragraph spacing when deciding whether the invisible mark fits.
            # If that spacing crosses the boundary, the mark moves to a blank
            # page and its manual break starts the following content on the
            # next page.
            keep_break_mark_spacing = (
                block.page_break_after and not self._block_has_ink(block)
            )
            if block.space_after > 0 and not keep_break_mark_spacing:
                content_h = block.height - block.space_after
                if content_h >= 0 and (current_y - margin_top + content_h) <= available + 0.5 \
                        and (current_y - margin_top + block.height) > available + 0.5:
                    block.height = content_h
                    block.space_after = 0.0

        for i, block in enumerate(blocks):
            at_page_top = abs(current_y - margin_top) < 0.5
            _apply_spacing_constraints(block, at_page_top)

            force_break = block.page_break_before and bool(page.blocks)

            # Soft overflow
            overflows = (current_y - margin_top + block.height) > available + 0.5

            # Orphan short block: fits alone but next block would be forced to a
            # new page — keep heading/caption with its following content.
            # Invisible (empty) neighbours never trigger this: an empty
            # paragraph spilling over is not worth dragging real content along.
            if (
                not force_break
                and not overflows
                and page.blocks
                and i + 1 < len(blocks)
                and not block.table_box
                and block.height <= 100
                and self._block_has_ink(block)
            ):
                next_b = blocks[i + 1]
                remain_after = available - (current_y - margin_top + block.height)
                if remain_after + 0.5 < next_b.height and self._block_has_ink(next_b):
                    force_break = True

            if force_break or (overflows and page.blocks):
                pages.append(page)
                page = new_page()
                if force_break:
                    page.had_hard_break = True
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
                and self._block_has_ink(block)
            ):
                next_b = blocks[i + 1]
                remain_after = available - (current_y - margin_top + block.height)
                if remain_after + 0.5 < next_b.height \
                        and self._block_has_ink(next_b) and (
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

            # Manual page break after this block.
            if block.page_break_after and i + 1 < len(blocks):
                pages.append(page)
                page = new_page()
                page.had_hard_break = True
                current_y = margin_top

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
