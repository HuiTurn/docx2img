"""Main document parser - Parses document.xml to IR"""

import logging
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

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parse document.xml and related files to DocumentModel"""

    def __init__(self, package: DocxPackage, config: Config):
        self.package = package
        self.config = config
        self.ns = NS.MAP
        self._styles_parser = StylesParser()
        self._style_resolver: Optional[StyleResolver] = None
        self._table_parser: Optional[TableParser] = None
        # Innermost containing table's w:tblStyle while parsing cell content;
        # used to apply table-style pPr to cell paragraphs (ECMA-376 §17.7.2).
        self._table_style_stack: List[str] = []
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
        # Route nested tables through _parse_table so the table-style
        # stack is maintained for nested cell paragraphs too.
        self._table_parser._parse_nested = self._parse_table
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
                elif tag == 'sdt':
                    self._parse_body_sdt(child, model)
                elif tag == 'customXml':
                    self._parse_body_custom_xml(child, model)
                elif child.tag == f"{{{NS.MC}}}AlternateContent":
                    self._parse_body_alternate_content(child, model)
                elif tag == 'sectPr':
                    section = self._parse_section(child)
                    if section:
                        model.sections.append(section)

        if not model.sections:
            model.sections.append(Section())

        self._parse_footnotes(model)
        self._parse_endnotes(model)

        # Parse header/footer XML for each section
        hf_parser = HeaderFooterParser(
            self._parse_paragraph,
            self._parse_table,
        )
        # Save the original drawing parser rels
        original_rels = self._drawing_parser.rels if self._drawing_parser else {}
        for section in model.sections:
            for htype, rid in section.header_refs.items():
                xml = self.package.headers.get(rid)
                if xml:
                    # Get header filename and swap rels for image resolution
                    header_filename = self._get_part_filename(rid, 'header')
                    if header_filename and self._drawing_parser:
                        header_rels = self.package.header_rels.get(header_filename, {})
                        self._drawing_parser.rels = header_rels
                    section.header_bodies[htype] = hf_parser.parse(xml)
            for ftype, rid in section.footer_refs.items():
                xml = self.package.footers.get(rid)
                if xml:
                    # Get footer filename and swap rels for image resolution
                    footer_filename = self._get_part_filename(rid, 'footer')
                    if footer_filename and self._drawing_parser:
                        footer_rels = self.package.footer_rels.get(footer_filename, {})
                        self._drawing_parser.rels = footer_rels
                    section.footer_bodies[ftype] = hf_parser.parse(xml)
        # Restore original rels
        if self._drawing_parser:
            self._drawing_parser.rels = original_rels

        # Header/footer inheritance: sections without explicit headers/footers
        # inherit from the previous section (OOXML behavior)
        for i in range(1, len(model.sections)):
            prev = model.sections[i - 1]
            curr = model.sections[i]
            # Inherit header bodies if current section has none
            if not curr.header_bodies and prev.header_bodies:
                curr.header_bodies = dict(prev.header_bodies)
            # Inherit footer bodies if current section has none
            if not curr.footer_bodies and prev.footer_bodies:
                curr.footer_bodies = dict(prev.footer_bodies)

        # Numbering
        model.numbering = NumberingParser().parse(self.package.numbering_xml or b"")

        model.media = self.package.media
        return model

    def _parse_body_sdt(self, elem, model: DocumentModel) -> None:
        content = elem.find(f"{{{NS.W}}}sdtContent")
        if content is None:
            logger.warning("body_sdt_unsupported: no sdtContent")
            return
        logger.warning(
            "body_sdt_fallback: rendered content without control appearance"
        )
        self._parse_body_container(content, model)

    def _parse_body_custom_xml(self, elem, model: DocumentModel) -> None:
        supported_tags = {"p", "tbl", "sdt", "customXml"}
        has_supported_content = any(
            (
                child.tag.split("}")[-1]
                if "}" in child.tag
                else child.tag
            )
            in supported_tags
            for child in elem
        )
        if not has_supported_content:
            logger.warning(
                "body_custom_xml_unsupported: no supported block content"
            )
            return
        logger.warning(
            "body_custom_xml_fallback: rendered content without data mapping"
        )
        self._parse_body_container(elem, model)

    def _parse_body_alternate_content(
        self, elem, model: DocumentModel
    ) -> None:
        unsupported_requires = []
        for choice in elem.findall(f"{{{NS.MC}}}Choice"):
            requires = choice.get("Requires", "").split()
            if requires and all(prefix == "w" for prefix in requires):
                logger.warning(
                    "body_alternate_content_choice: rendered Choice for "
                    "supported Requires=%s",
                    " ".join(requires),
                )
                before = (len(model.body), len(model.sections))
                self._parse_body_container(choice, model)
                if before == (len(model.body), len(model.sections)):
                    logger.warning(
                        "body_alternate_content_unsupported: selected Choice "
                        "has no supported block content"
                    )
                return
            unsupported_requires.extend(requires or ["<missing>"])

        fallback = elem.find(f"{{{NS.MC}}}Fallback")
        if fallback is not None:
            logger.warning(
                "body_alternate_content_fallback: rendered Fallback; "
                "unsupported Requires=%s",
                " ".join(unsupported_requires) or "<none>",
            )
            before = (len(model.body), len(model.sections))
            self._parse_body_container(fallback, model)
            if before == (len(model.body), len(model.sections)):
                logger.warning(
                    "body_alternate_content_unsupported: Fallback has no "
                    "supported block content"
                )
            return

        logger.warning(
            "body_alternate_content_unsupported: no supported Choice or "
            "Fallback"
        )

    def _parse_body_container(self, container, model: DocumentModel) -> None:
        for child in container:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                para = self._parse_paragraph(child)
                if para:
                    model.body.append(para)
                    if para.section_break is not None:
                        model.sections.append(para.section_break)
            elif tag == "tbl":
                table = self._parse_table(child)
                if table:
                    model.body.append(table)
            elif tag == "sdt":
                self._parse_body_sdt(child, model)
            elif tag == "customXml":
                self._parse_body_custom_xml(child, model)
            elif child.tag == f"{{{NS.MC}}}AlternateContent":
                self._parse_body_alternate_content(child, model)

    def _parse_footnotes(self, model: DocumentModel) -> None:
        if not self.package.footnotes_xml:
            return
        try:
            root = ET.fromstring(self.package.footnotes_xml)
        except ET.ParseError as exc:
            logger.warning("footnotes_malformed_xml: %s", exc)
            return
        for note in root.findall(f"{{{NS.W}}}footnote"):
            note_id = note.get(f"{{{NS.W}}}id")
            if note_id is None:
                continue
            try:
                if int(note_id) < 0:
                    continue
            except ValueError:
                logger.warning("footnote_invalid_id: %s", note_id)
                continue
            paragraphs = []
            for child in note:
                tag = child.tag.split("}")[-1]
                if tag == "p":
                    paragraph = self._parse_paragraph(child)
                    if paragraph is not None:
                        paragraphs.append(paragraph)
                elif tag == "tbl":
                    logger.warning(
                        "footnote_unsupported_table: footnote %s table omitted",
                        note_id,
                    )
            if paragraphs:
                marker_props = RunProps(
                    font_size=10.0,
                    vertical_align="superscript",
                    position_offset=-3.0,
                )
                paragraphs[0].runs.insert(
                    0,
                    Run(
                        text=TextRun(note_id, marker_props),
                        footnote_id=note_id,
                    ),
                )
            model.footnotes[note_id] = paragraphs

        referenced = {
            run.footnote_id
            for paragraph in model.body
            if isinstance(paragraph, Paragraph)
            for run in paragraph.runs
            if run.footnote_id is not None
        }
        for note_id in sorted(referenced):
            if note_id not in model.footnotes:
                logger.warning(
                    "footnote_missing_definition: reference %s has no definition",
                    note_id,
                )

    def _parse_endnotes(self, model: DocumentModel) -> None:
        if not self.package.endnotes_xml:
            return
        try:
            root = ET.fromstring(self.package.endnotes_xml)
        except ET.ParseError as exc:
            logger.warning("endnotes_malformed_xml: %s", exc)
            return
        for note in root.findall(f"{{{NS.W}}}endnote"):
            note_id = note.get(f"{{{NS.W}}}id")
            if note_id is None:
                continue
            try:
                if int(note_id) < 0:
                    continue
            except ValueError:
                logger.warning("endnote_invalid_id: %s", note_id)
                continue
            paragraphs = []
            for child in note:
                tag = child.tag.split("}")[-1]
                if tag == "p":
                    paragraph = self._parse_paragraph(child)
                    if paragraph is not None:
                        paragraphs.append(paragraph)
                elif tag == "tbl":
                    logger.warning(
                        "endnote_unsupported_table: endnote %s table omitted",
                        note_id,
                    )
            if paragraphs:
                marker_props = RunProps(
                    font_size=10.0,
                    vertical_align="superscript",
                    position_offset=-3.0,
                )
                paragraphs[0].runs.insert(
                    0,
                    Run(
                        text=TextRun(note_id, marker_props),
                        endnote_id=note_id,
                    ),
                )
            model.endnotes[note_id] = paragraphs

        referenced = {
            run.endnote_id
            for paragraph in self._iter_paragraphs(model.body)
            for run in paragraph.runs
            if run.endnote_id is not None
        }
        for note_id in sorted(referenced):
            if note_id not in model.endnotes:
                logger.warning(
                    "endnote_missing_definition: reference %s has no definition",
                    note_id,
                )

    @classmethod
    def _iter_paragraphs(cls, blocks):
        """Yield body paragraphs, including those in nested table cells."""
        for block in blocks:
            if isinstance(block, Paragraph):
                yield block
            elif isinstance(block, Table):
                for row in block.rows:
                    for cell in row.cells:
                        yield from cls._iter_paragraphs(cell.blocks)

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
            table_style_id = (
                self._table_style_stack[-1] if self._table_style_stack else None
            )
            para.props = self._style_resolver.resolve_para(
                style_id, direct, direct_set, table_style_id=table_style_id
            )
            para.props.style_id = style_id
        else:
            para.props = direct

        # Section break embedded in paragraph properties
        if props_elem is not None:
            sect = props_elem.find(f"{{{NS.W}}}sectPr")
            if sect is not None:
                para.section_break = self._parse_section(sect)

        self._append_paragraph_content(elem, para, style_id)

        return para

    def _append_paragraph_content(
        self, container, para: Paragraph, para_style_id: str
    ) -> None:
        """Append visible paragraph children in document order.

        Insertions and moved-to content are treated as accepted revisions;
        deletions and moved-from content are omitted.  Transparent containers
        such as hyperlinks and content controls are traversed recursively so
        revision wrappers do not make their nested runs disappear.
        """
        for child in container:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "pPr":
                continue
            if tag in ("del", "moveFrom"):
                continue
            if tag == "r":
                para.runs.extend(
                    self._parse_run_sequence(
                        child,
                        para_style_id=para_style_id,
                        target_para=para,
                    )
                )
                continue
            if tag in ("oMath", "oMathPara"):
                ast = self._math_parser.parse_element(child)
                if ast is not None:
                    para.runs.append(Run(math=MathRun(ast=ast)))
                continue
            if tag == "AlternateContent":
                choice = child.find(f"{{{NS.MC}}}Choice")
                fallback = child.find(f"{{{NS.MC}}}Fallback")
                selected = choice if choice is not None else fallback
                if selected is not None:
                    self._append_paragraph_content(
                        selected, para, para_style_id
                    )
                continue

            # w:ins, w:moveTo, w:hyperlink, w:smartTag, w:customXml,
            # w:sdt/w:sdtContent and w:fldSimple are transparent for our
            # accepted-revisions rendering model.
            self._append_paragraph_content(child, para, para_style_id)

    def _parse_run_sequence(
        self,
        elem,
        para_style_id: str = "",
        target_para: Optional[Paragraph] = None,
    ) -> List[Run]:
        """Parse a run while preserving interleaved break/tab markers.

        A w:r may contain ``lastRenderedPageBreak`` followed by text, or text
        on both sides of a normal ``w:br``.  Returning only one Run would drop
        either the marker or the text, so split such XML into ordered IR runs.
        """
        marker_names = {"br", "tab", "lastRenderedPageBreak"}
        children = list(elem)
        if not any(
            (child.tag.split("}")[-1] if "}" in child.tag else child.tag)
            in marker_names
            for child in children
        ):
            run = self._parse_run(
                elem,
                para_style_id=para_style_id,
                target_para=target_para,
            )
            return [run] if run else []

        import copy

        r_pr = elem.find(f"{{{NS.W}}}rPr")
        result: List[Run] = []
        buffered = []

        def flush() -> None:
            if not buffered:
                return
            fragment = ET.Element(elem.tag, elem.attrib)
            if r_pr is not None:
                fragment.append(copy.deepcopy(r_pr))
            for item in buffered:
                fragment.append(copy.deepcopy(item))
            run = self._parse_run(
                fragment,
                para_style_id=para_style_id,
                target_para=target_para,
            )
            if run:
                result.append(run)
            buffered.clear()

        for child in children:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "rPr":
                continue
            if tag in marker_names:
                flush()
                if tag == "tab":
                    result.append(Run(tab=TabRun()))
                else:
                    break_type = (
                        child.get(f"{{{NS.W}}}type", "line")
                        if tag == "br"
                        else "page"
                    )
                    result.append(Run(brk=BreakRun(break_type=break_type)))
            else:
                buffered.append(child)
        flush()
        return result

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

    def _parse_run(self, elem, para_style_id: str = "", target_para: Optional[Paragraph] = None) -> Optional[Run]:
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

        # Legacy VML drawings (w:pict/v:shape/v:line).  These are still common
        # in WPS-authored documents and older Word flowcharts.
        pict = elem.find(f"{{{NS.W}}}pict")
        if pict is not None and self._drawing_parser is not None:
            items = self._drawing_parser.parse_vml(pict)
            if target_para is not None:
                target_para.group_items.extend(items)
            if items:
                # VML text lives inside its own textbox paragraphs and must not
                # be duplicated into the host paragraph's normal text flow.
                return None

        # Drawing / image / textbox
        drawing = elem.find(f"{{{NS.W}}}drawing")
        if drawing is None:
            # Word often wraps w:drawing inside mc:AlternateContent > mc:Choice
            alt = elem.find(f"{{{NS.MC}}}AlternateContent")
            if alt is not None:
                choice = alt.find(f"{{{NS.MC}}}Choice")
                fallback = alt.find(f"{{{NS.MC}}}Fallback")
                container = choice if choice is not None else fallback
                if container is not None:
                    drawing = container.find(f".//{{{NS.W}}}drawing")

        if drawing is not None and self._drawing_parser is not None:
            # Check for WordprocessingGroup (wpg:wgp) first
            group = self._drawing_parser.parse_group(drawing)
            if group is not None:
                # Group contains image + textboxes + lines
                img = group.get("image")
                if img:
                    run.image = img
                # Store textboxes and lines as group_items on the paragraph
                group_has_items = False
                if target_para is not None:
                    for tbox in group.get("textboxes", []):
                        target_para.group_items.append({"type": "textbox", "data": tbox})
                        group_has_items = True
                    for line in group.get("lines", []):
                        target_para.group_items.append({"type": "line", "data": line})
                        group_has_items = True
                if run.image or group_has_items:
                    return run

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

        footnote_ref = elem.find(f"{{{NS.W}}}footnoteReference")
        if footnote_ref is not None:
            note_id = footnote_ref.get(f"{{{NS.W}}}id")
            if note_id is not None:
                run_props.vertical_align = "superscript"
                # Word scales the reference glyph as superscript but keeps it
                # close to the text cap height; compensate for the generic
                # superscript baseline used by the layout engine.
                run_props.position_offset -= 3.0
                run.text = TextRun(text=note_id, props=run_props)
                run.footnote_id = note_id
                return run

        endnote_ref = elem.find(f"{{{NS.W}}}endnoteReference")
        if endnote_ref is not None:
            note_id = endnote_ref.get(f"{{{NS.W}}}id")
            if note_id is not None:
                run_props.vertical_align = "superscript"
                run_props.position_offset -= 3.0
                run.text = TextRun(text=note_id, props=run_props)
                run.endnote_id = note_id
                return run

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
            self._table_parser._parse_nested = self._parse_table
        style_id = ""
        tbl_pr = elem.find(f"{{{NS.W}}}tblPr")
        if tbl_pr is not None:
            st = tbl_pr.find(f"{{{NS.W}}}tblStyle")
            if st is not None:
                style_id = st.get(f"{{{NS.W}}}val", "") or ""
        self._table_style_stack.append(style_id)
        try:
            return self._table_parser.parse(elem)
        finally:
            self._table_style_stack.pop()

    def _get_part_filename(self, rid: str, part_type: str) -> Optional[str]:
        """Get the filename for a header/footer part from its rId.
        
        Args:
            rid: Relationship ID (e.g., 'rId5')
            part_type: 'header' or 'footer'
            
        Returns:
            Filename like 'header1.xml' or None if not found
        """
        target = self.package.document_rels.get(rid, '')
        if not target:
            return None
        target = target.replace('\\', '/').lstrip('/')
        if target.startswith('word/'):
            target = target[5:]
        # Extract just the filename
        filename = target.split('/')[-1]
        if part_type in filename.lower():
            return filename
        return None

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

        # Document baseline grid (w:docGrid).  linePitch is expressed in
        # twips, but is active vertically only for type=lines/linesAndChars.
        # An omitted type means the OOXML "default" (inactive) mode.
        doc_grid = elem.find(f"{{{NS.W}}}docGrid")
        if doc_grid is not None:
            section.doc_grid_type = doc_grid.get(
                f"{{{NS.W}}}type", "default"
            )
            line_pitch = doc_grid.get(f"{{{NS.W}}}linePitch")
            if line_pitch:
                pitch_pt = Units.parse_twips(line_pitch)
                if pitch_pt > 0:
                    section.doc_grid_line_pitch = pitch_pt

        # Page borders (w:pgBorders)
        pg_borders = elem.find(f"{{{NS.W}}}pgBorders")
        if pg_borders is not None:
            from ..model.section import PageBorders, PageBorderDef
            borders = PageBorders(
                display=pg_borders.get(f"{{{NS.W}}}display", "allPages"),
                offset_from=pg_borders.get(f"{{{NS.W}}}offsetFrom", "page"),
            )
            for side in ("top", "bottom", "left", "right"):
                side_elem = pg_borders.find(f"{{{NS.W}}}{side}")
                if side_elem is not None:
                    bd = PageBorderDef(
                        style=side_elem.get(f"{{{NS.W}}}val", "none"),
                        size=int(side_elem.get(f"{{{NS.W}}}sz", "0")),
                        space=int(side_elem.get(f"{{{NS.W}}}space", "0")),
                        color=side_elem.get(f"{{{NS.W}}}color"),
                    )
                    setattr(borders, side, bd)
            section.page_borders = borders

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
