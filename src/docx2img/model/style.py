"""Style data models"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from .paragraph import RunProps, ParaProps


@dataclass
class Style:
    """Style definition
    
    Attributes:
        style_id: Style identifier
        name: Style display name
        type: 'paragraph' | 'character' | 'table'
        based_on: Parent style ID (for inheritance)
        next: Next style ID (for following paragraph)
        run_props: Run properties defined by this style
        para_props: Paragraph properties defined by this style
    """
    style_id: str = ""
    name: str = ""
    type: str = "paragraph"  # paragraph | character | table
    based_on: Optional[str] = None
    next: Optional[str] = None
    run_props: RunProps = field(default_factory=RunProps)
    para_props: ParaProps = field(default_factory=ParaProps)


@dataclass
class StyleTable:
    """Collection of styles with lookup and resolution
    
    Attributes:
        styles: Dictionary of styles by ID
        default_paragraph: Default paragraph style
        default_character: Default character style
    """
    styles: Dict[str, Style] = field(default_factory=dict)
    default_paragraph: Optional[Style] = None
    default_character: Optional[Style] = None
    
    def get(self, style_id: str) -> Optional[Style]:
        """Get style by ID"""
        return self.styles.get(style_id)
    
    def add(self, style: Style) -> None:
        """Add a style to the table"""
        self.styles[style.style_id] = style
    
    def resolve(self, style_id: str) -> Optional[Style]:
        """Resolve style with inheritance chain
        
        Returns a merged style with all inherited properties
        """
        style = self.get(style_id)
        if not style:
            return None
        
        # Build inheritance chain
        chain = []
        current = style
        visited = set()
        
        while current and current.style_id not in visited:
            chain.append(current)
            visited.add(current.style_id)
            if current.based_on:
                current = self.get(current.based_on)
            else:
                break
        
        # Merge from base to derived
        merged = Style(
            style_id=style.style_id,
            name=style.name,
            type=style.type,
        )
        
        for s in reversed(chain):
            # Merge run props
            for attr_name, attr_value in vars(s.run_props).items():
                if attr_value is not None and attr_value != getattr(type(s.run_props)(attr_name).default):
                    setattr(merged.run_props, attr_name, attr_value)
            
            # Merge para props  
            for attr_name, attr_value in vars(s.para_props).items():
                if attr_value is not None and attr_value != getattr(type(s.para_props)(attr_name).default):
                    setattr(merged.para_props, attr_name, attr_value)
        
        return merged
