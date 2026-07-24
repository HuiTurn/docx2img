"""Parse word/theme/theme1.xml for colors and fonts."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, Tuple

from .namespaces import NS, A


class ThemeParser:
    """Parse theme1.xml → theme_colors + theme_fonts."""

    # DrawingML namespace for theme
    A_NS = A

    def parse(self, theme_xml: bytes) -> Tuple[Dict[str, Tuple[int, int, int]], Dict[str, str]]:
        colors: Dict[str, Tuple[int, int, int]] = {}
        fonts: Dict[str, str] = {}

        if not theme_xml:
            return colors, fonts

        root = ET.fromstring(theme_xml)
        a = self.A_NS

        # a:themeElements / a:clrScheme
        clr_scheme = root.find(f".//{{{a}}}clrScheme")
        if clr_scheme is not None:
            for child in clr_scheme:
                tag = child.tag.split("}")[-1]
                rgb = self._parse_color_node(child)
                if rgb:
                    colors[tag] = rgb

        # a:fontScheme
        font_scheme = root.find(f".//{{{a}}}fontScheme")
        if font_scheme is not None:
            major = font_scheme.find(f"{{{a}}}majorFont")
            minor = font_scheme.find(f"{{{a}}}minorFont")
            if major is not None:
                fonts.update(self._parse_font_slot(major, "major"))
            if minor is not None:
                fonts.update(self._parse_font_slot(minor, "minor"))

        return colors, fonts

    def _parse_color_node(self, node) -> Tuple[int, int, int] | None:
        a = self.A_NS
        srgb = node.find(f"{{{a}}}srgbClr")
        if srgb is not None:
            val = srgb.get("val")
            if val and len(val) == 6:
                return (
                    int(val[0:2], 16),
                    int(val[2:4], 16),
                    int(val[4:6], 16),
                )
        sys = node.find(f"{{{a}}}sysClr")
        if sys is not None:
            last = sys.get("lastClr")
            if last and len(last) == 6:
                return (
                    int(last[0:2], 16),
                    int(last[2:4], 16),
                    int(last[4:6], 16),
                )
        return None

    def _parse_font_slot(self, node, prefix: str) -> Dict[str, str]:
        a = self.A_NS
        result = {}
        latin = node.find(f"{{{a}}}latin")
        ea = node.find(f"{{{a}}}ea")
        cs = node.find(f"{{{a}}}cs")
        if latin is not None and latin.get("typeface"):
            result[f"{prefix}_latin"] = latin.get("typeface")
        if ea is not None and ea.get("typeface"):
            # empty typeface means "use latin" in some themes
            tf = ea.get("typeface")
            if tf:
                result[f"{prefix}_ea"] = tf
        if cs is not None and cs.get("typeface"):
            tf = cs.get("typeface")
            if tf:
                result[f"{prefix}_cs"] = tf

        # Script-specific fonts (e.g. Hans)
        for font in node.findall(f"{{{a}}}font"):
            script = font.get("script")
            typeface = font.get("typeface")
            if script in ("Hans", "Hang", "Hant", "Jpan") and typeface:
                key = f"{prefix}_ea"
                if key not in result:
                    result[key] = typeface
        return result
