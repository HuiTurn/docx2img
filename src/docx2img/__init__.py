"""docx2img - Pure Python DOCX to Image rendering engine"""

__version__ = "0.1.0"

from .api import convert, convert_to_images
from .config import Config

__all__ = ["convert", "convert_to_images", "Config"]
