"""Parse header/footer XML parts."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional, Callable, Any

from ..model.paragraph import Paragraph, Run, TextRun, RunProps, ParaProps
from .namespaces import NS


FIELD_PAGE = "{{PAGE}}"
FIELD_NUMPAGES = "{{NUMPAGES}}"
FIELD_DATE = "{{DATE}}"
DEFAULT_REFERENCE_DATETIME = datetime(2000, 1, 1)


class HeaderFooterParser:
    """Parse word/header*.xml / footer*.xml into paragraph lists."""

    def __init__(self, para_parser: Callable):
        """
        Args:
            para_parser: DocumentParser._parse_paragraph bound method
        """
        self._parse_para = para_parser

    def parse(self, xml_bytes: bytes) -> List[Any]:
        if not xml_bytes:
            return []
        root = ET.fromstring(xml_bytes)
        blocks = []
        for child in root:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                # Pre-process fields into placeholder text runs
                self._inject_field_placeholders(child)
                para = self._parse_para(child)
                if para:
                    blocks.append(para)
            elif tag == "tbl":
                # Tables in headers — rely on document table parser if available
                pass
        return blocks

    def _inject_field_placeholders(self, para_elem) -> None:
        """Replace fldSimple / complex fields with placeholder w:r siblings."""
        # fldSimple → replace element with a w:r containing placeholder
        for fld in list(para_elem.findall(f"{{{NS.W}}}fldSimple")):
            instr = fld.get(f"{{{NS.W}}}instr", "") or ""
            placeholder = self.resolve_field_instr(instr, as_placeholder=True)
            r = ET.Element(f"{{{NS.W}}}r")
            t = ET.SubElement(r, f"{{{NS.W}}}t")
            t.text = placeholder
            # Replace fldSimple with run in parent
            parent = para_elem
            idx = list(parent).index(fld)
            parent.remove(fld)
            parent.insert(idx, r)

        # Complex fields: begin → instrText → separate → result → end
        children = list(para_elem)
        i = 0
        while i < len(children):
            child = children[i]
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag != "r":
                i += 1
                continue
            fld_char = child.find(f"{{{NS.W}}}fldChar")
            if fld_char is None or fld_char.get(f"{{{NS.W}}}fldCharType") != "begin":
                i += 1
                continue
            j = i + 1
            instr_parts = []
            while j < len(children):
                c2 = children[j]
                t2 = c2.tag.split("}")[-1] if "}" in c2.tag else c2.tag
                if t2 == "r":
                    instr = c2.find(f"{{{NS.W}}}instrText")
                    if instr is not None and instr.text:
                        instr_parts.append(instr.text)
                    fc = c2.find(f"{{{NS.W}}}fldChar")
                    if fc is not None and fc.get(f"{{{NS.W}}}fldCharType") == "end":
                        j += 1
                        break
                j += 1
            placeholder = self.resolve_field_instr(" ".join(instr_parts), as_placeholder=True)
            for k in range(j - 1, i - 1, -1):
                para_elem.remove(children[k])
            r = ET.Element(f"{{{NS.W}}}r")
            t = ET.SubElement(r, f"{{{NS.W}}}t")
            t.text = placeholder
            para_elem.insert(i, r)
            children = list(para_elem)
            i += 1

    @staticmethod
    def resolve_field_instr(
        instr: str,
        as_placeholder: bool = False,
        reference_datetime: Optional[datetime] = None,
    ) -> str:
        cleaned = re.sub(r"\s+", " ", (instr or "").strip()).upper()
        # Strip quotes / switches
        token = cleaned.split(" ")[0] if cleaned else ""
        if token == "PAGE":
            return FIELD_PAGE if as_placeholder else ""
        if token == "NUMPAGES":
            return FIELD_NUMPAGES if as_placeholder else ""
        if token == "DATE":
            if as_placeholder:
                return FIELD_DATE
            reference = reference_datetime or DEFAULT_REFERENCE_DATETIME
            return reference.strftime("%Y-%m-%d")
        return ""

    @staticmethod
    def expand_placeholders(
        text: str,
        page_num: int,
        total_pages: int,
        reference_datetime: Optional[datetime] = None,
    ) -> str:
        reference = reference_datetime or DEFAULT_REFERENCE_DATETIME
        return (
            text.replace(FIELD_PAGE, str(page_num))
            .replace(FIELD_NUMPAGES, str(total_pages))
            .replace(FIELD_DATE, reference.strftime("%Y-%m-%d"))
        )
