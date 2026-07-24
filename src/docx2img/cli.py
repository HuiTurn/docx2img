"""Command-line interface for docx2img"""

import argparse
import sys
from pathlib import Path

from .api import convert


def main():
    parser = argparse.ArgumentParser(
        description="Convert DOCX to PNG/JPEG/TIFF images"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input .docx file"
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output image file (PNG/JPEG/TIFF)"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Output DPI (default: 150)"
    )
    parser.add_argument(
        "--format",
        choices=["PNG", "JPEG", "TIFF"],
        default=None,
        help="Output format (auto-detected from extension if not provided)"
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    try:
        convert(args.input, args.output, dpi=args.dpi, format=args.format)
        print(f"Successfully converted {args.input} to {args.output}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
