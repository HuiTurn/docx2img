"""Table layout engine — column widths, merges, cell content."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Any, Callable, Dict

from ..config import Config
from ..model.table import Table, Row, Cell, BorderDef, TableProps
from ..model.paragraph import Paragraph
from ..model.enums import VerticalMerge, BorderStyle, Alignment
from .line_breaker import LineBreaker
from .justify import apply_justification


@dataclass
class CellBox:
    """Laid-out cell (origin cell for merges)."""
    cell: Optional[Cell] = None
    col_start: int = 0
    col_span: int = 1
    row_start: int = 0
    row_span: int = 1
    is_origin: bool = True
    v_merged: bool = False  # covered by vertical merge (not origin)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    content_height: float = 0.0
    lines: List[Any] = field(default_factory=list)  # LineBox from paragraphs
    nested_blocks: List[Any] = field(default_factory=list)  # nested TableBox / BlockBox
    padding: Dict[str, float] = field(default_factory=dict)
    shading: Optional[tuple] = None
    borders: Dict[str, BorderDef] = field(default_factory=dict)
    vertical_align: str = "top"


@dataclass
class TableBox:
    """Laid-out table."""
    grid: List[List[Optional[CellBox]]] = field(default_factory=list)
    col_widths: List[float] = field(default_factory=list)
    row_heights: List[float] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    table: Optional[Table] = None
    # Flat list of origin cells for easy rendering
    cells: List[CellBox] = field(default_factory=list)


class TableLayoutEngine:
    """Compute table geometry and lay out cell contents."""

    def __init__(
        self,
        config: Config,
        line_breaker: LineBreaker,
        layout_paragraph_fn: Callable,
        layout_table_fn: Optional[Callable] = None,
    ):
        self.config = config
        self.line_breaker = line_breaker
        self._layout_para = layout_paragraph_fn
        self._layout_table = layout_table_fn

    def layout(self, table: Table, available_width: float, px_per_pt: float) -> TableBox:
        n_cols = self._count_cols(table)
        col_widths = self._calc_col_widths(table, available_width, px_per_pt, n_cols)
        n_cols = len(col_widths)
        n_rows = len(table.rows)

        grid = self._build_grid(table, n_cols)
        self._resolve_row_spans(grid, n_rows, n_cols)

        for r in range(n_rows):
            for c in range(n_cols):
                box = grid[r][c]
                if box is None or not box.is_origin or box.v_merged:
                    continue
                cell_w = sum(col_widths[box.col_start : box.col_start + box.col_span])
                self._layout_cell_content(box, cell_w, px_per_pt, table.props, n_rows, n_cols)

        row_heights = self._calc_row_heights(grid, table.rows, px_per_pt)

        table_box = TableBox(
            grid=grid,
            col_widths=col_widths,
            row_heights=row_heights,
            width=sum(col_widths),
            height=sum(row_heights),
            table=table,
        )

        for box in [
            grid[r][c]
            for r in range(n_rows)
            for c in range(n_cols)
            if grid[r][c] and grid[r][c].is_origin and not grid[r][c].v_merged
        ]:
            span_h = sum(row_heights[box.row_start : box.row_start + box.row_span])
            span_w = sum(col_widths[box.col_start : box.col_start + box.col_span])
            box.x = sum(col_widths[: box.col_start])
            box.y = sum(row_heights[: box.row_start])
            box.width = span_w
            box.height = span_h
            self._apply_vertical_align(box)
            table_box.cells.append(box)

        return table_box

    def _count_cols(self, table: Table) -> int:
        n = len(table.col_widths)
        for row in table.rows:
            n = max(n, sum(max(1, c.props.grid_span) for c in row.cells))
        return max(n, 1)

    def _calc_col_widths(
        self, table: Table, available_width: float, px_per_pt: float, n_cols: int
    ) -> List[float]:
        target = available_width
        if table.props.width_type == "dxa" and table.props.width > 0:
            target = min(available_width, table.props.width * px_per_pt)
        elif table.props.width_type == "pct" and table.props.width > 0:
            target = available_width * (table.props.width / 100.0)

        # Autofit layout: size columns by content.  Word/LibreOffice ignore the
        # nominal grid widths when w:tblLayout@w:type="autofit" and instead
        # fit columns to their contents, then distribute any leftover width.
        if table.props.layout == "autofit":
            return self._autofit_col_widths(table, target, px_per_pt, n_cols)

        if table.col_widths:
            widths_pt = list(table.col_widths)
        else:
            widths_pt = [0.0] * n_cols
            if table.rows:
                c = 0
                for cell in table.rows[0].cells:
                    span = max(1, cell.props.grid_span)
                    each = 0.0
                    if cell.props.width and cell.props.width_type == "dxa":
                        each = cell.props.width / span
                    for _ in range(span):
                        if c < n_cols:
                            widths_pt[c] = each
                            c += 1

        while len(widths_pt) < n_cols:
            widths_pt.append(0.0)
        widths_pt = widths_pt[:n_cols]

        px_widths = [w * px_per_pt for w in widths_pt]
        total = sum(px_widths)

        if total <= 0:
            return [target / n_cols] * n_cols

        if abs(total - target) > 0.5:
            scale = target / total
            px_widths = [w * scale for w in px_widths]

        return px_widths

    def _measure_text_width(self, text: str, props, px_per_pt: float) -> float:
        """Return pixel width of a text run using the resolved font."""
        if not text:
            return 0.0
        size_pt = props.font_size or 12.0
        if props.vertical_align in ("superscript", "subscript"):
            size_pt *= 0.65
        name = (
            props.font_ascii
            or props.font_h_ansi
            or props.font_east_asia
            or self.config.default_font_ascii
        )
        font = self.line_breaker.font_manager.get_font(
            name, size_pt * px_per_pt, bool(props.bold), bool(props.italic)
        )
        try:
            bbox = font.getbbox(text)
            w = float(bbox[2] - bbox[0])
        except Exception:
            w = len(text) * size_pt * px_per_pt * 0.5
        if props.scale and props.scale != 100:
            w *= props.scale / 100.0
        if props.spacing:
            w += props.spacing * px_per_pt * max(0, len(text) - 1)
        return w

    def _cell_min_width(self, cell, px_per_pt: float) -> float:
        """Minimum pixel width needed for a cell's unwrapped content + padding."""
        padding_left = cell.props.margins.get("left", 5.4) * px_per_pt
        padding_right = cell.props.margins.get("right", 5.4) * px_per_pt
        content_w = 0.0
        for block in cell.blocks:
            if not isinstance(block, Paragraph):
                continue
            para_w = 0.0
            for run in block.runs:
                if run.text and run.text.text:
                    para_w += self._measure_text_width(
                        run.text.text, run.text.props, px_per_pt
                    )
            content_w = max(content_w, para_w)
        return content_w + padding_left + padding_right

    def _autofit_col_widths(
        self, table: Table, target: float, px_per_pt: float, n_cols: int
    ) -> List[float]:
        """Compute content-fitted column widths for autofit tables.

        LibreOffice's autofit starts from the table's grid-column widths and
        expands columns whose content needs more space; it does not shrink
        columns below the grid width.  We mirror that by taking the larger of
        the grid width and the content minimum for each column.
        """
        # Start from grid widths (converted to pixels).
        grid_px = [0.0] * n_cols
        for i, w in enumerate(table.col_widths or []):
            if i < n_cols:
                grid_px[i] = w * px_per_pt

        # Content minimums, handling spans by sharing across columns.
        content_mins = [0.0] * n_cols
        for row in table.rows:
            c = 0
            for cell in row.cells:
                span = max(1, cell.props.grid_span)
                if c + span > n_cols:
                    span = n_cols - c
                cell_min = self._cell_min_width(cell, px_per_pt)
                share = cell_min / span
                for sc in range(span):
                    if c + sc < n_cols:
                        content_mins[c + sc] = max(content_mins[c + sc], share)
                c += span

        # Column width is at least the grid width and at least the content min.
        abs_min = 30.0
        min_widths = [max(grid_px[i], content_mins[i], abs_min) for i in range(n_cols)]

        total_min = sum(min_widths)
        if total_min <= 0:
            return [target / n_cols] * n_cols

        if total_min >= target - 0.5:
            # Content-fitted widths exceed the page width.  Scaling them down
            # uniformly re-introduces wrapping, so keep the grid widths as a
            # fallback.  This preserves the large-document pagination while
            # still allowing narrower tables (like table-document) to expand.
            grid_total = sum(grid_px)
            if grid_total > 0:
                scale = target / grid_total
                return [w * scale for w in grid_px]
            return [target / n_cols] * n_cols

        # Distribute leftover space equally.
        extra = target - total_min
        per_col = extra / n_cols
        return [w + per_col for w in min_widths]

    def _build_grid(
        self, table: Table, n_cols: int
    ) -> List[List[Optional[CellBox]]]:
        n_rows = len(table.rows)
        # Ensure n_cols is enough
        for row in table.rows:
            need = sum(c.props.grid_span for c in row.cells)
            n_cols = max(n_cols, need)
        if n_cols == 0:
            n_cols = 1

        grid: List[List[Optional[CellBox]]] = [[None] * n_cols for _ in range(n_rows)]

        for r, row in enumerate(table.rows):
            c = 0
            for cell in row.cells:
                while c < n_cols and grid[r][c] is not None:
                    c += 1
                if c >= n_cols:
                    break

                span = max(1, cell.props.grid_span)
                is_continue = cell.props.v_merge == VerticalMerge.CONTINUE

                if is_continue:
                    # Covered by a RESTART above — mark placeholder if empty
                    for sc in range(span):
                        if c + sc < n_cols and grid[r][c + sc] is None:
                            grid[r][c + sc] = CellBox(
                                cell=cell,
                                col_start=c,
                                col_span=span,
                                row_start=r,
                                is_origin=False,
                                v_merged=True,
                            )
                    c += span
                    continue

                origin = CellBox(
                    cell=cell,
                    col_start=c,
                    col_span=span,
                    row_start=r,
                    row_span=1,
                    is_origin=True,
                    v_merged=False,
                    shading=cell.props.shading,
                    borders=dict(cell.props.borders),
                    vertical_align=cell.props.vertical_align,
                )
                for sc in range(span):
                    if c + sc < n_cols:
                        grid[r][c + sc] = origin if sc == 0 else CellBox(
                            cell=cell,
                            col_start=c,
                            col_span=span,
                            row_start=r,
                            is_origin=False,
                            v_merged=False,  # horizontal cover
                        )
                c += span

        return grid

    def _resolve_row_spans(
        self, grid: List[List[Optional[CellBox]]], n_rows: int, n_cols: int
    ) -> None:
        """Expand RESTART cells downward through CONTINUE."""
        for r in range(n_rows):
            for c in range(n_cols):
                box = grid[r][c]
                if not box or not box.is_origin or box.v_merged:
                    continue
                if box.cell and box.cell.props.v_merge == VerticalMerge.RESTART:
                    rr = r + 1
                    while rr < n_rows:
                        below = grid[rr][c]
                        if (
                            below
                            and below.cell
                            and below.cell.props.v_merge == VerticalMerge.CONTINUE
                        ):
                            box.row_span += 1
                            # Mark covered cells
                            for sc in range(box.col_span):
                                if c + sc < n_cols:
                                    grid[rr][c + sc] = CellBox(
                                        cell=below.cell,
                                        col_start=box.col_start,
                                        col_span=box.col_span,
                                        row_start=box.row_start,
                                        row_span=box.row_span,
                                        is_origin=False,
                                        v_merged=True,
                                    )
                            rr += 1
                        else:
                            break

    def _layout_cell_content(
        self,
        box: CellBox,
        cell_width: float,
        px_per_pt: float,
        table_props: TableProps,
        n_rows: int = 1,
        n_cols: int = 1,
    ) -> None:
        cell = box.cell
        if not cell:
            return

        margins = dict(DEFAULT_MARGINS)
        margins.update(table_props.cell_margins or {})
        margins.update(cell.props.margins or {})
        box.padding = {k: v * px_per_pt for k, v in margins.items()}

        # Effective borders: tcBorders > tbl outer (edge cells) > insideH/V > default
        tb = table_props.borders or {}
        cb = cell.props.borders or {}
        is_outer = {
            "top": box.row_start == 0,
            "bottom": box.row_start + box.row_span >= n_rows,
            "left": box.col_start == 0,
            "right": box.col_start + box.col_span >= n_cols,
        }
        borders = {}
        for side, inside_key in (
            ("top", "insideH"),
            ("bottom", "insideH"),
            ("left", "insideV"),
            ("right", "insideV"),
        ):
            if side in cb:
                borders[side] = cb[side]
            elif is_outer[side] and side in tb:
                borders[side] = tb[side]
            elif not is_outer[side] and inside_key in tb:
                borders[side] = tb[inside_key]
            elif side in tb:
                borders[side] = tb[side]
            else:
                borders[side] = BorderDef(
                    style=BorderStyle.SINGLE, width=0.5, color=(0, 0, 0)
                )
        box.borders = borders

        content_w = max(
            1.0,
            cell_width - box.padding.get("left", 0) - box.padding.get("right", 0),
        )

        y = 0.0
        lines = []
        nested = []
        for block in cell.blocks:
            if isinstance(block, Paragraph):
                props = block.props
                first_extra = 0.0
                if props.first_line_indent:
                    first_extra = props.first_line_indent * px_per_pt
                elif props.hanging_indent:
                    first_extra = -props.hanging_indent * px_per_pt

                para_lines = self.line_breaker.break_paragraph(
                    block, content_w, px_per_pt, first_line_extra=first_extra
                )

                for i, line in enumerate(para_lines):
                    indent = first_extra if i == 0 else 0.0
                    line.x = indent
                    line_avail = max(1.0, content_w - indent)
                    align = props.alignment or Alignment.LEFT
                    if align in (Alignment.JUSTIFY, Alignment.DISTRIBUTE):
                        is_last = i == len(para_lines) - 1
                        if not (align == Alignment.JUSTIFY and is_last):
                            apply_justification(
                                [line], line_avail, align, justify_last=True
                            )
                    elif align == Alignment.CENTER:
                        line.x = indent + max(0.0, (line_avail - line.width) / 2.0)
                    elif align == Alignment.RIGHT:
                        line.x = indent + max(0.0, line_avail - line.width)
                    line.y = y
                    y += line.height
                    lines.append(line)
                # Cell paragraph after-spacing, matched to LibreOffice golden:
                # - between blocks: full space_after (paragraph separation)
                # - trailing block, explicit spacing (style chain / direct):
                #   halved — LO keeps part of it (0.5x matches large-document
                #   50/50, whose Normal style sets after=160 explicitly)
                # - trailing block, docDefaults-only spacing: mostly dropped
                #   (0.125x) — LO compresses such rows (table-document golden
                #   rows carry almost none of the docDefaults after=10pt;
                #   0 under-paginates tracked-changes, 0.25 over-paginates
                #   table-document, 0.125 satisfies both).
                if block is not cell.blocks[-1]:
                    y += props.space_after * px_per_pt
                elif not getattr(props, "space_after_default_only", False):
                    y += props.space_after * px_per_pt * 0.5
                else:
                    y += props.space_after * px_per_pt * 0.125
            else:
                # Nested table
                if self._layout_table:
                    nested_box = self._layout_table(block, content_w, px_per_pt)
                    nested_box.y = y
                    nested.append(nested_box)
                    y += nested_box.height

        box.lines = lines
        box.nested_blocks = nested
        box.content_height = y + box.padding.get("top", 0) + box.padding.get("bottom", 0)

    def _calc_row_heights(
        self,
        grid: List[List[Optional[CellBox]]],
        rows: List[Row],
        px_per_pt: float,
    ) -> List[float]:
        n_rows = len(rows)
        heights = [0.0] * n_rows

        # First pass: single-row cells set minimum
        for r in range(n_rows):
            row = rows[r]
            min_h = 0.0
            for c, box in enumerate(grid[r]):
                if box and box.is_origin and not box.v_merged and box.row_span == 1:
                    min_h = max(min_h, box.content_height)
            if row.height_rule == "exact" and row.height > 0:
                heights[r] = row.height * px_per_pt
            elif row.height_rule == "atLeast" and row.height > 0:
                heights[r] = max(min_h, row.height * px_per_pt)
            else:
                heights[r] = max(min_h, 12.0 * px_per_pt)  # min line

        # Distribute multi-row merge content height
        for r in range(n_rows):
            for box in grid[r]:
                if not box or not box.is_origin or box.v_merged or box.row_span <= 1:
                    continue
                span_rows = range(box.row_start, box.row_start + box.row_span)
                current = sum(heights[i] for i in span_rows)
                if box.content_height > current:
                    extra = box.content_height - current
                    # Add extra to last row of span
                    last = box.row_start + box.row_span - 1
                    heights[last] += extra

        return heights

    def _apply_vertical_align(self, box: CellBox) -> None:
        """Offset content lines for vertical alignment within cell."""
        pad_top = box.padding.get("top", 0)
        pad_bottom = box.padding.get("bottom", 0)
        pad_left = box.padding.get("left", 0)
        inner_h = box.height - pad_top - pad_bottom
        content_h = box.content_height - pad_top - pad_bottom
        if box.vertical_align == "center":
            offset = pad_top + max(0.0, (inner_h - content_h) / 2.0)
        elif box.vertical_align == "bottom":
            offset = pad_top + max(0.0, inner_h - content_h)
        else:
            offset = pad_top

        for line in box.lines:
            line.x = box.x + pad_left + line.x
            line.y = box.y + offset + line.y
            for glyph in line.glyphs:
                # glyphs still have relative x within line
                pass

        for nested in box.nested_blocks:
            nested.x = box.x + pad_left
            nested.y = box.y + offset + nested.y


# Module-level default margins (pt)
DEFAULT_MARGINS = {"top": 0.0, "left": 5.4, "bottom": 0.0, "right": 5.4}
