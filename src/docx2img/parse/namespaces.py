"""OOXML namespace constants"""

# WordprocessingML namespace
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Relationships namespace
R = "http://schemas.openxmlformats.org/package/2006/relationships"

# DrawingML namespace
A = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Picture namespace
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"

# Word14 namespace (for some newer features)
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"


class NS:
    """Namespace map for ElementTree"""
    
    MAP = {
        'w': W,
        'r': R,
        'a': A,
        'pic': PIC,
        'w14': W14,
    }
    
    @classmethod
    def xpath(cls, path: str) -> str:
        """Convert prefixed path for ElementTree findall
        
        Example: 'w:p/w:r' -> '{http://...}p/{http://...}r'
        """
        result = []
        for part in path.split('/'):
            if ':' in part:
                prefix, name = part.split(':', 1)
                ns = cls.MAP.get(prefix, '')
                if ns:
                    result.append(f"{{{ns}}}{name}")
                else:
                    result.append(part)
            else:
                result.append(part)
        return '/'.join(result)
