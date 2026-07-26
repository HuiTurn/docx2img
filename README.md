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
Current office golden cases: `basic_text`, `date_field`, `drawingml_text`,
`page_break`, `shape_fill`. Word COM / Poppler `pdftoppm` are **dev-only**;
`src/docx2img` must never import Office. First office golden introduction
records baseline metrics without a global MAE/SSIM pass threshold; later
slices must improve the target case and not regress existing office goldens.
Paragraph `auto` line spacing follows Word (`natural × line/240`), not the
older LibreOffice-oriented floor-only formula.

DATE fields in headers and footers no longer read the system clock.
`Config.reference_datetime` supplies the fixed evaluation time and defaults
to `2000-01-01`, so identical input and configuration stay deterministic
across calendar days. The `date_field` Word 16.0 golden records its reference
time in metadata and reuses it for both renderer passes (150 dpi, 1/1 page,
exact size): MAE 0.308, RMSE 8.215, changed pixels 0.159%, SSIM 0.982710.
Callers that want “today” must pass that time explicitly.

Manual page breaks (`w:br w:type="page"`) preserve the invisible paragraph
mark and its trailing paragraph spacing during page-fit checks. When that
break-only paragraph crosses the page boundary, it moves to a blank
intermediate page before the break starts the following content on the next
page. The `page_break` office case now matches Word 16.0 at 3/3 pages and
identical page sizes (150 dpi): blank page 2 is pixel-identical, mean MAE
0.565, SSIM 0.955725, and changed-pixel ratio 0.284%. No global visual pass
threshold is implied.

Standalone DrawingML text boxes and autoshapes (`wps:wsp`/`w:txbxContent`
inside `wp:anchor`) now keep their `a:solidFill` background and `a:ln` outline
instead of rendering as bare text: the `shape_fill` office case quantifies
this (Word 16.0, 150 dpi) at MAE ≈ 0.8, SSIM ≈ 0.97, diff% ≈ 0.6%.

Native DrawingML shape text (`a:sp/a:txSp/a:txBody`) is no longer silently
dropped. The basic subset maps `a:p`, `a:r`, cached `a:fld` text and `a:br`
into the existing paragraph/run model; common run font, size, emphasis and
sRGB color properties plus `a:bodyPr` insets/vertical anchoring are retained.
Unsupported visible child nodes emit `drawingml_txbody_unsupported`; cached
fields and unsupported theme colors emit their own stable approximation
warnings.
The code-generated `drawingml_text` Word 16.0 golden (150 dpi, 1/1 page,
identical size, deterministic output) improved from the pre-change MAE 0.631,
RMSE 11.400, changed pixels 0.339%, SSIM 0.652430 to MAE 0.554, RMSE 10.552,
changed pixels 0.317%, SSIM 0.889565. Bullets, autofit, vertical/warped text,
theme-color resolution and arbitrary DrawingML effects remain unsupported or
approximate; this is a basic subset, not complete DrawingML text fidelity.

LibreOffice corpus under `testdata/regression/sample-files-complex/` and
optional metric-compatible fonts need redistribution licence review before
publishing.

## License

MIT
