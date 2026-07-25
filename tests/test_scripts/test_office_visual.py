"""Tests for Word/office visual-regression helpers (no Office required for unit tests)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


visual_compare = _load("visual_compare", SCRIPTS / "visual_compare.py")
generate_office = _load(
    "generate_office_golden", SCRIPTS / "generate_office_golden.py"
)


def test_compare_identical_pages_zero_error(tmp_path):
    img = Image.new("RGB", (120, 80), (255, 255, 255))
    img.putpixel((10, 10), (0, 0, 0))
    m = visual_compare.compare_pages_strict(
        img,
        img.copy(),
        abs_diff_path=tmp_path / "abs.png",
        diff_path=tmp_path / "diff.png",
        overlay_path=tmp_path / "overlay.png",
    )
    assert m["size_match"] is True
    assert m["hard_size_mismatch"] is False
    assert m["mae"] == 0.0
    assert m["rmse"] == 0.0
    assert m["diff_pixel_ratio"] == 0.0
    assert m["ssim"] == pytest.approx(1.0, abs=1e-4)
    assert (tmp_path / "abs.png").exists()
    assert (tmp_path / "diff.png").exists()
    assert (tmp_path / "overlay.png").exists()


def test_compare_size_mismatch_is_hard_diff_without_resize(tmp_path):
    a = Image.new("RGB", (100, 80), (255, 255, 255))
    b = Image.new("RGB", (90, 80), (255, 255, 255))
    m = visual_compare.compare_pages_strict(
        a, b, overlay_path=tmp_path / "overlay.png"
    )
    assert m["hard_size_mismatch"] is True
    assert m["mae"] is None
    assert m["rmse"] is None
    assert m["diff_pixel_ratio"] is None
    assert m["ssim"] is None


def test_compare_detects_changed_pixels():
    a = Image.new("RGB", (40, 40), (255, 255, 255))
    b = Image.new("RGB", (40, 40), (255, 255, 255))
    for y in range(40):
        for x in range(40):
            b.putpixel((x, y), (0, 0, 0))
    m = visual_compare.compare_pages_strict(a, b)
    assert m["mae"] is not None and m["mae"] > 100
    assert m["diff_pixel_ratio"] == 1.0


def test_office_cases_and_paths_isolated_from_libreoffice():
    assert "libreoffice" not in str(generate_office.GOLDEN_ROOT).replace("\\", "/")
    assert generate_office.GOLDEN_ROOT.name == "office"
    assert "basic_text" in generate_office.CASES
    assert "page_break" in generate_office.CASES
    assert "shape_fill" in generate_office.CASES


def test_page_break_fixture_is_deterministic(tmp_path):
    """The page_break office fixture must hash-stably regenerate."""
    from fixtures.gen_fixtures import make_page_break

    a = make_page_break(tmp_path / "page_break.docx")
    h1 = generate_office.sha256(a)
    b = make_page_break(tmp_path / "page_break.docx")
    h2 = generate_office.sha256(b)
    assert h1 == h2
    assert a.stat().st_size > 1000


def test_shape_fill_fixture_is_deterministic(tmp_path):
    """The shape_fill office fixture must hash-stably regenerate."""
    from fixtures.gen_fixtures import make_shape_fill

    a = make_shape_fill(tmp_path / "shape_fill.docx")
    h1 = generate_office.sha256(a)
    b = make_shape_fill(tmp_path / "shape_fill.docx")
    h2 = generate_office.sha256(b)
    assert h1 == h2
    assert a.stat().st_size > 1000


def test_ensure_fixture_writes_minimal_docx(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_office, "CORPUS", tmp_path)
    docx = generate_office.ensure_fixture("basic_text")
    assert docx.exists()
    assert docx.stat().st_size > 1000
    # Regenerating must be deterministic at the OOXML builder level for hash
    # stability of the committed fixture path.
    h1 = generate_office.sha256(docx)
    docx2 = generate_office.ensure_fixture("basic_text")
    h2 = generate_office.sha256(docx2)
    assert h1 == h2


def _word_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401
        import pythoncom

        pythoncom.CoInitialize()
        word = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            _ = word.Version
            return True
        finally:
            if word is not None:
                try:
                    word.Quit()
                except Exception:
                    pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
    except Exception:
        return False


@pytest.mark.skipif(not _word_available(), reason="Word COM not available")
def test_word_export_pdf_roundtrip(tmp_path):
    docx = generate_office.ensure_fixture("basic_text")
    # Point corpus at the real path used by ensure_fixture for this process.
    pdf = tmp_path / "out.pdf"
    version = generate_office.word_export_pdf(docx, pdf)
    assert pdf.exists() and pdf.stat().st_size > 100
    assert version  # e.g. "16.0"
