"""Main document parser - Parses document.xml to IR"""

import xml.etree.ElementTree as ET
from typing import Optional, Dict, List
from pathlib import Path

from ..config import Config
from ..unpack.unpacker import DocxPackage
from ..model.document import DocumentModel
from ..model.paragraph import (
    Paragraph, Run, TextRun, BreakRun, TabRun,
    ParaProps, RunProps, TabStop
)
from ..model.table import Table, Row, Cell, TableProps, CellProps
from ..model.section import Section
from ..model.enums import Alignment, SectionType, TabStopType
from .namespaces import NS
from .units import Units


class DocumentParser:
    """Parse document.xml and related files to DocumentModel"""
    
    def __init__(self, package: DocxPackage, config: Config):
        self.package = package
        self.config = config
        self.ns = NS.MAP
    
    def parse(self) -> DocumentModel:
        """Parse DOCX package to DocumentModel"""
        model = DocumentModel()
        
        # Parse main document
        root = ET.fromstring(self.package.document_xml)
        
        # Parse body elements
        body = root.find(f"{{{NS.W}}}body")
        if body is not None:
            for child in body:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                if tag == 'p':
                    para = self._parse_paragraph(child)
                    if para:
                        model.body.append(para)
                elif tag == 'tbl':
                    table = self._parse_table(child)
                    if table:
                        model.body.append(table)
                elif tag == 'sectPr':
                    section = self._parse_section(child)
                    if section:
                        model.sections.append(section)
        
        # If no section defined, add default
        if not model.sections:
            model.sections.append(Section())
        
        # Store media
        model.media = self.package.media
        
        return model
    
    def _parse_paragraph(self, elem) -> Optional[Paragraph]:
        """Parse w:p element to Paragraph"""
        para = Paragraph()
        props_elem = elem.find(f"{{{NS.W}}}pPr")
        
        if props_elem is not None:
            para.props = self._parse_para_props(props_elem)
        
        # Parse runs
        for child in elem:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            
            if tag == 'r':
                run = self._parse_run(child)
                if run:
                    para.runs.append(run)
        
        return para
    
    def _parse_para_props(self, elem) -> ParaProps:
        """Parse w:pPr to ParaProps"""
        props = ParaProps()
        
        # Alignment (w:jc)
        jc = elem.find(f"{{{NS.W}}}jc")
        if jc is not None:
            val = jc.get(f"{{{NS.W}}}val", "left")
            try:
                props.alignment = Alignment(val)
            except ValueError:
                props.alignment = Alignment.LEFT
        
        # Spacing (w:spacing)
        spacing = elem.find(f"{{{NS.W}}}spacing")
        if spacing is not None:
            before = spacing.get(f"{{{NS.W}}}before")
            after = spacing.get(f"{{{NS.W}}}after")
            line = spacing.get(f"{{{NS.W}}}line")
            line_rule = spacing.get(f"{{{NS.W}}}lineRule", "auto")
            
            if before:
                props.space_before = Units.parse_twips(before)
            if after:
                props.space_after = Units.parse_twips(after)
            if line:
                line_val = int(line)
                if line_rule == "exact":
                    props.line_spacing_exact = Units.twips_to_pt(line_val)
                    props.line_spacing_rule = "exact"
                elif line_rule == "atLeast":
                    props.line_spacing_exact = Units.twips_to_pt(line_val)
                    props.line_spacing_rule = "atLeast"
                else:
                    # auto: line is in twentieths of a point, but represents multiplier * 240
                    props.line_spacing = line_val / 240.0 if line_val > 0 else 1.0
        
        # Indentation (w:ind)
        ind = elem.find(f"{{{NS.W}}}ind")
        if ind is not None:
            left = ind.get(f"{{{NS.W}}}left")
            right = ind.get(f"{{{NS.W}}}right")
            first = ind.get(f"{{{NS.W}}}firstLine")
            hanging = ind.get(f"{{{NS.W}}}hanging")
            
            if left:
                props.indent_left = Units.parse_twips(left)
            if right:
                props.indent_right = Units.parse_twips(right)
            if first:
                props.first_line_indent = Units.parse_twips(first)
            if hanging:
                props.hanging_indent = Units.parse_twips(hanging)
        
        # Tab stops (w:tabs)
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
                        leader=leader
                    ))
        
        # Keep next (w:keepNext)
        if elem.find(f"{{{NS.W}}}keepNext") is not None:
            props.keep_next = True
        
        # Keep lines (w:keepLines)
        if elem.find(f"{{{NS.W}}}keepLines") is not None:
            props.keep_lines = True
        
        # Page break before (w:pageBreakBefore)
        if elem.find(f"{{{NS.W}}}pageBreakBefore") is not None:
            props.page_break_before = True
        
        # Style reference (w:pStyle)
        p_style = elem.find(f"{{{NS.W}}}pStyle")
        if p_style is not None:
            props.style_id = p_style.get(f"{{{NS.W}}}val", "")
        
        # Numbering (w:numPr)
        num_pr = elem.find(f"{{{NS.W}}}numPr")
        if num_pr is not None:
            num_id_elem = num_pr.find(f"{{{NS.W}}}numId")
            ilvl_elem = num_pr.find(f"{{{NS.W}}}ilvl")
            
            if num_id_elem is not None:
                num_id_val = num_id_elem.get(f"{{{NS.W}}}val")
                if num_id_val:
                    props.num_id = int(num_id_val)
            
            if ilvl_elem is not None:
                ilvl_val = ilvl_elem.get(f"{{{NS.W}}}val")
                if ilvl_val:
                    props.num_level = int(ilvl_val)
        
        return props
    
    def _parse_run(self, elem) -> Optional[Run]:
        """Parse w:r to Run"""
        run = Run()
        
        # Check for special runs first
        tab_elem = elem.find(f"{{{NS.W}}}tab")
        if tab_elem is not None:
            run.tab = TabRun()
            return run
        
        br_elem = elem.find(f"{{{NS.W}}}br")
        if br_elem is not None:
            br_type = br_elem.get(f"{{{NS.W}}}type", "line")
            run.brk = BreakRun(break_type=br_type)
            return run
        
        # Parse text runs
        r_pr_elem = elem.find(f"{{{NS.W}}}rPr")
        run_props = self._parse_run_props(r_pr_elem) if r_pr_elem is not None else RunProps()
        
        # Get text content
        texts = []
        for t_elem in elem.findall(f"{{{NS.W}}}t"):
            text = t_elem.text or ""
            # Handle xml:space="preserve"
            space = t_elem.get(f"{{{NS.W}}}space")
            if space == "preserve" and text and not text.startswith(' '):
                # Previous run ended without space, this might need leading space
                pass
            texts.append(text)
        
        if texts:
            full_text = ''.join(texts)
            text_run = TextRun(text=full_text, props=run_props)
            run.text = text_run
        
        return run if (run.text or run.tab or run.brk) else None
    
    def _parse_run_props(self, elem) -> RunProps:
        """Parse w:rPr to RunProps"""
        props = RunProps()
        
        if elem is None:
            return props
        
        # Fonts (w:rFonts)
        r_fonts = elem.find(f"{{{NS.W}}}rFonts")
        if r_fonts is not None:
            ascii_font = r_fonts.get(f"{{{NS.W}}}ascii")
            east_asia = r_fonts.get(f"{{{NS.W}}}eastAsia")
            h_ansi = r_fonts.get(f"{{{NS.W}}}hAnsi")
            
            if ascii_font:
                props.font_ascii = ascii_font
            if east_asia:
                props.font_east_asia = east_asia
            if h_ansi:
                props.font_h_ansi = h_ansi
        
        # Bold (w:b)
        b_elem = elem.find(f"{{{NS.W}}}b")
        if b_elem is not None:
            val = b_elem.get(f"{{{NS.W}}}val", "true")
            props.bold = val != "false"
        
        # Italic (w:i)
        i_elem = elem.find(f"{{{NS.W}}}i")
        if i_elem is not None:
            val = i_elem.get(f"{{{NS.W}}}val", "true")
            props.italic = val != "false"
        
        # Underline (w:u)
        u_elem = elem.find(f"{{{NS.W}}}u")
        if u_elem is not None:
            val = u_elem.get(f"{{{NS.W}}}val", "single")
            props.underline = val != "none"
            props.underline_style = val
        
        # Strikethrough (w:strike)
        strike_elem = elem.find(f"{{{NS.W}}}strike")
        if strike_elem is not None:
            val = strike_elem.get(f"{{{NS.W}}}val", "true")
            props.strike = val != "false"
        
        # Color (w:color)
        color_elem = elem.find(f"{{{NS.W}}}color")
        if color_elem is not None:
            val = color_elem.get(f"{{{NS.W}}}val", "000000")
            props.color = self._parse_color(val)
        
        # Highlight (w:highlight)
        highlight_elem = elem.find(f"{{{NS.W}}}highlight")
        if highlight_elem is not None:
            val = highlight_elem.get(f"{{{NS.W}}}val")
            if val and val != "none":
                props.highlight = val
        
        # Font size (w:sz)
        sz_elem = elem.find(f"{{{NS.W}}}sz")
        if sz_elem is not None:
            val = sz_elem.get(f"{{{NS.W}}}val")
            if val:
                # Size is in half-points
                props.font_size = int(val) / 2.0
        
        # Vertical align (w:vertAlign)
        vert_align = elem.find(f"{{{NS.W}}}vertAlign")
        if vert_align is not None:
            val = vert_align.get(f"{{{NS.W}}}val", "baseline")
            props.vertical_align = val
        
        # Position offset (w:position)
        position = elem.find(f"{{{NS.W}}}position")
        if position is not None:
            val = position.get(f"{{{NS.W}}}val")
            if val:
                # Position is in half-points
                props.position_offset = int(val) / 2.0
        
        # Character spacing (w:spacing)
        spacing = elem.find(f"{{{NS.W}}}spacing")
        if spacing is not None:
            val = spacing.get(f"{{{NS.W}}}val")
            if val:
                # Spacing is in twentieths of a point
                props.spacing = Units.parse_twips(int(val))
        
        # Small caps (w:smallCaps)
        small_caps = elem.find(f"{{{NS.W}}}smallCaps")
        if small_caps is not None:
            val = small_caps.get(f"{{{NS.W}}}val", "true")
            props.small_caps = val != "false"
        
        # All caps (w:caps)
        caps = elem.find(f"{{{NS.W}}}caps")
        if caps is not None:
            val = caps.get(f"{{{NS.W}}}val", "true")
            props.all_caps = val != "false"
        
        return props
    
    def _parse_table(self, elem) -> Optional[Table]:
        """Parse w:tbl to Table"""
        table = Table()
        
        # Table properties
        tbl_pr = elem.find(f"{{{NS.W}}}tblPr")
        if tbl_pr is not None:
            table.props = self._parse_table_props(tbl_pr)
        
        # Parse rows
        for row_elem in elem.findall(f"{{{NS.W}}}tr"):
            row = self._parse_table_row(row_elem)
            if row:
                table.rows.append(row)
        
        return table
    
    def _parse_table_props(self, elem) -> TableProps:
        """Parse w:tblPr to TableProps"""
        props = TableProps()
        
        # Width (w:tblW)
        tbl_w = elem.find(f"{{{NS.W}}}tblW")
        if tbl_w is not None:
            w = tbl_w.get(f"{{{NS.W}}}w")
            w_type = tbl_w.get(f"{{{NS.W}}}type", "dxa")
            if w:
                props.width = Units.parse_twips(w)
                props.width_type = w_type
        
        # Alignment (w:jc)
        jc = elem.find(f"{{{NS.W}}}jc")
        if jc is not None:
            val = jc.get(f"{{{NS.W}}}val", "left")
            props.alignment = val
        
        return props
    
    def _parse_table_row(self, elem) -> Optional[Row]:
        """Parse w:tr to Row"""
        row = Row()
        
        # Row height
        tr_height = elem.find(f"{{{NS.W}}}trHeight")
        if tr_height is not None:
            val = tr_height.get(f"{{{NS.W}}}val")
            rule = tr_height.get(f"{{{NS.W}}}hRule", "atLeast")
            if val:
                row.height = Units.parse_twips(val)
                row.height_rule = rule
        
        # Parse cells
        for cell_elem in elem.findall(f"{{{NS.W}}}tc"):
            cell = self._parse_table_cell(cell_elem)
            if cell:
                row.cells.append(cell)
        
        return row
    
    def _parse_table_cell(self, elem) -> Optional[Cell]:
        """Parse w:tc to Cell"""
        cell = Cell()
        
        # Cell properties
        tc_pr = elem.find(f"{{{NS.W}}}tcPr")
        if tc_pr is not None:
            cell.props = self._parse_cell_props(tc_pr)
        
        # Parse paragraphs in cell
        for child in elem:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'p':
                para = self._parse_paragraph(child)
                if para:
                    cell.paragraphs.append(para)
        
        return cell
    
    def _parse_cell_props(self, elem) -> CellProps:
        """Parse w:tcPr to CellProps"""
        props = CellProps()
        
        # Width (w:tcW)
        tc_w = elem.find(f"{{{NS.W}}}tcW")
        if tc_w is not None:
            w = tc_w.get(f"{{{NS.W}}}w")
            w_type = tc_w.get(f"{{{NS.W}}}type", "dxa")
            if w:
                props.width = Units.parse_twips(w)
                props.width_type = w_type
        
        # Grid span (w:gridSpan)
        grid_span = elem.find(f"{{{NS.W}}}gridSpan")
        if grid_span is not None:
            val = grid_span.get(f"{{{NS.W}}}val")
            if val:
                props.grid_span = int(val)
        
        # Vertical merge (w:vMerge)
        v_merge = elem.find(f"{{{NS.W}}}vMerge")
        if v_merge is not None:
            val = v_merge.get(f"{{{NS.W}}}val", "continue")
            if val == "restart":
                props.v_merge = VerticalMerge.RESTART
            else:
                props.v_merge = VerticalMerge.CONTINUE
        
        return props
    
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
