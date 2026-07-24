"""Theme color / font resolution."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..model.paragraph import RunProps


class ThemeResolver:
    """Resolve themeColor / theme font tokens against theme1.xml data."""

    def __init__(
        self,
        theme_colors: Optional[Dict[str, Tuple[int, int, int]]] = None,
        theme_fonts: Optional[Dict[str, str]] = None,
    ):
        self.theme_colors = theme_colors or {}
        self.theme_fonts = theme_fonts or {}

    def resolve_color(
        self,
        hex_val: Optional[str] = None,
        theme_color: Optional[str] = None,
        tint: Optional[str] = None,
        shade: Optional[str] = None,
    ) -> Tuple[int, int, int]:
        if hex_val and hex_val != "auto":
            return self._hex_to_rgb(hex_val)
        if theme_color:
            base = self.theme_colors.get(theme_color, (0, 0, 0))
            if tint:
                base = self._apply_tint(base, int(tint, 16) / 255.0)
            if shade:
                base = self._apply_shade(base, int(shade, 16) / 255.0)
            return base
        return (0, 0, 0)

    def apply_fonts(self, props: RunProps) -> RunProps:
        """Replace +mj-lt / +mn-lt / +mj-ea / +mn-ea with theme faces."""
        mapping = {
            "+mj-lt": self.theme_fonts.get("major_latin", "Cambria"),
            "+mn-lt": self.theme_fonts.get("minor_latin", "Calibri"),
            "+mj-ea": self.theme_fonts.get("major_ea") or self.theme_fonts.get("major_latin", "SimSun"),
            "+mn-ea": self.theme_fonts.get("minor_ea") or self.theme_fonts.get("minor_latin", "SimSun"),
            "+mj-cs": self.theme_fonts.get("major_cs", "Times New Roman"),
            "+mn-cs": self.theme_fonts.get("minor_cs", "Times New Roman"),
            # OOXML theme attribute values sometimes kept raw
            "majorAscii": self.theme_fonts.get("major_latin", "Cambria"),
            "minorAscii": self.theme_fonts.get("minor_latin", "Calibri"),
            "majorEastAsia": self.theme_fonts.get("major_ea", "SimSun"),
            "minorEastAsia": self.theme_fonts.get("minor_ea", "SimSun"),
        }
        for attr in ("font_ascii", "font_h_ansi", "font_east_asia", "font_cs"):
            val = getattr(props, attr, None)
            if val in mapping:
                setattr(props, attr, mapping[val])
        return props

    def apply_color(self, props: RunProps) -> RunProps:
        raw = getattr(props, "_color_raw", None)
        if not raw:
            return props
        props.color = self.resolve_color(
            hex_val=raw.get("val"),
            theme_color=raw.get("themeColor"),
            tint=raw.get("themeTint"),
            shade=raw.get("themeShade"),
        )
        return props

    def _hex_to_rgb(self, val: str) -> Tuple[int, int, int]:
        val = val.lstrip("#")
        if len(val) == 6:
            try:
                return (int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))
            except ValueError:
                pass
        return (0, 0, 0)

    def _apply_tint(self, rgb: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
        """Mix toward white."""
        return tuple(int(c + (255 - c) * factor) for c in rgb)

    def _apply_shade(self, rgb: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
        """Mix toward black."""
        return tuple(int(c * factor) for c in rgb)
