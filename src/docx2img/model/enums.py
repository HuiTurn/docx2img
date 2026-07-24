"""Enumeration types for IR models"""

from enum import Enum


class Alignment(Enum):
    """Paragraph alignment"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "both"  # OOXML uses "both"
    DISTRIBUTE = "distribute"

    @classmethod
    def from_ooxml(cls, val: str) -> "Alignment":
        mapping = {
            "left": cls.LEFT,
            "start": cls.LEFT,
            "center": cls.CENTER,
            "right": cls.RIGHT,
            "end": cls.RIGHT,
            "both": cls.JUSTIFY,
            "justify": cls.JUSTIFY,
            "distribute": cls.DISTRIBUTE,
        }
        return mapping.get(val or "left", cls.LEFT)


class BorderStyle(Enum):
    """Border line style (OOXML w:val)."""
    NONE = "none"
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    THICK = "thick"
    DASHED = "dashed"
    DOTTED = "dotted"
    WAVE = "wave"
    # Compound borders — look like double lines (common on table outer edges)
    THIN_THICK_SMALL_GAP = "thinThickSmallGap"
    THICK_THIN_SMALL_GAP = "thickThinSmallGap"
    THIN_THICK_MEDIUM_GAP = "thinThickMediumGap"
    THICK_THIN_MEDIUM_GAP = "thickThinMediumGap"
    THIN_THICK_LARGE_GAP = "thinThickLargeGap"
    THICK_THIN_LARGE_GAP = "thickThinLargeGap"

    @classmethod
    def from_ooxml(cls, val: str) -> "BorderStyle":
        if not val or val in ("nil", "none"):
            return cls.NONE
        try:
            return cls(val)
        except ValueError:
            # Unknown compound / art borders → nearest visual equivalent
            low = val.lower()
            if "double" in low:
                return cls.DOUBLE
            if "thick" in low and "thin" in low:
                return cls.THICK_THIN_SMALL_GAP if low.startswith("thick") else cls.THIN_THICK_SMALL_GAP
            if "dash" in low:
                return cls.DASHED
            if "dot" in low:
                return cls.DOTTED
            if "wave" in low:
                return cls.WAVE
            if "triple" in low:
                return cls.TRIPLE
            return cls.SINGLE


class NumberFormat(Enum):
    """Numbering format"""
    DECIMAL = "decimal"           # 1, 2, 3
    UPPER_LETTER = "upperLetter"  # A, B, C
    LOWER_LETTER = "lowerLetter"  # a, b, c
    UPPER_ROMAN = "upperRoman"    # I, II, III
    LOWER_ROMAN = "lowerRoman"    # i, ii, iii
    BULLET = "bullet"             # •
    CHINESE_COUNTING = "chineseCounting"  # 一，二，三
    IDEOGRAPH_DIGITAL = "ideographDigital"
    NONE = "none"


class TabStopType(Enum):
    """Tab stop type"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    DECIMAL = "decimal"


class VerticalMerge(Enum):
    """Table cell vertical merge state"""
    RESTART = "restart"
    CONTINUE = "continue"
    NONE = "none"


class WrapType(Enum):
    """Image/text wrap type"""
    INLINE = "inline"
    SQUARE = "square"
    TIGHT = "tight"
    TOP_BOTTOM = "topAndBottom"
    BEHIND = "behind"
    IN_FRONT = "inFrontOf"


class SectionType(Enum):
    """Section break type"""
    NEXT_PAGE = "nextPage"
    CONTINUOUS = "continuous"
    EVEN_PAGE = "evenPage"
    ODD_PAGE = "oddPage"
