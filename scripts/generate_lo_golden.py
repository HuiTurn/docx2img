#!/usr/bin/env python3
"""Generate LibreOffice golden reference PNGs for the complex regression corpus.

Pipeline per DOCX:
  1. Verify SHA-256 against testdata/regression/sample-files-complex/README.md.
  2. LibreOffice headless -> PDF (in a temp dir, with an isolated user profile).
  3. pdftoppm -png -r <dpi> -> tests/golden/libreoffice/<case>/page-%03d.png
  4. Write metadata.json (input hash, tool versions, DPI, page count, sizes...).

Goldens are versioned artifacts: an existing golden directory is NEVER
silently overwritten. Pass --force to regenerate.

Usage:
  python scripts/generate_lo_golden.py [--dpi 150] [--case lists ...] [--force]

LibreOffice is only used offline here; it is NOT a runtime dependency of
docx2img.
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

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "testdata" / "regression" / "sample-files-complex"
GOLDEN_ROOT = REPO / "tests" / "golden" / "libreoffice"

# case name -> docx filename
CASES = {
    "image-document": "sample-files.com-image-document.docx",
    "table-document": "sample-files.com-table-document.docx",
    "template": "sample-files.com-template.docx",
    "lists": "sample-files.com-lists.docx",
    "tracked-changes": "sample-files.com-tracked-changes.docx",
    "multi-column": "sample-files.com-multi-column.docx",
    "large-document": "sample-files.com-large-document.docx",
}

SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


def find_soffice() -> str:
    for cand in SOFFICE_CANDIDATES:
        path = shutil.which(cand) or (cand if Path(cand).exists() else None)
        if path:
            return path
    raise SystemExit("ERROR: LibreOffice (soffice) not found. Install it first.")


def find_pdftoppm() -> str:
    path = shutil.which("pdftoppm")
    if not path:
        raise SystemExit("ERROR: pdftoppm not found. Install poppler first.")
    return path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_tracked_changes(docx: Path, outdir: Path) -> Path:
    """Return a temporary DOCX with tracked changes accepted.

    LibreOffice headless cannot load some sample-files.com tracked-changes
    documents ("source file could not be loaded").  Accepting all changes
    removes w:ins/w:del wrappers while preserving the final document text,
    producing a renderable golden that matches what docx2img renders (it does
    not draw revision marks either).
    """
    import zipfile

    cleaned = outdir / (docx.stem + "-cleaned.docx")
    with zipfile.ZipFile(docx, "r") as zin, zipfile.ZipFile(cleaned, "w") as zout:
        for item in zin.namelist():
            data = zin.read(item)
            if item == "word/document.xml":
                # Simple, robust regex-based stripping of revision wrappers.
                # We keep the children of w:ins (insertions) and drop w:del
                # entirely (deletions).  We also strip comment range markers,
                # which LibreOffice headless sometimes cannot resolve without
                # the corresponding comments part.
                text = data.decode("utf-8")
                # Remove w:del blocks entirely.
                text = re.sub(
                    r"<w:del\b[^>]*>.*?</w:del>",
                    "",
                    text,
                    flags=re.DOTALL,
                )
                # Unwrap w:ins blocks: keep their content.
                text = re.sub(
                    r"<w:ins\b[^>]*>(.*?)</w:ins>",
                    r"\1",
                    text,
                    flags=re.DOTALL,
                )
                # Strip comment range markers and references.
                text = re.sub(
                    r"<w:commentRange(?:Start|End)\b[^>]*?/>",
                    "",
                    text,
                )
                text = re.sub(
                    r"<w:commentReference\b[^>]*?/>",
                    "",
                    text,
                )
                # Drop any orphaned revision IDs/attributes on runs/paragraphs.
                text = re.sub(r'\s+w:rsidDel="[^"]*"', "", text)
                text = re.sub(r'\s+w:rsidRPr="[^"]*"', "", text)
                text = re.sub(r'\s+w:rsidTr="[^"]*"', "", text)
                data = text.encode("utf-8")
            zout.writestr(item, data)
    return cleaned


def readme_hashes() -> dict:
    """Parse expected SHA-256 per filename from the corpus README table."""
    text = (CORPUS / "README.md").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"`([^`]+\.docx)`.*?`([0-9a-f]{64})`", text):
        out[m.group(1)] = m.group(2)
    return out


def tool_version(cmd: list) -> str:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, check=False
        )
        return (proc.stdout or proc.stderr).strip().splitlines()[0]
    except Exception as exc:  # pragma: no cover
        return f"unknown ({exc})"


def convert_to_pdf(soffice: str, docx: Path, outdir: Path) -> Path:
    profile = outdir / "lo-profile"
    cmd = [
        soffice,
        "--headless",
        "--norestore",
        f"-env:UserInstallation=file://{profile}",
        "--convert-to", "pdf",
        "--outdir", str(outdir),
        str(docx),
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600, check=False
    )
    pdf = outdir / (docx.stem + ".pdf")
    if proc.returncode != 0 or not pdf.exists():
        raise RuntimeError(
            f"LibreOffice PDF export failed for {docx.name}:\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return pdf


def pdf_to_pngs(pdftoppm: str, pdf: Path, dest: Path, dpi: int) -> list:
    dest.mkdir(parents=True, exist_ok=True)
    prefix = dest / "page"
    subprocess.run(
        [pdftoppm, "-png", "-r", str(dpi), str(pdf), str(prefix)],
        check=True, capture_output=True, timeout=1200,
    )
    pages = sorted(dest.glob("page-*.png"))
    if not pages:
        raise RuntimeError(f"pdftoppm produced no pages for {pdf.name}")
    # Normalise names to page-001.png style (pdftoppm pads by total count).
    renamed = []
    for p in pages:
        m = re.match(r"page-(\d+)\.png", p.name)
        idx = int(m.group(1))
        target = dest / f"page-{idx:03d}.png"
        if p != target:
            p.rename(target)
        renamed.append(target)
    return sorted(dest.glob("page-*.png"))


def generate_case(case: str, dpi: int, force: bool, soffice: str, pdftoppm: str,
                  expected: dict) -> dict:
    from PIL import Image

    docx = CORPUS / CASES[case]
    if not docx.exists():
        raise SystemExit(f"ERROR: missing corpus file {docx}")

    actual_hash = sha256(docx)
    exp = expected.get(docx.name)
    if exp and exp != actual_hash:
        raise SystemExit(
            f"ERROR: SHA-256 mismatch for {docx.name}!\n"
            f"  expected {exp}\n  actual   {actual_hash}\n"
            "Refusing to generate golden from a modified input."
        )

    dest = GOLDEN_ROOT / case
    if dest.exists() and any(dest.glob("page-*.png")):
        if not force:
            print(f"[skip] {case}: golden already exists (use --force to regenerate)")
            with open(dest / "metadata.json", encoding="utf-8") as f:
                return json.load(f)
        shutil.rmtree(dest)

    with tempfile.TemporaryDirectory(prefix="docx2img-lo-") as tmp:
        tmpdir = Path(tmp)
        source_docx = docx
        if case == "tracked-changes":
            source_docx = strip_tracked_changes(docx, tmpdir)
        pdf = convert_to_pdf(soffice, source_docx, tmpdir)
        pages = pdf_to_pngs(pdftoppm, pdf, dest, dpi)

    sizes = []
    for p in pages:
        with Image.open(p) as img:
            sizes.append(list(img.size))

    meta = {
        "case": case,
        "input_docx": docx.name,
        "input_sha256": actual_hash,
        "libreoffice_version": tool_version([soffice, "--version"]),
        "pdftoppm_version": tool_version([pdftoppm, "-v"]),
        "macos_version": platform.mac_ver()[0] or platform.platform(),
        "python_version": platform.python_version(),
        "dpi": dpi,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pdf_pages": len(pages),
        "page_sizes_px": sizes,
        "fonts_note": "LibreOffice used system-installed fonts; substitutions not "
                      "individually traced (headless export does not report them).",
        "tracked_changes_note": (
            "Golden generated from a tracked-changes-accepted copy; "
            "LibreOffice headless could not load the raw file."
            if case == "tracked-changes"
            else None
        ),
    }
    with open(dest / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"[ok]   {case}: {len(pages)} pages @ {dpi}dpi -> {dest.relative_to(REPO)}")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--case", action="append", choices=sorted(CASES),
                    help="limit to specific case(s); default: all")
    ap.add_argument("--force", action="store_true",
                    help="regenerate existing goldens")
    args = ap.parse_args()

    soffice = find_soffice()
    pdftoppm = find_pdftoppm()
    expected = readme_hashes()

    cases = args.case or sorted(CASES)
    for case in cases:
        generate_case(case, args.dpi, args.force, soffice, pdftoppm, expected)


if __name__ == "__main__":
    sys.exit(main())
