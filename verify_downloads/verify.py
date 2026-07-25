import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docx2img.api import convert_to_images
from docx2img.config import Config

DL = Path(__file__).resolve().parent
OUT = DL / "output"
OUT.mkdir(exist_ok=True)

files = [
    "chinese-into-english-simplified.docx",
    "chinese-into-english-traditional.docx",
]

import re

def count_scripts_in_pages(pages):
    """Count CJK vs Latin chars from rendered text spans across pages."""
    cjk = 0
    latin = 0
    for page in pages:
        for block in page.blocks:
            text = getattr(block, "text", None)
            if text is None and hasattr(block, "runs"):
                text = "".join(getattr(r, "text", "") or "" for r in block.runs)
            if not text:
                continue
            cjk += len(re.findall(r"[\u4e00-\u9fff]", text))
            latin += len(re.findall(r"[A-Za-z]", text))
    return cjk, latin

for fname in files:
    src = DL / fname
    print(f"\n=== {fname} ===")
    cfg = Config(dpi=150)
    try:
        images = convert_to_images(src, cfg)
    except Exception as e:
        print(f"  ERROR during conversion: {e!r}")
        import traceback; traceback.print_exc()
        continue
    print(f"  pages: {len(images)}")
    # Save
    base = fname.rsplit(".", 1)[0]
    for i, img in enumerate(images):
        p = OUT / f"{base}_{i+1}.png"
        img.save(str(p), format="PNG")
    # Non-blank check
    from PIL import Image
    total_nonwhite = 0
    for img in images:
        gray = img.convert("L")
        total_nonwhite += (gray.point(lambda x: 255 if x < 250 else 0)).getextrema() and 0
        extrema = gray.getextrema()
        # count non-white pixels
        hist = gray.histogram()
        nonwhite = sum(hist[0:250])
        total_nonwhite += nonwhite
    print(f"  non-white pixels (total): {total_nonwhite}")

print("\nDone.")
