"""Detailed layout diagnostic: what goes on each page and why."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.layout.engine import LayoutEngine
from docx2img.config import Config

DL = Path(__file__).resolve().parent
src = DL / "chinese-into-english-traditional.docx"
cfg = Config(dpi=150)

u = Unpacker(src)
pkg = u.unpack()
dp = DocumentParser(pkg, cfg)
doc = dp.parse()

print(f"=== Document Info ===")
print(f"  Sections: {len(doc.sections)}")
for i, sec in enumerate(doc.sections):
    print(f"  Section {i}: page_w={sec.page_w}pt page_h={sec.page_h}pt")
    print(f"    margins: t={sec.margin_top} b={sec.margin_bottom} l={sec.margin_left} r={sec.margin_right}")
    print(f"    content_h: {sec.page_h - sec.margin_top - sec.margin_bottom}pt")

le = LayoutEngine(doc, cfg)
pages = le.layout()

print(f"\n=== Layout Result: {len(pages)} pages ===")
for pi, page in enumerate(pages):
    print(f"\n--- Page {pi+1} ---")
    print(f"  blocks: {len(page.blocks)}")
    total_h = 0
    for bi, block in enumerate(page.blocks):
        btype = type(block).__name__
        h = getattr(block, 'height', '?')
        y = getattr(block, 'y', '?')
        # Get text preview
        text_preview = ""
        if hasattr(block, 'text') and block.text:
            text_preview = block.text[:60].replace('\n', ' ')
        elif hasattr(block, 'runs'):
            texts = [getattr(r, 'text', '') or '' for r in getattr(block, 'runs', [])]
            text_preview = ''.join(texts)[:60].replace('\n', ' ')
        elif hasattr(block, 'paragraph'):
            p = block.paragraph
            if p:
                texts = [getattr(r, 'text', '') or '' for r in getattr(p, 'runs', [])]
                text_preview = ''.join(texts)[:60].replace('\n', ' ')
        print(f"  [{bi}] {btype} y={y} h={h} | {text_preview}")
        if isinstance(h, (int, float)):
            total_h += h
    print(f"  total_block_height: {total_h}pt")

# Also check: how much text content exists vs what fits
print(f"\n=== Content volume check ===")
total_chars = 0
all_paras = []
for block in pages[0].blocks if pages else []:
    if hasattr(block, 'runs'):
        for r in block.runs:
            t = getattr(r, 'text', '')
            if t:
                total_chars += len(t)
                all_paras.append(t)

# Count from document model instead
doc_chars = 0
for para in doc.paragraphs:
    for run in para.runs:
        if run.text:
            doc_chars += len(run.text)
print(f"  Total chars in document model: {doc_chars}")
print(f"  Chars on page 1 only: ~{sum(len(getattr(b,'text','') or '') for b in pages[0].blocks if hasattr(b,'text'))}")
