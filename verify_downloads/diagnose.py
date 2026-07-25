"""Diagnose which chars become tofu and which font was chosen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docx2img.api import convert_to_images
from docx2img.config import Config
from docx2img.font.manager import FontManager

DL = Path(__file__).resolve().parent
src = DL / "chinese-into-english-traditional.docx"
cfg = Config(dpi=150)

# Convert and capture font manager state
fm = FontManager(cfg)
# Monkey-patch to capture the fm instance used during conversion
from docx2img.unpack import unpacker as _up
from docx2img.parse.document import DocumentParser
from docx2img.layout.engine import LayoutEngine
from docx2img.render.canvas import RenderCanvas

u = _up.Unpacker(src)
pkg = u.unpack()
dp = DocumentParser(pkg, cfg)
doc = dp.parse()

# Replace font manager in config so we can inspect it
cfg._font_manager = fm
le = LayoutEngine(doc, cfg)
pages = le.layout()

# Check missing log
print("=== MISSING CHAR LOG (tofu candidates) ===")
print(f"Total missing entries: {len(fm._missing_log)}")
seen = set()
for ch, req, actual, fpath in fm._missing_log:
    if ch not in seen:
        seen.add(ch)
        print(f"  U+{ord(ch):04X} '{ch}'  requested={req!r}  actual={actual!r}  font={Path(fpath).name if fpath else 'DEFAULT'}")

# Also scan all text runs for CJK coverage
print("\n=== FONT COVERAGE SAMPLE ===")
cjk_samples = []
for page in pages:
    for block in page.blocks:
        for run in getattr(block, 'runs', []):
            t = getattr(run, 'text', '')
            for ch in t:
                if 0x4E00 <= ord(ch) <= 0x9FFF:
                    cjk_samples.append(ch)

if cjk_samples:
    # Test first 20 unique CJK chars against PingFang
    uniq = list(dict.fromkeys(cjk_samples))[:30]
    pf_path = "/System/Library/Fonts/PingFang.ttc"
    try:
        from PIL import ImageFont
        pf = ImageFont.truetype(pf_path, 12)
        print(f"PingFang.ttc exists: YES")
        for ch in uniq:
            has = fm.font_has_char(pf, ch)
            print(f"  U+{ord(ch):04X} '{ch}'  in PingFang: {has}")
    except Exception as e:
        print(f"PingFang.ttc error: {e}")
