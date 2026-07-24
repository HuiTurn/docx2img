# docx2img

Pure Python DOCX to Image rendering engine.

## Features

- Pure Python implementation (only Pillow + stdlib)
- Support `.docx` (OOXML format)
- High-fidelity rendering to PNG/JPEG/TIFF

## Installation

```bash
pip install -e .
```

## Usage

### CLI

```bash
docx2img input.docx output.png --dpi 150
```

### Python API

```python
from docx2img import convert

convert("input.docx", "output.png", dpi=150)
```

## License

MIT
