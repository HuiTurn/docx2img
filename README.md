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

The repository also includes an optional LibreOffice-based visual-regression
workflow for complex real-world documents:

```bash
python scripts/run_visual_regression.py
```

Its corpus lives under `testdata/regression/` and reference pages under
`tests/golden/libreoffice/`. Regenerate references only when intentionally
updating the baseline:

```bash
python scripts/generate_lo_golden.py --force
```

Golden generation requires LibreOffice and Poppler's `pdftoppm`; neither is a
runtime dependency. The external corpus and optional metric-compatible fonts
must have their redistribution licences reviewed before publishing them.

## License

MIT
