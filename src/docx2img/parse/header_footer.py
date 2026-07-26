"""Parse header/footer XML parts."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


class HeaderFooterParser:
    """Parse word/header*.xml / footer*.xml into paragraph lists."""

    def __init__(
        self,
        para_parser: Callable,
        table_parser: Optional[Callable] = None,
    ):
        """
        Args:
            para_parser: DocumentParser._parse_paragraph bound method
            table_parser: DocumentParser._parse_table bound method, when
                header/footer tables are supported by the caller
        """
        self._parse_para = para_parser
        self._parse_table = table_parser

    def parse(self, xml_bytes: bytes) -> List[Any]:
        if not xml_bytes:
            return []
        root = ET.fromstring(xml_bytes)
        blocks = []
        for child in root:
            blocks.extend(self._parse_block(child))
        return blocks

    def _parse_block(self, elem) -> List[Any]:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "p":
            self._inject_field_placeholders(elem)
            para = self._parse_para(elem)
            return [para] if para else []
        if tag == "tbl":
            if self._parse_table is None:
                logger.warning(
                    "header_footer_table_unsupported: "
                    "table parser unavailable"
                )
                return []
            try:
                table = self._parse_table(elem)
            except Exception as exc:
                logger.warning(
                    "header_footer_table_malformed: %s",
                    exc,
                )
                return []
            if table is None or not getattr(table, "rows", None):
                logger.warning(
                    "header_footer_table_empty: table has no rows"
                )
                return []
            return [table]
        if tag == "sdt":
            content = elem.find(f"{{{NS.W}}}sdtContent")
            if content is None:
                logger.warning(
                    "header_footer_sdt_unsupported: no sdtContent"
                )
                return []
            logger.warning(
                "header_footer_sdt_fallback: rendered content without "
                "control appearance"
            )
            blocks = []
            for child in content:
                blocks.extend(self._parse_block(child))
            return blocks
        return []

    def _inject_field_placeholders(self, para_elem) -> None:
        """Replace fldSimple / complex fields with placeholder w:r siblings."""
        # fldSimple → replace element with a w:r containing placeholder
        for fld in list(para_elem.findall(f"{{{NS.W}}}fldSimple")):
            instr = fld.get(f"{{{NS.W}}}instr", "") or ""
            placeholder = self.resolve_field_instr(instr, as_placeholder=True)
            parent = para_elem
            idx = list(parent).index(fld)
            parent.remove(fld)
            if placeholder:
                r = ET.Element(f"{{{NS.W}}}r")
                t = ET.SubElement(r, f"{{{NS.W}}}t")
                t.text = placeholder
                parent.insert(idx, r)
                continue

            token = self.field_token(instr)
            cached_children = list(fld)
            for offset, child in enumerate(cached_children):
                parent.insert(idx + offset, child)
            has_cached_text = any(
                (text.text or "")
                for child in cached_children
                for text in child.iter(f"{{{NS.W}}}t")
            )
            if has_cached_text:
                logger.warning(
                    "header_footer_field_cached: %s rendered cached result",
                    token,
                )
            else:
                logger.warning(
                    "header_footer_field_unsupported: %s has no cached result",
                    token,
                )

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
            separate_index = None
            end_index = None
            while j < len(children):
                c2 = children[j]
                t2 = c2.tag.split("}")[-1] if "}" in c2.tag else c2.tag
                if t2 == "r":
                    instr = c2.find(f"{{{NS.W}}}instrText")
                    if (
                        separate_index is None
                        and instr is not None
                        and instr.text
                    ):
                        instr_parts.append(instr.text)
                    fc = c2.find(f"{{{NS.W}}}fldChar")
                    if fc is not None:
                        field_type = fc.get(f"{{{NS.W}}}fldCharType")
                        if (
                            field_type == "separate"
                            and separate_index is None
                        ):
                            separate_index = j
                        elif field_type == "end":
                            end_index = j
                            j += 1
                            break
                j += 1
            field_instr = " ".join(instr_parts)
            placeholder = self.resolve_field_instr(
                field_instr, as_placeholder=True
            )
            cached_children = (
                children[separate_index + 1 : end_index]
                if separate_index is not None and end_index is not None
                else []
            )
            for k in range(j - 1, i - 1, -1):
                para_elem.remove(children[k])
            inserted = []
            if placeholder:
                r = ET.Element(f"{{{NS.W}}}r")
                t = ET.SubElement(r, f"{{{NS.W}}}t")
                t.text = placeholder
                inserted = [r]
            else:
                inserted = cached_children
                token = self.field_token(field_instr)
                has_cached_text = any(
                    (text.text or "")
                    for cached in cached_children
                    for text in cached.iter(f"{{{NS.W}}}t")
                )
                if has_cached_text:
                    logger.warning(
                        "header_footer_complex_field_cached: %s rendered "
                        "cached result",
                        token,
                    )
                else:
                    logger.warning(
                        "header_footer_complex_field_unsupported: %s has "
                        "no cached result",
                        token,
                    )
            for offset, cached in enumerate(inserted):
                para_elem.insert(i + offset, cached)
            children = list(para_elem)
            i += len(inserted)

    @staticmethod
    def field_token(instr: str) -> str:
        cleaned = re.sub(r"\s+", " ", (instr or "").strip())
        return cleaned.split(" ", 1)[0].upper() if cleaned else "UNKNOWN"

    @staticmethod
    def resolve_field_instr(
        instr: str,
        as_placeholder: bool = False,
        reference_datetime: Optional[datetime] = None,
    ) -> str:
        cleaned = re.sub(r"\s+", " ", (instr or "").strip()).upper()
        # Strip quotes / switches
        token = HeaderFooterParser.field_token(cleaned)
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
