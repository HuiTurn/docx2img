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
- Word-style pagination with widow/orphan control and cross-page tables
- CJK line breaking, punctuation hanging, justification, and document-grid layout
- Justified text, tab stops, text boxes
- OMML math (fractions, super/subscripts, radicals, accents, bars, limits, equation arrays)
- Footnotes and endnotes with continuation pages
- DrawingML and legacy VML shapes, text boxes, flowchart nodes, and arrows

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
from docx2img import Config, convert, convert_to_images

# A multi-page document is saved as output_1.png, output_2.png, ...
convert("input.docx", "output.png", dpi=150)

# Per-page images
pages = convert_to_images("input.docx", Config(dpi=150))
for i, img in enumerate(pages):
    img.save(f"page_{i + 1}.png")
```

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

See [`docs/technical_design.md`](docs/technical_design.md) for architecture details.

## License

MIT
