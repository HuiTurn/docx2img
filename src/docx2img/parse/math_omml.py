"""Parse OMML (Office Math Markup Language) into Math AST."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional, List

from ..model.math_ast import (
    MathNode, MathChar, MathRunSeq, MathFrac, MathRad, MathSup, MathSub,
    MathSubSup, MathNary, MathDelim, MathMatrix, MathFunc, MathBar,
)

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


class OmmlParser:
    """Parse m:oMath / m:oMathPara into MathNode AST."""

    def parse_element(self, elem) -> Optional[MathNode]:
        if elem is None:
            return None
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag in ("oMath", "e", "num", "den", "sub", "sup", "deg", "lim", "fName"):
            return self._parse_children_seq(elem)
        if tag == "r":
            return self._parse_run(elem)
        if tag == "f":
            return MathFrac(
                numerator=self._child(elem, "num"),
                denominator=self._child(elem, "den"),
            )
        if tag == "rad":
            return MathRad(
                degree=self._child(elem, "deg"),
                radicand=self._child(elem, "e"),
            )
        if tag == "bar":
            pos = elem.find(f"{{{M}}}barPr/{{{M}}}pos")
            position = (
                "bottom"
                if pos is not None and pos.get(f"{{{M}}}val") == "bot"
                else "top"
            )
            return MathBar(body=self._child(elem, "e"), position=position)
        if tag == "sSup":
            return MathSup(base=self._child(elem, "e"), superscript=self._child(elem, "sup"))
        if tag == "sSub":
            return MathSub(base=self._child(elem, "e"), subscript=self._child(elem, "sub"))
        if tag == "sSubSup":
            return MathSubSup(
                base=self._child(elem, "e"),
                subscript=self._child(elem, "sub"),
                superscript=self._child(elem, "sup"),
            )
        if tag == "nary":
            chr_elem = elem.find(f"{{{M}}}naryPr/{{{M}}}chr")
            ch = "∑"
            if chr_elem is not None and chr_elem.get(f"{{{M}}}val"):
                ch = chr_elem.get(f"{{{M}}}val")
            return MathNary(
                char=ch,
                lower=self._child(elem, "sub"),
                upper=self._child(elem, "sup"),
                body=self._child(elem, "e"),
            )
        if tag == "d":
            beg = elem.find(f"{{{M}}}dPr/{{{M}}}begChr")
            end = elem.find(f"{{{M}}}dPr/{{{M}}}endChr")
            return MathDelim(
                open_chr=(beg.get(f"{{{M}}}val") if beg is not None else "(") or "(",
                close_chr=(end.get(f"{{{M}}}val") if end is not None else ")") or ")",
                body=self._child(elem, "e"),
            )
        if tag == "m":
            rows = []
            for mr in elem.findall(f"{{{M}}}mr"):
                cells = []
                for e in mr.findall(f"{{{M}}}e"):
                    node = self._parse_children_seq(e)
                    if node:
                        cells.append(node)
                rows.append(cells)
            return MathMatrix(rows=rows)
        if tag == "func":
            name_node = self._child(elem, "fName")
            name = self._text_of(name_node) or "f"
            return MathFunc(name=name, arg=self._child(elem, "e"))
        if tag == "oMathPara":
            for child in elem:
                t = child.tag.split("}")[-1]
                if t == "oMath":
                    return self.parse_element(child)
            return self._parse_children_seq(elem)

        return self._parse_children_seq(elem)

    def parse_xml(self, xml_bytes: bytes) -> Optional[MathNode]:
        root = ET.fromstring(xml_bytes)
        return self.parse_element(root)

    def _parse_run(self, elem) -> Optional[MathNode]:
        texts = []
        for t in elem.findall(f"{{{M}}}t"):
            texts.append(t.text or "")
        text = "".join(texts)
        if not text:
            return None
        sty = elem.find(f"{{{M}}}rPr/{{{M}}}sty")
        style = "i"
        if sty is not None:
            style = sty.get(f"{{{M}}}val", "i") or "i"
        # Single chars as sequence
        if len(text) == 1:
            return MathChar(char=text, style=style)
        return MathRunSeq(children=[MathChar(char=c, style=style) for c in text])

    def _child(self, elem, name: str) -> Optional[MathNode]:
        child = elem.find(f"{{{M}}}{name}")
        if child is None:
            return None
        return self.parse_element(child)

    def _parse_children_seq(self, elem) -> Optional[MathNode]:
        nodes: List[MathNode] = []
        for child in elem:
            tag = child.tag.split("}")[-1]
            if tag in (
                "rPr", "fPr", "radPr", "barPr", "sSupPr", "sSubPr",
                "naryPr", "dPr", "mPr", "ctrlPr",
            ):
                continue
            node = self.parse_element(child)
            if node is None:
                continue
            if isinstance(node, MathRunSeq):
                nodes.extend(node.children)
            else:
                nodes.append(node)
        if not nodes:
            return None
        if len(nodes) == 1:
            return nodes[0]
        return MathRunSeq(children=nodes)

    def _text_of(self, node: Optional[MathNode]) -> str:
        if node is None:
            return ""
        if isinstance(node, MathChar):
            return node.char
        if isinstance(node, MathRunSeq):
            return "".join(self._text_of(c) for c in node.children)
        return ""
