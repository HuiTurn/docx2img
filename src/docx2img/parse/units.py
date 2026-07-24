"""Unit conversion utilities for OOXML

OOXML uses various units:
- twips (twentieths of a point): 1 twip = 1/20 pt
- EMU (English Metric Units): 914400 EMU = 1 inch, 12700 EMU = 1 pt
- half-points: used in some style definitions
- points (pt): 1/72 inch
"""


class Units:
    """Unit conversion constants and methods"""
    
    # Conversion factors
    TWIPS_PER_PT = 20.0
    EMU_PER_INCH = 914400.0
    EMU_PER_PT = 12700.0
    HALF_PT_PER_PT = 2.0
    
    @staticmethod
    def twips_to_pt(twips: float) -> float:
        """Convert twips to points"""
        return twips / Units.TWIPS_PER_PT
    
    @staticmethod
    def pt_to_twips(pt: float) -> float:
        """Convert points to twips"""
        return pt * Units.TWIPS_PER_PT
    
    @staticmethod
    def emu_to_pt(emu: float) -> float:
        """Convert EMU to points"""
        return emu / Units.EMU_PER_PT
    
    @staticmethod
    def pt_to_emu(pt: float) -> float:
        """Convert points to EMU"""
        return pt * Units.EMU_PER_PT
    
    @staticmethod
    def emu_to_px(emu: float, dpi: int = 96) -> float:
        """Convert EMU to pixels"""
        inches = emu / Units.EMU_PER_INCH
        return inches * dpi
    
    @staticmethod
    def pt_to_px(pt: float, dpi: int = 96) -> float:
        """Convert points to pixels"""
        return pt * (dpi / 72.0)
    
    @staticmethod
    def half_pt_to_pt(half_pt: float) -> float:
        """Convert half-points to points"""
        return half_pt / Units.HALF_PT_PER_PT
    
    @staticmethod
    def parse_size(val, default: float = 0.0) -> float:
        """Parse a size value from XML attribute
        
        Handles both numeric strings and None
        Returns value in points if it's a twip measurement
        """
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def parse_twips(val, default: float = 0.0) -> float:
        """Parse a twips value and convert to points"""
        if val is None:
            return default
        try:
            return Units.twips_to_pt(float(val))
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def parse_emu(val, default: float = 0.0) -> float:
        """Parse an EMU value and convert to points"""
        if val is None:
            return default
        try:
            return Units.emu_to_pt(float(val))
        except (ValueError, TypeError):
            return default
