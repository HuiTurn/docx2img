"""Style data models"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Set
from .paragraph import RunProps, ParaProps


@dataclass
class Style:
    """Style definition from styles.xml."""
    style_id: str = ""
    name: str = ""
    type: str = "paragraph"  # paragraph | character | table | numbering
    based_on: Optional[str] = None
    next: Optional[str] = None
    run_props: RunProps = field(default_factory=RunProps)
    para_props: ParaProps = field(default_factory=ParaProps)
    # Fields explicitly set in this style's XML (for correct merge)
    run_set: Set[str] = field(default_factory=set)
    para_set: Set[str] = field(default_factory=set)


@dataclass
class StyleTable:
    """Collection of styles with lookup."""
    styles: Dict[str, Style] = field(default_factory=dict)
    default_paragraph: Optional[Style] = None
    default_character: Optional[Style] = None

    def get(self, style_id: str) -> Optional[Style]:
        return self.styles.get(style_id)

    def add(self, style: Style) -> None:
        self.styles[style.style_id] = style
