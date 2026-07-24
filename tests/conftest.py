"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

# Ensure src/ is importable when package is not installed
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
