#!/usr/bin/env python3
"""Generate Microsoft Word (office) golden reference PNGs.

Pipeline per DOCX:
  1. Copy fixture to a temp path (never open the original for write).
  2. Word.Application via DispatchEx → ExportAsFixedFormat PDF.
  3. pdftoppm -png -r <dpi> → tests/golden/office/<case>/page-%03d.png
  4. Write metadata.json (Word version, input SHA-256, DPI, sizes...).

Word/Office is ONLY used offline here; it is NOT a runtime dependency of
docx2img. Goldens live under tests/golden/office/ and must never be mixed
with tests/golden/libreoffice/.

Usage:
  python scripts/generate_office_golden.py [--dpi 150] [--case basic_text] [--force]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))

CORPUS = REPO / "testdata" / "regression" / "office-min"
GOLDEN_ROOT = REPO / "tests" / "golden" / "office"

# Minimal code-generated fixtures (no external licensed corpus required).
CASES = {
    "basic_text": "basic_text.docx",
    "date_field": "date_field.docx",
    "drawingml_text": "drawingml_text.docx",
    "page_break": "page_break.docx",
    "shape_fill": "shape_fill.docx",
}

# Word COM constants
WD_EXPORT_FORMAT_PDF = 17
WD_ALERTS_NONE = 0
MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3
WD_EXPORT_OPTIMIZE_FOR_PRINT = 0
WD_EXPORT_CREATE_NO_BOOKMARKS = 0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_pdftoppm() -> str:
    path = shutil.which("pdftoppm")
    if not path:
        raise SystemExit("ERROR: pdftoppm not found. Install Poppler first.")
    return path


def tool_version(cmd: list) -> str:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
        return (proc.stdout or proc.stderr).strip().splitlines()[0]
    except Exception as exc:  # pragma: no cover
        return f"unknown ({exc})"


def ensure_fixture(case: str) -> Path:
    """Ensure the minimal office-min fixture exists (regenerate from builder)."""
    from fixtures.gen_fixtures import (
        make_basic_text,
        make_date_field,
        make_drawingml_text,
        make_page_break,
        make_shape_fill,
    )

    builders = {
        "basic_text": make_basic_text,
        "date_field": make_date_field,
        "drawingml_text": make_drawingml_text,
        "page_break": make_page_break,
        "shape_fill": make_shape_fill,
    }
    CORPUS.mkdir(parents=True, exist_ok=True)
    dest = CORPUS / CASES[case]
    builders[case](dest)
    return dest


def word_export_pdf(docx: Path, pdf_path: Path) -> str:
    """Export DOCX → PDF via Word COM. Returns Word version string.

    Opens a temporary read-only copy only. Never saves the fixture.
    """
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "ERROR: pywin32 is required for Word golden generation on Windows."
        ) from exc

    pythoncom.CoInitialize()
    word = None
    doc = None
    version = "unknown"
    tmp_copy = pdf_path.parent / (docx.stem + "-readonly-copy.docx")
    shutil.copy2(docx, tmp_copy)
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = WD_ALERTS_NONE
        try:
            word.AutomationSecurity = MSO_AUTOMATION_SECURITY_FORCE_DISABLE
        except Exception:
            pass
        # Disable automatic link updates where the property exists.
        try:
            word.Options.UpdateLinksAtOpen = False
        except Exception:
            pass
        try:
            word.Options.ConfirmConversions = False
        except Exception:
            pass

        version = str(word.Version)
        # ReadOnly open of the temp copy — never the corpus file itself.
        doc = word.Documents.Open(
            str(tmp_copy),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            NoEncodingDialog=True,
        )
        # Avoid field / TOC refresh mutating layout unexpectedly.
        try:
            doc.Fields.Update()
        except Exception:
            pass

        # Minimal ExportAsFixedFormat flags — avoid build-specific optional kwargs.
        doc.ExportAsFixedFormat(
            OutputFileName=str(pdf_path),
            ExportFormat=WD_EXPORT_FORMAT_PDF,
            OpenAfterExport=False,
            OptimizeFor=WD_EXPORT_OPTIMIZE_FOR_PRINT,
            BitmapMissingFonts=True,
            CreateBookmarks=WD_EXPORT_CREATE_NO_BOOKMARKS,
        )
        if not pdf_path.exists():
            raise RuntimeError(f"Word ExportAsFixedFormat produced no PDF: {pdf_path}")
        return version
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
            try:
                del word
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        if tmp_copy.exists():
            try:
                tmp_copy.unlink()
            except OSError:
                pass


def pdf_to_pngs(pdftoppm: str, pdf: Path, dest: Path, dpi: int) -> list:
    dest.mkdir(parents=True, exist_ok=True)
    # Remove prior pages so regenerate is clean.
    for old in dest.glob("page-*.png"):
        old.unlink()
    prefix = dest / "page"
    # -aa / -aaVector off for more deterministic rasterization across runs.
    subprocess.run(
        [
            pdftoppm,
            "-png",
            "-r",
            str(dpi),
            "-aa",
            "no",
            "-aaVector",
            "no",
            str(pdf),
            str(prefix),
        ],
        check=True,
        capture_output=True,
        timeout=1200,
    )
    pages = sorted(dest.glob("page-*.png"))
    if not pages:
        raise RuntimeError(f"pdftoppm produced no pages for {pdf.name}")
    renamed = []
    for p in pages:
        m = re.match(r"page-(\d+)\.png", p.name)
        if not m:
            continue
        idx = int(m.group(1))
        target = dest / f"page-{idx:03d}.png"
        if p != target:
            if target.exists():
                target.unlink()
            p.rename(target)
        renamed.append(target)
    return sorted(dest.glob("page-*.png"))


def generate_case(
    case: str,
    dpi: int,
    force: bool,
    pdftoppm: str,
) -> dict:
    from PIL import Image

    docx = ensure_fixture(case)
    actual_hash = sha256(docx)
    reference_datetime = None
    if case == "date_field":
        reference_datetime = (
            datetime.datetime.now()
            .astimezone()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat()
        )

    dest = GOLDEN_ROOT / case
    if dest.exists() and any(dest.glob("page-*.png")):
        if not force:
            print(f"[skip] {case}: office golden already exists (use --force)")
            meta_path = dest / "metadata.json"
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    return json.load(f)
            return {"case": case, "skipped": True}

    dest.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="docx2img-office-") as tmp:
        tmpdir = Path(tmp)
        pdf = tmpdir / (docx.stem + ".pdf")
        word_version = word_export_pdf(docx, pdf)
        pages = pdf_to_pngs(pdftoppm, pdf, dest, dpi)

    sizes = []
    for p in pages:
        with Image.open(p) as img:
            # Force RGB white-background pages for consistent compare.
            rgb = img.convert("RGB")
            if rgb.mode != "RGB":
                rgb = rgb.convert("RGB")
            rgb.save(p)
            sizes.append(list(rgb.size))

    meta = {
        "provider": "office",
        "case": case,
        "input_docx": docx.name,
        "input_path": str(docx.relative_to(REPO)).replace("\\", "/"),
        "input_sha256": actual_hash,
        "word_version": word_version,
        "pdftoppm_version": tool_version([pdftoppm, "-v"]),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "docx2img_version": _docx2img_version(),
        "dpi": dpi,
        "color_mode": "RGB",
        "background": [255, 255, 255],
        "reference_datetime": reference_datetime,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pdf_pages": len(pages),
        "page_sizes_px": sizes,
        "fonts_note": (
            "Word used the host font environment; substitutions are not "
            "individually traced by ExportAsFixedFormat."
        ),
        "baseline_note": (
            "First-introduction baseline: no global MAE/SSIM pass threshold. "
            "Subsequent slices must improve the target case without regressing "
            "existing office goldens."
        ),
    }
    with open(dest / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(
        f"[ok]   {case}: {len(pages)} pages @ {dpi}dpi "
        f"(Word {word_version}) -> {dest.relative_to(REPO)}"
    )
    return meta


def _docx2img_version() -> str:
    try:
        sys.path.insert(0, str(REPO / "src"))
        from docx2img import __version__

        return __version__
    except Exception:
        return "unknown"


def main(argv: Optional[list] = None) -> int:
    if sys.platform != "win32":
        print("ERROR: Word office golden generation requires Windows + Word COM.")
        return 2

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument(
        "--case",
        action="append",
        choices=sorted(CASES),
        help="limit to specific case(s); default: all",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="regenerate existing office goldens",
    )
    args = ap.parse_args(argv)

    pdftoppm = find_pdftoppm()
    cases = args.case or sorted(CASES)
    for case in cases:
        generate_case(case, args.dpi, args.force, pdftoppm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
