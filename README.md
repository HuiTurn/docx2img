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

## License

MIT
