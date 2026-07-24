"""Main document parser - Parses document.xml to IR"""

import xml.etree.ElementTree as ET
from typing import Optional, Dict, List
from pathlib import Path

from ..config import Config
from ..unpack.unpacker import DocxPackage
from ..model.document import DocumentModel
from ..model.paragraph import (
    Paragraph, Run, TextRun, BreakRun, TabRun,
    ParaProps, RunProps, TabStop, MathRun, TextBoxRun
)
from ..model.table import Table
from ..model.section import Section
from ..model.enums import Alignment, SectionType, TabStopType
from ..style.resolver import StyleResolver
from .namespaces import NS
from .units import Units
from .styles import StylesParser
from .theme import ThemeParser
from .table import TableParser
from .drawing import DrawingParser
from .header_footer import HeaderFooterParser
from .numbering import NumberingParser
from .math_omml import OmmlParser
from .namespaces import NS, M


class DocumentParser:
    """Parse document.xml and related files to DocumentModel"""

    def __init__(self, package: DocxPackage, config: Config):
        self.package = package
        self.config = config
        self.ns = NS.MAP
        self._styles_parser = StylesParser()
        self._style_resolver: Optional[StyleResolver] = None
        self._table_parser: Optional[TableParser] = None
        self._drawing_parser: Optional[DrawingParser] = None
        self._math_parser = OmmlParser()

    def parse(self) -> DocumentModel:
        """Parse DOCX package to DocumentModel"""
        model = DocumentModel()

        # Styles + theme (P1)
        style_table, default_rpr, default_ppr = self._styles_parser.parse(
            self.package.styles_xml or b""
        )
        theme_colors, theme_fonts = ThemeParser().parse(self.package.theme_xml or b"")
        model.styles = style_table
        model.default_run_props = default_rpr
        model.default_para_props = default_ppr
        model.theme_colors = theme_colors
        model.theme_fonts = theme_fonts
        self._style_resolver = StyleResolver(
            style_table,
            theme_colors=theme_colors,
            theme_fonts=theme_fonts,
            default_rpr=default_rpr,
            default_ppr=default_ppr,
        )
        self._table_parser = TableParser(
            para_parser=self._parse_paragraph,
            nested_table_parser=None,
        )
        self._table_parser._parse_nested = self._table_parser.parse
        self._drawing_parser = DrawingParser(
            media=self.package.media,
            rels=self.package.document_rels,
            para_parser=self._parse_paragraph,
        )

        root = ET.fromstring(self.package.document_xml)

        body = root.find(f"{{{NS.W}}}body")
        if body is not None:
            for child in body:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag == 'p':
                    para = self._parse_paragraph(child)
                    if para:
                        model.body.append(para)
                        if para.section_break is not None:
                            model.sections.append(para.section_break)
                elif tag == 'tbl':
                    table = self._parse_table(child)
                    if table:
                        model.body.append(table)
                elif tag == 'sectPr':
                    section = self._parse_section(child)
                    if section:
                        model.sections.append(section)

        if not model.sections:
            model.sections.append(Section())

        # Parse header/footer XML for each section
        hf_parser = HeaderFooterParser(self._parse_paragraph)
        for section in model.sections:
            for htype, rid in section.header_refs.items():
                xml = self.package.headers.get(rid)
                if xml:
                    section.header_bodies[htype] = hf_parser.parse(xml)
            for ftype, rid in section.footer_refs.items():
                xml = self.package.footers.get(rid)
                if xml:
                    section.footer_bodies[ftype] = hf_parser.parse(xml)

        # Numbering
        model.numbering = NumberingParser().parse(self.package.numbering_xml or b"")

        model.media = self.package.media
        return model

    def _parse_paragraph(self, elem) -> Optional[Paragraph]:
        """Parse w:p element to Paragraph with style resolution."""
        para = Paragraph()
        props_elem = elem.find(f"{{{NS.W}}}pPr")

        direct = ParaProps()
        direct_set = set()
        style_id = ""

        if props_elem is not None:
            direct, direct_set = self._styles_parser.parse_para_props(props_elem)
            # Tabs / numbering / style id (extra fields not in StylesParser)
            self._parse_para_extras(props_elem, direct, direct_set)
            style_id = direct.style_id or ""

        if self._style_resolver:
            para.props = self._style_resolver.resolve_para(style_id, direct, direct_set)
            para.props.style_id = style_id
        else:
            para.props = direct

        # Section break embedded in paragraph properties
        if props_elem is not None:
            sect = props_elem.find(f"{{{NS.W}}}sectPr")
            if sect is not None:
                para.section_break = self._parse_section(sect)

        for child in elem:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'r':
                run = self._parse_run(child, para_style_id=style_id)
                if run:
                    para.runs.append(run)
            elif tag in ('oMath', 'oMathPara'):
                ast = self._math_parser.parse_element(child)
                if ast is not None:
                    para.runs.append(Run(math=MathRun(ast=ast)))

        return para

    def _parse_para_extras(self, elem, props: ParaProps, fields: set) -> None:
        """Parse tabs / numbering / pStyle into props."""
        tabs_elem = elem.find(f"{{{NS.W}}}tabs")
        if tabs_elem is not None:
            for tab in tabs_elem.findall(f"{{{NS.W}}}tab"):
                pos = tab.get(f"{{{NS.W}}}pos")
                val = tab.get(f"{{{NS.W}}}val", "left")
                leader = tab.get(f"{{{NS.W}}}leader", "none")
                if pos:
                    try:
                        tab_type = TabStopType(val)
                    except ValueError:
                        tab_type = TabStopType.LEFT
                    props.tab_stops.append(TabStop(
                        position=Units.parse_twips(pos),
                        type=tab_type,
                        leader=leader,
                    ))
            fields.add("tab_stops")

        p_style = elem.find(f"{{{NS.W}}}pStyle")
        if p_style is not None:
            props.style_id = p_style.get(f"{{{NS.W}}}val", "") or ""
            fields.add("style_id")

        num_pr = elem.find(f"{{{NS.W}}}numPr")
        if num_pr is not None:
            num_id_elem = num_pr.find(f"{{{NS.W}}}numId")
            ilvl_elem = num_pr.find(f"{{{NS.W}}}ilvl")
            if num_id_elem is not None:
                num_id_val = num_id_elem.get(f"{{{NS.W}}}val")
                if num_id_val:
                    props.num_id = int(num_id_val)
                    fields.add("num_id")
            if ilvl_elem is not None:
                ilvl_val = ilvl_elem.get(f"{{{NS.W}}}val")
                if ilvl_val:
                    props.num_level = int(ilvl_val)
                    fields.add("num_level")

    def _parse_run(self, elem, para_style_id: str = "") -> Optional[Run]:
        """Parse w:r to Run with style resolution."""
        run = Run()

        tab_elem = elem.find(f"{{{NS.W}}}tab")
        if tab_elem is not None:
            run.tab = TabRun()
            return run

        br_elem = elem.find(f"{{{NS.W}}}br")
        if br_elem is not None:
            br_type = br_elem.get(f"{{{NS.W}}}type", "line")
            run.brk = BreakRun(break_type=br_type)
            return run

        # Drawing / image / textbox
        drawing = elem.find(f"{{{NS.W}}}drawing")
        if drawing is not None and self._drawing_parser is not None:
            image_run = self._drawing_parser.parse(drawing)
            if image_run:
                run.image = image_run
                return run
            tbox = self._drawing_parser.parse_textbox(drawing)
            if tbox:
                run.textbox = tbox
                return run

        # Math inside run (rare)
        omml = elem.find(f"{{{M}}}oMath")
        if omml is not None:
            ast = self._math_parser.parse_element(omml)
            if ast is not None:
                run.math = MathRun(ast=ast)
                return run

        r_pr_elem = elem.find(f"{{{NS.W}}}rPr")
        direct = RunProps()
        direct_set = set()
        char_style_id = ""

        if r_pr_elem is not None:
            direct, direct_set = self._styles_parser.parse_run_props(r_pr_elem)
            r_style = r_pr_elem.find(f"{{{NS.W}}}rStyle")
            if r_style is not None:
                char_style_id = r_style.get(f"{{{NS.W}}}val", "") or ""

        if self._style_resolver:
            run_props = self._style_resolver.resolve_run(
                char_style_id, para_style_id, direct, direct_set
            )
        else:
            run_props = direct

        texts = []
        for t_elem in elem.findall(f"{{{NS.W}}}t"):
            texts.append(t_elem.text or "")

        if texts:
            run.text = TextRun(text=''.join(texts), props=run_props)

        return run if (run.text or run.tab or run.brk or run.image or run.math or run.textbox) else None
    
    def _parse_table(self, elem) -> Optional[Table]:
        """Parse w:tbl to Table"""
        if self._table_parser is None:
            self._table_parser = TableParser(self._parse_paragraph)
            self._table_parser._parse_nested = self._table_parser.parse
        return self._table_parser.parse(elem)

    def _parse_section(self, elem) -> Optional[Section]:
        """Parse w:sectPr to Section"""
        section = Section()
        
        # Page size (w:pgSz)
        pg_sz = elem.find(f"{{{NS.W}}}pgSz")
        if pg_sz is not None:
            w = pg_sz.get(f"{{{NS.W}}}w")
            h = pg_sz.get(f"{{{NS.W}}}h")
            orient = pg_sz.get(f"{{{NS.W}}}orient", "portrait")
            
            if w:
                section.page_w = Units.parse_twips(w)
            if h:
                section.page_h = Units.parse_twips(h)
            section.orientation = orient
        
        # Margins (w:pgMar)
        pg_mar = elem.find(f"{{{NS.W}}}pgMar")
        if pg_mar is not None:
            top = pg_mar.get(f"{{{NS.W}}}top")
            bottom = pg_mar.get(f"{{{NS.W}}}bottom")
            left = pg_mar.get(f"{{{NS.W}}}left")
            right = pg_mar.get(f"{{{NS.W}}}right")
            header = pg_mar.get(f"{{{NS.W}}}header")
            footer = pg_mar.get(f"{{{NS.W}}}footer")
            gutter = pg_mar.get(f"{{{NS.W}}}gutter")
            
            if top:
                section.margin_top = Units.parse_twips(top)
            if bottom:
                section.margin_bottom = Units.parse_twips(bottom)
            if left:
                section.margin_left = Units.parse_twips(left)
            if right:
                section.margin_right = Units.parse_twips(right)
            if header:
                section.header_distance = Units.parse_twips(header)
            if footer:
                section.footer_distance = Units.parse_twips(footer)
            if gutter:
                section.gutter = Units.parse_twips(gutter)
        
        # Section type (w:type)
        type_elem = elem.find(f"{{{NS.W}}}type")
        if type_elem is not None:
            val = type_elem.get(f"{{{NS.W}}}val", "nextPage")
            try:
                section.section_type = SectionType(val)
            except ValueError:
                section.section_type = SectionType.NEXT_PAGE

        # Columns (w:cols)
        cols = elem.find(f"{{{NS.W}}}cols")
        if cols is not None:
            num = cols.get(f"{{{NS.W}}}num")
            if num:
                section.col_count = max(1, int(num))
            space = cols.get(f"{{{NS.W}}}space")
            if space:
                section.col_space = Units.parse_twips(space)
            eq = cols.get(f"{{{NS.W}}}equalWidth", "1")
            section.col_equal_width = eq not in ("0", "false")
            section.col_sep = cols.get(f"{{{NS.W}}}sep") in ("1", "true")
            from ..model.section import ColumnDef
            for col in cols.findall(f"{{{NS.W}}}col"):
                cw = col.get(f"{{{NS.W}}}w")
                cs = col.get(f"{{{NS.W}}}space")
                section.columns.append(ColumnDef(
                    width=Units.parse_twips(cw) if cw else 0.0,
                    space=Units.parse_twips(cs) if cs else section.col_space,
                ))
            if section.columns and not num:
                section.col_count = len(section.columns)

        # Header / footer references
        from .namespaces import R_DOC
        for href in elem.findall(f"{{{NS.W}}}headerReference"):
            htype = href.get(f"{{{NS.W}}}type", "default")
            rid = href.get(f"{{{R_DOC}}}id")
            if rid:
                section.header_refs[htype] = rid
        for fref in elem.findall(f"{{{NS.W}}}footerReference"):
            ftype = fref.get(f"{{{NS.W}}}type", "default")
            rid = fref.get(f"{{{R_DOC}}}id")
            if rid:
                section.footer_refs[ftype] = rid

        if elem.find(f"{{{NS.W}}}titlePg") is not None:
            section.title_page = True

        pg_num = elem.find(f"{{{NS.W}}}pgNumType")
        if pg_num is not None:
            start = pg_num.get(f"{{{NS.W}}}start")
            if start:
                section.page_num_start = int(start)

        return section

    def _parse_color(self, val: str) -> tuple:
        """Parse hex color string to RGB tuple"""
        val = val.lstrip('#')
        if len(val) == 6:
            try:
                r = int(val[0:2], 16)
                g = int(val[2:4], 16)
                b = int(val[4:6], 16)
                return (r, g, b)
            except ValueError:
                pass
        return (0, 0, 0)
