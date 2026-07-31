"""Unit tests for FontManager glyph-coverage substitution."""

import shutil
from pathlib import Path

import pytest
from PIL import ImageFont
from fontTools.ttLib import TTFont

from docx2img.config import Config
from docx2img.font.manager import FontManager

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS = ROOT / "fonts"
CARLITO = FONTS / "Carlito-Regular.ttf"
CALADEA = FONTS / "Caladea-Regular.ttf"

pytestmark = pytest.mark.skipif(
    not (CARLITO.exists() and CALADEA.exists()),
    reason="optional Carlito/Caladea regression fonts are not available",
)


def _cmap(path: Path) -> set:
    font = TTFont(str(path), lazy=True)
    try:
        return set(font.getBestCmap().keys())
    finally:
        font.close()


@pytest.fixture
def manager():
    return FontManager(Config(dpi=150))


def test_glyph_coverage_scan_finds_covering_font(manager):
    """When no preferred family covers a codepoint, the last-resort scan must
    locate any discovered font whose cmap contains the glyph."""
    carlito_only = _cmap(CARLITO) - _cmap(CALADEA)
    # pick a stable, printable codepoint present in Carlito but not Caladea
    cp = min(c for c in carlito_only if 0x2010 <= c <= 0x2027)
    ch = chr(cp)

    # Restrict discovery to the two bundled faces so the result is deterministic.
    manager._font_paths = {
        "caladea": str(CALADEA),
        "carlito": str(CARLITO),
    }
    manager._char_font_cache.clear()

    font = manager._find_font_covering(ch, 22.0, bold=False, italic=False)
    assert font is not None
    assert manager.font_has_char(font, ch)
    assert Path(getattr(font, "path", "")).name == "Carlito-Regular.ttf"


def test_glyph_coverage_scan_returns_none_when_uncovered(manager):
    """A codepoint absent from every discovered font yields no substitute."""
    # U+E000 is a Private Use Area codepoint not present in the bundled faces.
    manager._font_paths = {
        "caladea": str(CALADEA),
        "carlito": str(CARLITO),
    }
    manager._char_font_cache.clear()
    assert 0xE000 not in _cmap(CARLITO)
    assert manager._find_font_covering("\ue000", 22.0, False, False) is None


def test_scan_result_is_cached(manager):
    """Repeated lookups for the same codepoint must reuse the cached path."""
    manager._font_paths = {"carlito": str(CARLITO)}
    manager._char_font_cache.clear()
    manager._find_font_covering("A", 22.0, False, False)
    assert ord("A") in manager._char_font_cache
    assert manager._char_font_cache[ord("A")] == str(CARLITO)


def test_get_font_for_char_logs_scan_fallback(manager):
    """get_font_for_char records a fallback (not unresolved) when the scan
    rescues a symbol none of the preferred families covers."""
    carlito_only = _cmap(CARLITO) - _cmap(CALADEA)
    cp = min(c for c in carlito_only if 0x2010 <= c <= 0x2027)
    ch = chr(cp)

    class _Props:
        font_ascii = "Caladea"
        font_h_ansi = "Caladea"
        font_east_asia = "Caladea"
        bold = False
        italic = False

    # Only Caladea (lacks the char) + Carlito (has it) are discoverable.
    manager._font_paths = {"caladea": str(CALADEA), "carlito": str(CARLITO)}
    manager._char_font_cache.clear()
    manager.clear_missing_log()

    font = manager.get_font_for_char(ch, _Props(), 22.0)
    assert manager.font_has_char(font, ch)
    # exactly one log entry, marked as a scan fallback (used is not None)
    assert len(manager._missing_log) == 1
    logged_ch, requested, used, _path = manager._missing_log[0]
    assert logged_ch == ch
    assert used is not None  # counts as fallback, not unresolved


def test_metrics_use_the_loaded_platform_fallback(manager, monkeypatch):
    """Missing family metrics come from the font actually chosen to render."""
    loaded = ImageFont.truetype(str(CARLITO), 22)
    monkeypatch.setattr(manager, "_resolve_family_path", lambda *args: None)
    monkeypatch.setattr(manager, "get_font", lambda *args: loaded)

    ascent, descent, line_gap = manager.get_font_metrics(
        "Unavailable Family", 22.0
    )

    tt = TTFont(str(CARLITO), lazy=True)
    try:
        scale = 22.0 / tt["head"].unitsPerEm
        assert ascent == pytest.approx(tt["hhea"].ascender * scale)
        assert descent == pytest.approx(abs(tt["hhea"].descender) * scale)
        assert line_gap == pytest.approx(tt["hhea"].lineGap * scale)
    finally:
        tt.close()


def test_exact_stem_beats_filename_alias_in_same_discovery_tier(tmp_path):
    """An exact family file must replace an earlier filename-derived alias."""
    alias_path = tmp_path / "times.ttf"
    exact_path = tmp_path / "Times New Roman.ttf"
    shutil.copyfile(CARLITO, alias_path)
    shutil.copyfile(CALADEA, exact_path)

    manager = FontManager(
        Config(font_paths=[str(alias_path), str(exact_path)])
    )

    assert manager._font_paths["times new roman"] == str(exact_path)
