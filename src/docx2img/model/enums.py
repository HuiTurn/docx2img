"""Enumeration types for IR models"""

from enum import Enum


class Alignment(Enum):
    """Paragraph alignment"""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"
    DISTRIBUTE = "distribute"


class BorderStyle(Enum):
    """Border line style"""
    NONE = "none"
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    THICK = "thick"
    DASHED = "dashed"
    DOTTED = "dotted"
    WAVE = "wave"


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
