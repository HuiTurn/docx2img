"""Math AST nodes for OMML."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class MathNode:
    pass


@dataclass
class MathChar(MathNode):
    char: str
    style: str = "i"  # p=plain, i=italic, b=bold


@dataclass
class MathRunSeq(MathNode):
    """Sequence of math nodes (row)."""
    children: List[MathNode] = field(default_factory=list)


@dataclass
class MathFrac(MathNode):
    numerator: Optional[MathNode] = None
    denominator: Optional[MathNode] = None


@dataclass
class MathRad(MathNode):
    degree: Optional[MathNode] = None
    radicand: Optional[MathNode] = None


@dataclass
class MathBar(MathNode):
    body: Optional[MathNode] = None
    position: str = "top"


@dataclass
class MathSup(MathNode):
    base: Optional[MathNode] = None
    superscript: Optional[MathNode] = None


@dataclass
class MathSub(MathNode):
    base: Optional[MathNode] = None
    subscript: Optional[MathNode] = None


@dataclass
class MathSubSup(MathNode):
    base: Optional[MathNode] = None
    subscript: Optional[MathNode] = None
    superscript: Optional[MathNode] = None


@dataclass
class MathNary(MathNode):
    char: str = "∑"
    lower: Optional[MathNode] = None
    upper: Optional[MathNode] = None
    body: Optional[MathNode] = None


@dataclass
class MathDelim(MathNode):
    open_chr: str = "("
    close_chr: str = ")"
    body: Optional[MathNode] = None


@dataclass
class MathMatrix(MathNode):
    rows: List[List[MathNode]] = field(default_factory=list)


@dataclass
class MathFunc(MathNode):
    name: str = "sin"
    arg: Optional[MathNode] = None
