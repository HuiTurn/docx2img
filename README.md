# docx2img

A pure Python `.docx` → image rendering engine. No Microsoft Office or LibreOffice required.

## Features

- Paragraphs, runs, fonts, colors, bold/italic/underline/strikethrough
- Full style inheritance and theme resolution
- Tables with merged cells, nested tables, and borders
- Inline images and floating images with text wrap
- Multi-section documents, landscape pages, multi-column layout
- Headers, footers, and page numbers
- Ordered / unordered lists with numbering
- Justified text, tab stops, text boxes
- OMML math (fractions, super/subscripts, radicals, accents, bars, limits, equation arrays)
- Footnotes and endnotes with continuation pages
- DrawingML shapes and text boxes

## Installation

```bash
pip install docx2img
```

## Usage

### CLI

```bash
docx2img input.docx output.png --dpi 150
```

### Python API

```python
from docx2img import convert, convert_to_images

# Single image (first page or stitched)
convert("input.docx", "output.png", dpi=150)

# Per-page images
pages = convert_to_images("input.docx", dpi=150)
for i, img in enumerate(pages):
    img.save(f"page_{i}.png")
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

See [`docs/technical_design.md`](docs/technical_design.md) for architecture details.

## License

MIT
