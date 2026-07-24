"""Python API for docx2img"""

from typing import List, Union, Optional
from pathlib import Path

from .config import Config
from .unpack.unpacker import Unpacker
from .parse.document import DocumentParser
from .layout.engine import LayoutEngine
from .render.canvas import RenderCanvas


def convert_to_images(
    docx_path: Union[str, Path],
    config: Optional[Config] = None,
) -> List:
    """Convert DOCX to list of PIL Image objects
    
    Args:
        docx_path: Path to .docx file
        config: Configuration object
        
    Returns:
        List of PIL.Image objects (one per page)
    """
    if config is None:
        config = Config()
    
    docx_path = Path(docx_path)
    
    # Step 1: Unpack ZIP
    unpacker = Unpacker(docx_path)
    package = unpacker.unpack()
    
    # Step 2: Parse XML to IR
    parser = DocumentParser(package, config)
    document_model = parser.parse()
    
    # Step 3: Layout
    layout_engine = LayoutEngine(document_model, config)
    pages = layout_engine.layout()
    
    # Step 4: Render
    canvas = RenderCanvas(config)
    images = canvas.render_pages(pages)
    
    return images


def convert(
    docx_path: Union[str, Path],
    output_path: Union[str, Path],
    dpi: int = 150,
    format: Optional[str] = None,
) -> None:
    """Convert DOCX to image file(s)
    
    Args:
        docx_path: Path to .docx file
        output_path: Output path (PNG/JPEG/TIFF)
        dpi: Output DPI
        format: Output format (auto-detected from extension if not provided)
    """
    from pathlib import Path
    
    docx_path = Path(docx_path)
    output_path = Path(output_path)
    
    config = Config(dpi=dpi)
    images = convert_to_images(docx_path, config)
    
    # Determine format
    if format is None:
        ext = output_path.suffix.lower()
        format_map = {
            '.png': 'PNG',
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG',
            '.tiff': 'TIFF',
            '.tif': 'TIFF',
        }
        format = format_map.get(ext, 'PNG')
    
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save images
    if len(images) == 1:
        images[0].save(str(output_path), format=format)
    else:
        # Multi-page: save as TIFF or numbered files
        if format == 'TIFF':
            images[0].save(
                str(output_path),
                format=format,
                save_all=True,
                append_images=images[1:]
            )
        else:
            # Save as numbered files
            stem = output_path.stem
            suffix = output_path.suffix
            parent = output_path.parent

            for i, img in enumerate(images):
                num_path = parent / f"{stem}_{i+1}{suffix}"
                img.save(str(num_path), format=format)
