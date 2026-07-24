"""Numbering data models"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from .enums import NumberFormat


@dataclass
class LevelDef:
    """Numbering level definition
    
    Attributes:
        level: Level index (0-8)
        format: Number format
        start: Starting number
        text: Numbering text pattern (e.g., "%1." for "1.")
        alignment: Alignment (left/center/right)
        left: Left indent
        hanging: Hanging indent
        tab_pos: Tab position after number
        font_name: Font for numbering
        font_size: Font size
    """
    level: int = 0
    format: NumberFormat = NumberFormat.DECIMAL
    start: int = 1
    text: str = "%1."
    alignment: str = "left"
    left: float = 0.0      # pt
    hanging: float = 0.0   # pt
    tab_pos: float = 0.0   # pt
    font_name: str = ""
    font_size: float = 12.0


@dataclass
class AbstractNum:
    """Abstract numbering definition
    
    Attributes:
        abstract_num_id: Abstract numbering ID
        levels: Level definitions
        name: Abstract numbering name
    """
    abstract_num_id: int = 0
    levels: Dict[int, LevelDef] = field(default_factory=dict)
    name: str = ""


@dataclass
class NumberingInstance:
    """Concrete numbering instance
    
    Attributes:
        num_id: Numbering instance ID
        abstract_num_id: Reference to abstract numbering
        level_overrides: Override levels for this instance
    """
    num_id: int = 0
    abstract_num_id: int = 0
    level_overrides: Dict[int, LevelDef] = field(default_factory=dict)


@dataclass
class NumberingTable:
    """Numbering definitions container
    
    Attributes:
        abstract_nums: Abstract numbering definitions
        instances: Numbering instances
    """
    abstract_nums: Dict[int, AbstractNum] = field(default_factory=dict)
    instances: Dict[int, NumberingInstance] = field(default_factory=dict)
    
    def get_instance(self, num_id: int) -> Optional[NumberingInstance]:
        """Get numbering instance by ID"""
        return self.instances.get(num_id)
    
    def get_abstract(self, abstract_num_id: int) -> Optional[AbstractNum]:
        """Get abstract numbering by ID"""
        return self.abstract_nums.get(abstract_num_id)
    
    def get_level(self, num_id: int, level: int) -> Optional[LevelDef]:
        """Get effective level definition
        
        Returns override if exists, otherwise from abstract numbering
        """
        instance = self.get_instance(num_id)
        if not instance:
            return None
        
        # Check for override
        if level in instance.level_overrides:
            return instance.level_overrides[level]
        
        # Get from abstract
        abstract = self.get_abstract(instance.abstract_num_id)
        if abstract and level in abstract.levels:
            return abstract.levels[level]
        
        return None
