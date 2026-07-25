"""Check line spacing values from the parsed document model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.config import Config

DL = Path(__file__).resolve().parent
src = DL / "chinese-into-english-traditional.docx"
cfg = Config(dpi=150)

u = Unpacker(src)
pkg = u.unpack()
dp = DocumentParser(pkg, cfg)
doc = dp.parse()

print(f"=== Document body: {len(doc.body)} elements ===")
print(f"{'#':>3} {'style':<20} {'line_rule':<8} {'spacing':>6} {'exact':>8} {'space_b':>7} {'space_a':>7} {'font_sz':>7} {'text':<40}")
print("-" * 120)
for i, elem in enumerate(doc.body):
    if not hasattr(elem, 'props') or not hasattr(elem.props, 'line_spacing'):
        print(f"{i:>3} [TABLE or non-para]")
        continue
    p = elem.props
    text = ''.join(getattr(r.text, 'text', '') or '' for r in getattr(elem, 'runs', []))[:35]
    rule = getattr(p, 'line_spacing_rule', '-') or '-'
    spc = p.line_spacing if p.line_spacing else 1.0
    exact = p.line_spacing_exact or 0
    sb = p.space_before or 0
    sa = p.space_after or 0
    fs = p.mark_font_size or 12
    style = p.style_id or ''
    print(f"{i:>3} {style:<20} {rule:<8} {spc:>6.2f} {exact:>8.1f} {sb:>7.1f} {sa:>7.1f} {fs:>7.1f} {text:<40}")
