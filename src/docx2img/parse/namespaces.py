"""OOXML namespace constants"""

# WordprocessingML namespace
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Package relationships namespace
R = "http://schemas.openxmlformats.org/package/2006/relationships"

# Office document relationships (used in r:embed)
R_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# DrawingML namespace
A = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Picture namespace
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"

# Wordprocessing Drawing
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"

# Word14 namespace
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

# Office Math
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


class NS:
    """Namespace map for ElementTree"""

    W = W
    R = R
    R_DOC = R_DOC
    A = A
    PIC = PIC
    WP = WP
    W14 = W14
    M = M

    MAP = {
        "w": W,
        "r": R_DOC,
        "a": A,
        "pic": PIC,
        "wp": WP,
        "w14": W14,
        "m": M,
    }

    @classmethod
    def xpath(cls, path: str) -> str:
        result = []
        for part in path.split("/"):
            if ":" in part:
                prefix, name = part.split(":", 1)
                ns = cls.MAP.get(prefix, "")
                if ns:
                    result.append(f"{{{ns}}}{name}")
                else:
                    result.append(part)
            else:
                result.append(part)
        return "/".join(result)
