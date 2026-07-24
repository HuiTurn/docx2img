"""Color utilities"""

from typing import Tuple


def parse_color(val: str) -> Tuple[int, int, int]:
    """Parse hex color string to RGB tuple
    
    Args:
        val: Color value in hex format (e.g., "FF0000" or "#FF0000")
        
    Returns:
        RGB tuple (R, G, B)
    """
    val = val.lstrip('#')
    if len(val) == 6:
        try:
            r = int(val[0:2], 16)
            g = int(val[2:4], 16)
            b = int(val[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass
    return (0, 0, 0)
