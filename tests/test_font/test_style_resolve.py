"""Font style resolution tests (Windows Times New Roman bold/italic)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from docx2img.config import Config
from docx2img.font.manager import FontManager

WIN_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
TIMESBD = WIN_FONTS / "timesbd.ttf"
TIMESI = WIN_FONTS / "timesi.ttf"
TIMESBI = WIN_FONTS / "timesbi.ttf"


@pytest.mark.skipif(sys.platform != "win32" or not TIMESBD.exists(),
                    reason="Windows timesbd.ttf required")
def test_times_new_roman_bold_resolves_to_timesbd_not_simhei():
    """Bold TNR must not fall through to simhei via global bold style_keys."""
    fm = FontManager(Config(dpi=150))
    font = fm.get_font("Times New Roman", 24.0, bold=True, italic=False)
    path = Path(getattr(font, "path", "")).name.lower()
    assert path == "timesbd.ttf", f"got {path}"


@pytest.mark.skipif(sys.platform != "win32" or not TIMESI.exists(),
                    reason="Windows timesi.ttf required")
def test_times_new_roman_italic_resolves_to_timesi():
    fm = FontManager(Config(dpi=150))
    font = fm.get_font("Times New Roman", 24.0, bold=False, italic=True)
    path = Path(getattr(font, "path", "")).name.lower()
    assert path == "timesi.ttf", f"got {path}"


@pytest.mark.skipif(sys.platform != "win32" or not TIMESBI.exists(),
                    reason="Windows timesbi.ttf required")
def test_times_new_roman_bold_italic_resolves_to_timesbi():
    fm = FontManager(Config(dpi=150))
    font = fm.get_font("Times New Roman", 24.0, bold=True, italic=True)
    path = Path(getattr(font, "path", "")).name.lower()
    assert path == "timesbi.ttf", f"got {path}"
