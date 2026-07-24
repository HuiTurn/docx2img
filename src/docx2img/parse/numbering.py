"""Parse word/numbering.xml."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from ..model.numbering import (
    NumberingTable, AbstractNum, NumberingInstance, LevelDef,
)
from ..model.enums import NumberFormat
from .namespaces import NS
from .units import Units


class NumberingParser:
    def parse(self, xml_bytes: bytes) -> NumberingTable:
        table = NumberingTable()
        if not xml_bytes:
            return table

        root = ET.fromstring(xml_bytes)

        for abs_elem in root.findall(f"{{{NS.W}}}abstractNum"):
            abs_id = abs_elem.get(f"{{{NS.W}}}abstractNumId")
            if abs_id is None:
                continue
            abstract = AbstractNum(abstract_num_id=int(abs_id))
            name = abs_elem.find(f"{{{NS.W}}}name")
            if name is not None:
                abstract.name = name.get(f"{{{NS.W}}}val", "") or ""

            for lvl in abs_elem.findall(f"{{{NS.W}}}lvl"):
                level = self._parse_level(lvl)
                if level is not None:
                    abstract.levels[level.level] = level
            table.abstract_nums[abstract.abstract_num_id] = abstract

        for num_elem in root.findall(f"{{{NS.W}}}num"):
            num_id = num_elem.get(f"{{{NS.W}}}numId")
            if num_id is None:
                continue
            abs_ref = num_elem.find(f"{{{NS.W}}}abstractNumId")
            abs_id = int(abs_ref.get(f"{{{NS.W}}}val", "0")) if abs_ref is not None else 0
            inst = NumberingInstance(num_id=int(num_id), abstract_num_id=abs_id)
            for override in num_elem.findall(f"{{{NS.W}}}lvlOverride"):
                ilvl = override.get(f"{{{NS.W}}}ilvl")
                lvl_elem = override.find(f"{{{NS.W}}}lvl")
                if ilvl is not None and lvl_elem is not None:
                    level = self._parse_level(lvl_elem)
                    if level:
                        inst.level_overrides[int(ilvl)] = level
                start_ov = override.find(f"{{{NS.W}}}startOverride")
                if start_ov is not None and ilvl is not None:
                    # Create minimal override if only start changed
                    lvl = inst.level_overrides.get(int(ilvl)) or LevelDef(level=int(ilvl))
                    val = start_ov.get(f"{{{NS.W}}}val")
                    if val:
                        lvl.start = int(val)
                        inst.level_overrides[int(ilvl)] = lvl
            table.instances[inst.num_id] = inst

        return table

    def _parse_level(self, elem) -> Optional[LevelDef]:
        ilvl = elem.get(f"{{{NS.W}}}ilvl")
        if ilvl is None:
            return None
        level = LevelDef(level=int(ilvl))

        start = elem.find(f"{{{NS.W}}}start")
        if start is not None:
            level.start = int(start.get(f"{{{NS.W}}}val", "1"))

        fmt = elem.find(f"{{{NS.W}}}numFmt")
        if fmt is not None:
            val = fmt.get(f"{{{NS.W}}}val", "decimal")
            try:
                level.format = NumberFormat(val)
            except ValueError:
                level.format = NumberFormat.DECIMAL

        text = elem.find(f"{{{NS.W}}}lvlText")
        if text is not None:
            level.text = text.get(f"{{{NS.W}}}val", "%1.") or "%1."

        jc = elem.find(f"{{{NS.W}}}lvlJc")
        if jc is not None:
            level.alignment = jc.get(f"{{{NS.W}}}val", "left") or "left"

        ppr = elem.find(f"{{{NS.W}}}pPr")
        if ppr is not None:
            ind = ppr.find(f"{{{NS.W}}}ind")
            if ind is not None:
                left = ind.get(f"{{{NS.W}}}left")
                hanging = ind.get(f"{{{NS.W}}}hanging")
                if left:
                    level.left = Units.parse_twips(left)
                if hanging:
                    level.hanging = Units.parse_twips(hanging)

        rpr = elem.find(f"{{{NS.W}}}rPr")
        if rpr is not None:
            fonts = rpr.find(f"{{{NS.W}}}rFonts")
            if fonts is not None:
                level.font_name = (
                    fonts.get(f"{{{NS.W}}}ascii")
                    or fonts.get(f"{{{NS.W}}}hAnsi")
                    or ""
                )
            sz = rpr.find(f"{{{NS.W}}}sz")
            if sz is not None:
                val = sz.get(f"{{{NS.W}}}val")
                if val:
                    level.font_size = int(val) / 2.0

        return level
