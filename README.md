# docx2img

A pure Python `.docx` → image rendering engine (Pillow + standard library).

## Progress

| Phase | Status |
|-------|--------|
| **P0** Basic text | ✅ |
| **P1** Style system | ✅ |
| **P2** Tables (merge / nested / borders) | ✅ |
| **P3** Inline images + multi-section / columns | ✅ |
| **P4** Headers & footers + page numbers | ✅ |
| **P5** List numbering | ✅ |
| **P6** Advanced layout (justify / tab stops / float wrap / text boxes) | ✅ |
| **P7** Math (OMML fractions / super-subscripts / radicals / summations) | ✅ basic |

See [`docs/technical_design.md`](docs/technical_design.md).

## Installation

```bash
pip install -e .
```

## Usage

```bash
docx2img input.docx output.png --dpi 150
```

```python
from docx2img import convert, convert_to_images
convert("input.docx", "output.png", dpi=150)
```

## Testing

```bash
python -m pytest tests/ -v
```

### Visual regression providers

Visual regression is provider-based. **Microsoft Word is the layout/visual
authority for fidelity work**; LibreOffice remains an optional diagnostic aid
and is **not** evidence of Word fidelity.

| Provider | Golden root | Generate | Compare |
|----------|-------------|----------|---------|
| `office` (Word COM → PDF → PNG) | `tests/golden/office/` | `python scripts/generate_office_golden.py` | `python scripts/run_visual_regression.py --provider office` |
| `libreoffice` (diagnostic) | `tests/golden/libreoffice/` | `python scripts/generate_lo_golden.py` | `python scripts/run_visual_regression.py --provider libreoffice` |

Office corpus uses code-generated minimal fixtures under
`testdata/regression/office-min/` (no third-party licensed DOCX required).
Current office golden cases: `basic_text`, `page_break`, `shape_fill`. Word
COM / Poppler `pdftoppm` are **dev-only**; `src/docx2img` must never import
Office. First office golden introduction records baseline metrics without a
global MAE/SSIM pass threshold; later slices must improve the target case and
not regress existing office goldens. Paragraph `auto` line spacing follows
Word (`natural × line/240`), not the older LibreOffice-oriented floor-only
formula.

Manual page breaks (`w:br w:type="page"`) preserve the invisible paragraph
mark and its trailing paragraph spacing during page-fit checks. When that
break-only paragraph crosses the page boundary, it moves to a blank
intermediate page before the break starts the following content on the next
page. The `page_break` office case now matches Word 16.0 at 3/3 pages and
identical page sizes (150 dpi): blank page 2 is pixel-identical, mean MAE
0.562, SSIM 0.957358, and changed-pixel ratio 0.283%. No global visual pass
threshold is implied.

Standalone DrawingML text boxes and autoshapes (`wps:wsp`/`w:txbxContent`
inside `wp:anchor`) now keep their `a:solidFill` background and `a:ln` outline
instead of rendering as bare text: the `shape_fill` office case quantifies
this (Word 16.0, 150 dpi) at MAE ≈ 0.8, SSIM ≈ 0.97, diff% ≈ 0.6%.

LibreOffice corpus under `testdata/regression/sample-files-complex/` and
optional metric-compatible fonts need redistribution licence review before
publishing.

## License

MIT
