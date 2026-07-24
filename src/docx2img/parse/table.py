"""Parse w:tbl / borders / shading helpers."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..model.table import BorderDef, TableProps, CellProps, Table, Row, Cell
from ..model.enums import BorderStyle, VerticalMerge
from ..utils.color import parse_color
from .namespaces import NS
from .units import Units


# Default Word cell margins (twips → pt): left/right 108 twips = 5.4pt
DEFAULT_CELL_MARGINS = {"top": 0.0, "left": 5.4, "bottom": 0.0, "right": 5.4}


def parse_border_elem(elem) -> BorderDef:
    """Parse a single border element (w:top / w:left / ...)."""
    if elem is None:
        return BorderDef(style=BorderStyle.NONE, width=0.0)

    val = elem.get(f"{{{NS.W}}}val", "nil")
    style = BorderStyle.from_ooxml(val or "nil")

    # sz is in eighths of a point
    sz = elem.get(f"{{{NS.W}}}sz")
    width = (int(sz) / 8.0) if sz else 0.5

    color_val = elem.get(f"{{{NS.W}}}color", "000000")
    if color_val and color_val != "auto":
        color = parse_color(color_val)
    else:
        color = (0, 0, 0)

    space = Units.parse_twips(elem.get(f"{{{NS.W}}}space"), 0.0)
    return BorderDef(style=style, width=width, color=color, space=space)


def parse_borders(parent) -> Dict[str, BorderDef]:
    """Parse w:tblBorders or w:tcBorders."""
    if parent is None:
        return {}
    result = {}
    for side in ("top", "left", "bottom", "right", "insideH", "insideV", "tl2br", "tr2bl"):
        node = parent.find(f"{{{NS.W}}}{side}")
        if node is not None:
            result[side] = parse_border_elem(node)
    return result


def parse_shading(elem) -> Optional[Tuple[int, int, int]]:
    """Parse w:shd → fill RGB."""
    if elem is None:
        return None
    fill = elem.get(f"{{{NS.W}}}fill")
    if fill and fill not in ("auto", "null"):
        return parse_color(fill)
    return None


def parse_margins(elem) -> Dict[str, float]:
    """Parse w:tcMar / w:tblCellMar."""
    if elem is None:
        return {}
    result = {}
    for side in ("top", "left", "bottom", "right"):
        node = elem.find(f"{{{NS.W}}}{side}")
        if node is not None:
            w = node.get(f"{{{NS.W}}}w")
            w_type = node.get(f"{{{NS.W}}}type", "dxa")
            if w is not None:
                if w_type == "dxa":
                    result[side] = Units.parse_twips(w)
                else:
                    result[side] = Units.parse_twips(w)
    return result


class TableParser:
    """Parse w:tbl elements. Needs a DocumentParser-like host for paragraphs."""

    def __init__(self, para_parser, nested_table_parser=None):
        """
        Args:
            para_parser: callable(elem) -> Paragraph
            nested_table_parser: callable(elem) -> Table (usually self.parse)
        """
        self._parse_para = para_parser
        self._parse_nested = nested_table_parser or self.parse

    def parse(self, elem) -> Optional[Table]:
        table = Table()

        tbl_pr = elem.find(f"{{{NS.W}}}tblPr")
        if tbl_pr is not None:
            table.props = self._parse_table_props(tbl_pr)

        # tblGrid
        tbl_grid = elem.find(f"{{{NS.W}}}tblGrid")
        if tbl_grid is not None:
            for col in tbl_grid.findall(f"{{{NS.W}}}gridCol"):
                w = col.get(f"{{{NS.W}}}w")
                if w:
                    table.col_widths.append(Units.parse_twips(w))

        for row_elem in elem.findall(f"{{{NS.W}}}tr"):
            row = self._parse_row(row_elem)
            if row:
                table.rows.append(row)

        return table

    def _parse_table_props(self, elem) -> TableProps:
        props = TableProps()

        tbl_w = elem.find(f"{{{NS.W}}}tblW")
        if tbl_w is not None:
            w = tbl_w.get(f"{{{NS.W}}}w")
            w_type = tbl_w.get(f"{{{NS.W}}}type", "auto")
            props.width_type = w_type or "auto"
            if w and w_type == "dxa":
                props.width = Units.parse_twips(w)
            elif w and w_type == "pct":
                # pct is in fiftieths of a percent
                props.width = float(w) / 50.0  # store as percent 0-100
                props.width_type = "pct"

        jc = elem.find(f"{{{NS.W}}}jc")
        if jc is not None:
            props.alignment = jc.get(f"{{{NS.W}}}val", "left")

        ind = elem.find(f"{{{NS.W}}}tblInd")
        if ind is not None:
            w = ind.get(f"{{{NS.W}}}w")
            if w:
                props.indent = Units.parse_twips(w)

        borders = elem.find(f"{{{NS.W}}}tblBorders")
        if borders is not None:
            props.borders = parse_borders(borders)

        spacing = elem.find(f"{{{NS.W}}}tblCellSpacing")
        if spacing is not None:
            w = spacing.get(f"{{{NS.W}}}w")
            if w:
                props.cell_spacing = Units.parse_twips(w)

        layout = elem.find(f"{{{NS.W}}}tblLayout")
        if layout is not None:
            props.layout = layout.get(f"{{{NS.W}}}type", "autofit")

        style = elem.find(f"{{{NS.W}}}tblStyle")
        if style is not None:
            props.style_id = style.get(f"{{{NS.W}}}val", "") or ""

        cell_mar = elem.find(f"{{{NS.W}}}tblCellMar")
        if cell_mar is not None:
            props.cell_margins = parse_margins(cell_mar)
        else:
            props.cell_margins = dict(DEFAULT_CELL_MARGINS)

        return props

    def _parse_row(self, elem) -> Optional[Row]:
        row = Row()

        tr_pr = elem.find(f"{{{NS.W}}}trPr")
        if tr_pr is not None:
            tr_height = tr_pr.find(f"{{{NS.W}}}trHeight")
            if tr_height is not None:
                val = tr_height.get(f"{{{NS.W}}}val")
                rule = tr_height.get(f"{{{NS.W}}}hRule", "atLeast")
                if val:
                    row.height = Units.parse_twips(val)
                    row.height_rule = rule
            if tr_pr.find(f"{{{NS.W}}}tblHeader") is not None:
                row.is_header = True
            if tr_pr.find(f"{{{NS.W}}}cantSplit") is not None:
                row.cant_split = True
        else:
            # Some docs put trHeight directly under tr
            tr_height = elem.find(f"{{{NS.W}}}trHeight")
            if tr_height is not None:
                val = tr_height.get(f"{{{NS.W}}}val")
                rule = tr_height.get(f"{{{NS.W}}}hRule", "atLeast")
                if val:
                    row.height = Units.parse_twips(val)
                    row.height_rule = rule

        for cell_elem in elem.findall(f"{{{NS.W}}}tc"):
            cell = self._parse_cell(cell_elem)
            if cell:
                row.cells.append(cell)
        return row

    def _parse_cell(self, elem) -> Optional[Cell]:
        cell = Cell()
        tc_pr = elem.find(f"{{{NS.W}}}tcPr")
        if tc_pr is not None:
            cell.props = self._parse_cell_props(tc_pr)

        for child in elem:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                para = self._parse_para(child)
                if para:
                    cell.blocks.append(para)
            elif tag == "tbl":
                nested = self._parse_nested(child)
                if nested:
                    cell.blocks.append(nested)
        return cell

    def _parse_cell_props(self, elem) -> CellProps:
        props = CellProps()

        tc_w = elem.find(f"{{{NS.W}}}tcW")
        if tc_w is not None:
            w = tc_w.get(f"{{{NS.W}}}w")
            w_type = tc_w.get(f"{{{NS.W}}}type", "dxa")
            props.width_type = w_type or "dxa"
            if w and w_type == "dxa":
                props.width = Units.parse_twips(w)
            elif w and w_type == "pct":
                props.width = float(w) / 50.0
                props.width_type = "pct"

        grid_span = elem.find(f"{{{NS.W}}}gridSpan")
        if grid_span is not None:
            val = grid_span.get(f"{{{NS.W}}}val")
            if val:
                props.grid_span = max(1, int(val))

        v_merge = elem.find(f"{{{NS.W}}}vMerge")
        if v_merge is not None:
            val = v_merge.get(f"{{{NS.W}}}val", "continue")
            props.v_merge = (
                VerticalMerge.RESTART if val == "restart" else VerticalMerge.CONTINUE
            )

        borders = elem.find(f"{{{NS.W}}}tcBorders")
        if borders is not None:
            props.borders = parse_borders(borders)

        shd = elem.find(f"{{{NS.W}}}shd")
        props.shading = parse_shading(shd)

        v_align = elem.find(f"{{{NS.W}}}vAlign")
        if v_align is not None:
            props.vertical_align = v_align.get(f"{{{NS.W}}}val", "top") or "top"

        tc_mar = elem.find(f"{{{NS.W}}}tcMar")
        if tc_mar is not None:
            props.margins = parse_margins(tc_mar)

        if elem.find(f"{{{NS.W}}}noWrap") is not None:
            props.no_wrap = True

        return props
