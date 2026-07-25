"""Deeper diagnose: render traditional doc and inspect actual glyph coverage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import ImageFont

# 1. Check what fonts are actually resolved for SimSun on this macOS
from docx2img.config import Config
from docx2img.font.manager import FontManager

cfg = Config(dpi=150)
fm = FontManager(cfg)

print("=== Font paths discovered (sample) ===")
# Show some key font resolutions
for name in ["SimSun", "simsun", "Microsoft YaHei", "msyh", "PingFang", "STHeiti"]:
    try:
        f = fm.get_font(name, 12)
        p = getattr(f, "path", "N/A")
        print(f"  {name!r} -> {Path(p).name if p != 'N/A' else 'DEFAULT'}")
    except Exception as e:
        print(f"  {name!r} -> ERROR: {e}")

# 2. Extract raw text from the traditional docx and test each CJK char against the font that would be used
import zipfile, re
docx_path = Path(__file__).resolve().parent / "chinese-into-english-traditional.docx"
with zipfile.ZipFile(docx_path) as zf:
    xml = zf.read("word/document.xml").decode("utf-8")

# Strip tags to get text
text = re.sub(r"<[^>]+>", " ", xml)
text = " ".join(text.split())

cjk_chars = [ch for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF]
print(f"\n=== Traditional CJK chars in document: {len(cjk_chars)} unique ===")
uniq_cjk = list(dict.fromkeys(cjk_chars))

# Test each against the font that get_font_for_char would pick
tofu = []
ok = []
for ch in uniq_cjk[:50]:  # first 50 unique
    # Simulate what the renderer does
    font = fm.get_font_for_char(ch, None, 12)
    fpath = getattr(font, "path", "")
    has = fm.font_has_char(font, ch)
    fname = Path(fpath).name if fpath else "(default)"
    status = "OK" if has else "TOFU"
    if not has:
        tofu.append((ch, fname))
    else:
        ok.append((ch, fname))

print(f"  OK (first 10): {[(c, f) for c, f in ok[:10]]}")
print(f"  TOFU: {len(tofu)} chars")
for c, f in tofu[:20]:
    print(f"    U+{ord(c):04X} '{c}'  font={f}")

# 3. Also test PingFang directly
print("\n=== Direct PingFang.ttc test ===")
pf = "/System/Library/Fonts/PingFang.ttc"
try:
    pf_font = ImageFont.truetype(pf, 12)
    pf_tofu = []
    for ch in uniq_cjk:
        if not fm.font_has_char(pf_font, ch):
            pf_tofu.append(ch)
    print(f"PingFang.ttc missing {len(pf_tofu)} of {len(uniq_cjk)} CJK chars")
    if pf_tofu:
        print(f"  Missing: {''.join(pf_tofu[:20])}")
except Exception as e:
    print(f"PingFang error: {e}")
