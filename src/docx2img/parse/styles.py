"""Parse word/styles.xml into StyleTable + document defaults."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional, Set, Tuple

from ..model.style import Style, StyleTable
from ..model.paragraph import RunProps, ParaProps
from ..model.enums import Alignment, TabStopType
from .namespaces import NS
from .units import Units
from .table import parse_border_elem


def ooxml_on_off(node, default: bool = True) -> bool:
    """Interpret OOXML on/off elements (presence = on; val=0/false/off = off)."""
    if node is None:
        return False
    val = node.get(f"{{{NS.W}}}val")
    if val is None:
        return default
    return str(val).lower() not in ("0", "false", "off")


class StylesParser:
    """Parse styles.xml."""

    def __init__(self):
        self.ns = NS.MAP

    def parse(self, styles_xml: bytes) -> Tuple[StyleTable, RunProps, ParaProps]:
        """Return (style_table, default_rpr, default_ppr)."""
        table = StyleTable()
        default_rpr = RunProps()
        default_ppr = ParaProps()

        if not styles_xml:
            return table, default_rpr, default_ppr

        root = ET.fromstring(styles_xml)

        # docDefaults
        doc_defaults = root.find(f"{{{NS.W}}}docDefaults")
        if doc_defaults is not None:
            rpr_default = doc_defaults.find(f"{{{NS.W}}}rPrDefault/{{{NS.W}}}rPr")
            if rpr_default is not None:
                default_rpr, _ = self.parse_run_props(rpr_default)

            ppr_default = doc_defaults.find(f"{{{NS.W}}}pPrDefault/{{{NS.W}}}pPr")
            if ppr_default is not None:
                default_ppr, _ = self.parse_para_props(ppr_default)

        for style_elem in root.findall(f"{{{NS.W}}}style"):
            style = self._parse_style(style_elem)
            if not style.style_id:
                continue
            table.add(style)
            if style_elem.get(f"{{{NS.W}}}default") in ("1", "true"):
                if style.type == "paragraph":
                    table.default_paragraph = style
                elif style.type == "character":
                    table.default_character = style

        return table, default_rpr, default_ppr

    def _parse_style(self, elem) -> Style:
        style = Style()
        style.style_id = elem.get(f"{{{NS.W}}}styleId", "") or ""
        style.type = elem.get(f"{{{NS.W}}}type", "paragraph") or "paragraph"

        name_elem = elem.find(f"{{{NS.W}}}name")
        if name_elem is not None:
            style.name = name_elem.get(f"{{{NS.W}}}val", "") or ""

        based = elem.find(f"{{{NS.W}}}basedOn")
        if based is not None:
            style.based_on = based.get(f"{{{NS.W}}}val")

        next_elem = elem.find(f"{{{NS.W}}}next")
        if next_elem is not None:
            style.next = next_elem.get(f"{{{NS.W}}}val")

        ppr = elem.find(f"{{{NS.W}}}pPr")
        if ppr is not None:
            props, fields = self.parse_para_props(ppr)
            style.para_props = props
            style.para_set = fields

        rpr = elem.find(f"{{{NS.W}}}rPr")
        if rpr is not None:
            props, fields = self.parse_run_props(rpr)
            style.run_props = props
            style.run_set = fields

        return style

    def parse_para_props(self, elem) -> Tuple[ParaProps, Set[str]]:
        """Parse w:pPr; return props + set of explicitly assigned field names."""
        props = ParaProps()
        fields: Set[str] = set()

        jc = elem.find(f"{{{NS.W}}}jc")
        if jc is not None:
            val = jc.get(f"{{{NS.W}}}val", "left")
            props.alignment = Alignment.from_ooxml(val)
            fields.add("alignment")

        spacing = elem.find(f"{{{NS.W}}}spacing")
        if spacing is not None:
            before = spacing.get(f"{{{NS.W}}}before")
            after = spacing.get(f"{{{NS.W}}}after")
            before_lines = spacing.get(f"{{{NS.W}}}beforeLines")
            after_lines = spacing.get(f"{{{NS.W}}}afterLines")
            line = spacing.get(f"{{{NS.W}}}line")
            line_rule = spacing.get(f"{{{NS.W}}}lineRule", "auto")
            if before is not None:
                props.space_before = Units.parse_twips(before)
                fields.add("space_before")
            if after is not None:
                props.space_after = Units.parse_twips(after)
                fields.add("space_after")
            # beforeLines/afterLines override the twip values (hundredths of
            # a line); resolved against grid pitch at layout time.
            if before_lines is not None:
                try:
                    props.space_before_lines = int(before_lines)
                    fields.add("space_before_lines")
                except ValueError:
                    pass
            if after_lines is not None:
                try:
                    props.space_after_lines = int(after_lines)
                    fields.add("space_after_lines")
                except ValueError:
                    pass
            if line is not None:
                line_val = int(line)
                fields.add("line_spacing_rule")
                if line_rule == "exact":
                    props.line_spacing_exact = Units.twips_to_pt(line_val)
                    props.line_spacing_rule = "exact"
                    fields.add("line_spacing_exact")
                elif line_rule == "atLeast":
                    props.line_spacing_exact = Units.twips_to_pt(line_val)
                    props.line_spacing_rule = "atLeast"
                    fields.add("line_spacing_exact")
                else:
                    props.line_spacing = line_val / 240.0 if line_val > 0 else 1.0
                    props.line_spacing_rule = "auto"
                    fields.add("line_spacing")

        ind = elem.find(f"{{{NS.W}}}ind")
        if ind is not None:
            mapping = [
                ("left", "indent_left"),
                ("right", "indent_right"),
                ("firstLine", "first_line_indent"),
                ("hanging", "hanging_indent"),
            ]
            for xml_attr, field in mapping:
                val = ind.get(f"{{{NS.W}}}{xml_attr}")
                if val is not None:
                    setattr(props, field, Units.parse_twips(val))
                    fields.add(field)
            # Character-unit indents (hundredths of a character); when present
            # they take precedence over the twip values at layout time.
            char_mapping = [
                ("leftChars", "indent_left_chars"),
                ("firstLineChars", "first_line_chars"),
                ("hangingChars", "hanging_chars"),
            ]
            for xml_attr, field in char_mapping:
                val = ind.get(f"{{{NS.W}}}{xml_attr}")
                if val is not None:
                    try:
                        setattr(props, field, int(val))
                        fields.add(field)
                    except ValueError:
                        pass

        keep_next = elem.find(f"{{{NS.W}}}keepNext")
        if keep_next is not None:
            props.keep_next = ooxml_on_off(keep_next)
            fields.add("keep_next")
        keep_lines = elem.find(f"{{{NS.W}}}keepLines")
        if keep_lines is not None:
            props.keep_lines = ooxml_on_off(keep_lines)
            fields.add("keep_lines")
        page_break = elem.find(f"{{{NS.W}}}pageBreakBefore")
        if page_break is not None:
            props.page_break_before = ooxml_on_off(page_break)
            fields.add("page_break_before")
        widow = elem.find(f"{{{NS.W}}}widowControl")
        if widow is not None:
            props.widow_control = ooxml_on_off(widow)
            fields.add("widow_control")

        # CJK auto-spacing at script boundaries.  Word enables both by default;
        # an explicit val="0"/"false" disables the gap insertion.
        auto_de = elem.find(f"{{{NS.W}}}autoSpaceDE")
        if auto_de is not None:
            props.auto_space_de = ooxml_on_off(auto_de)
            fields.add("auto_space_de")
        auto_dn = elem.find(f"{{{NS.W}}}autoSpaceDN")
        if auto_dn is not None:
            props.auto_space_dn = ooxml_on_off(auto_dn)
            fields.add("auto_space_dn")

        # Paragraph borders (w:pBdr) — top/left/bottom/right/between.
        pbdr = elem.find(f"{{{NS.W}}}pBdr")
        if pbdr is not None:
            borders = {}
            for side in ("top", "left", "bottom", "right", "between"):
                node = pbdr.find(f"{{{NS.W}}}{side}")
                if node is not None:
                    spec = parse_border_elem(node)
                    # For paragraph borders w:space is in points (CT_Border),
                    # not twips — re-parse it directly.
                    space_raw = node.get(f"{{{NS.W}}}space")
                    if space_raw is not None:
                        try:
                            spec.space = float(space_raw)
                        except ValueError:
                            pass
                    borders[side] = spec
            if borders:
                props.borders = borders
                fields.add("borders")

        outline = elem.find(f"{{{NS.W}}}outlineLvl")
        if outline is not None:
            val = outline.get(f"{{{NS.W}}}val")
            if val is not None:
                props.outline_level = int(val)
                fields.add("outline_level")

        # Paragraph mark formatting (w:pPr/w:rPr) — only font size is used,
        # it drives empty-paragraph height and character-unit indents.
        mark_rpr = elem.find(f"{{{NS.W}}}rPr")
        if mark_rpr is not None:
            sz = mark_rpr.find(f"{{{NS.W}}}sz")
            if sz is not None:
                val = sz.get(f"{{{NS.W}}}val")
                if val:
                    try:
                        props.mark_font_size = int(val) / 2.0
                        fields.add("mark_font_size")
                    except ValueError:
                        pass

        return props, fields

    def parse_run_props(self, elem) -> Tuple[RunProps, Set[str]]:
        """Parse w:rPr; return props + set of explicitly assigned field names."""
        props = RunProps()
        fields: Set[str] = set()

        r_fonts = elem.find(f"{{{NS.W}}}rFonts")
        if r_fonts is not None:
            for xml_attr, field in (
                ("ascii", "font_ascii"),
                ("eastAsia", "font_east_asia"),
                ("hAnsi", "font_h_ansi"),
                ("cs", "font_cs"),
                ("asciiTheme", "font_ascii"),
                ("eastAsiaTheme", "font_east_asia"),
                ("hAnsiTheme", "font_h_ansi"),
            ):
                val = r_fonts.get(f"{{{NS.W}}}{xml_attr}")
                if val:
                    # Theme font tokens like majorAscii → +mj-lt style markers
                    mapped = _theme_font_token(xml_attr, val)
                    setattr(props, field, mapped)
                    fields.add(field)

        def _on_off(tag: str, field: str) -> None:
            node = elem.find(f"{{{NS.W}}}{tag}")
            if node is not None:
                setattr(props, field, ooxml_on_off(node))
                fields.add(field)

        _on_off("b", "bold")
        _on_off("i", "italic")
        _on_off("strike", "strike")
        _on_off("dstrike", "double_strike")
        _on_off("smallCaps", "small_caps")
        _on_off("caps", "all_caps")

        u_elem = elem.find(f"{{{NS.W}}}u")
        if u_elem is not None:
            val = u_elem.get(f"{{{NS.W}}}val", "single")
            props.underline = val != "none"
            props.underline_style = val
            fields.add("underline")
            fields.add("underline_style")

        color_elem = elem.find(f"{{{NS.W}}}color")
        if color_elem is not None:
            # Raw hex; theme resolution happens in StyleResolver
            val = color_elem.get(f"{{{NS.W}}}val")
            theme = color_elem.get(f"{{{NS.W}}}themeColor")
            tint = color_elem.get(f"{{{NS.W}}}themeTint")
            shade = color_elem.get(f"{{{NS.W}}}themeShade")
            props._color_raw = {  # type: ignore[attr-defined]
                "val": val,
                "themeColor": theme,
                "themeTint": tint,
                "themeShade": shade,
            }
            if val and val != "auto":
                props.color = _hex_to_rgb(val)
                fields.add("color")
            elif theme:
                fields.add("color")  # resolved later

        highlight = elem.find(f"{{{NS.W}}}highlight")
        if highlight is not None:
            val = highlight.get(f"{{{NS.W}}}val")
            if val and val != "none":
                props.highlight = val
                fields.add("highlight")

        sz = elem.find(f"{{{NS.W}}}sz")
        if sz is not None:
            val = sz.get(f"{{{NS.W}}}val")
            if val:
                props.font_size = int(val) / 2.0
                fields.add("font_size")

        vert = elem.find(f"{{{NS.W}}}vertAlign")
        if vert is not None:
            props.vertical_align = vert.get(f"{{{NS.W}}}val", "baseline")
            fields.add("vertical_align")

        position = elem.find(f"{{{NS.W}}}position")
        if position is not None:
            val = position.get(f"{{{NS.W}}}val")
            if val:
                props.position_offset = int(val) / 2.0
                fields.add("position_offset")

        spacing = elem.find(f"{{{NS.W}}}spacing")
        if spacing is not None:
            val = spacing.get(f"{{{NS.W}}}val")
            if val:
                props.spacing = Units.parse_twips(int(val))
                fields.add("spacing")

        # w:w — character width scaling (percentage, 100 = normal)
        w_elem = elem.find(f"{{{NS.W}}}w")
        if w_elem is not None:
            val = w_elem.get(f"{{{NS.W}}}val")
            if val:
                try:
                    props.scale = max(1, min(int(val), 600))
                    fields.add("scale")
                except ValueError:
                    pass

        return props, fields


def _theme_font_token(attr: str, val: str) -> str:
    """Normalize theme font references to +mj-lt / +mn-lt / +mj-ea / +mn-ea."""
    theme_vals = {
        "majorAscii": "+mj-lt",
        "majorHAnsi": "+mj-lt",
        "majorEastAsia": "+mj-ea",
        "majorBidi": "+mj-cs",
        "minorAscii": "+mn-lt",
        "minorHAnsi": "+mn-lt",
        "minorEastAsia": "+mn-ea",
        "minorBidi": "+mn-cs",
    }
    if attr.endswith("Theme") or val in theme_vals:
        return theme_vals.get(val, val)
    return val


def _hex_to_rgb(val: str) -> tuple:
    val = val.lstrip("#")
    if len(val) == 6:
        try:
            return (int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))
        except ValueError:
            pass
    return (0, 0, 0)
