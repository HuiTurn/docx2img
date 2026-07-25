#!/usr/bin/env python3
"""Visual regression: docx2img output vs LibreOffice golden references.

Per case:
  1. Render the DOCX with docx2img at the golden's DPI into
     tests/output/actual/<case>/page-NNN.png
  2. Compare each page against tests/golden/libreoffice/<case>/page-NNN.png:
       - page count match
       - page pixel size
       - ink bounding box (non-white area) for both sides
       - mean absolute pixel error (MAE, grayscale, resized-aligned)
       - differing-pixel ratio (threshold 32/255)
       - diff heatmap image -> tests/output/diff/<case>/page-NNN-diff.png
  3. Run validate.visual glyph/blank/sparse checks.
  4. Write tests/output/report.json and print a summary table.

Usage:
  python scripts/run_visual_regression.py [--case lists ...] [--max-pages N]

Only Pillow + stdlib are used (project runtime constraint).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from PIL import Image, ImageChops, ImageOps  # noqa: E402

CORPUS = REPO / "testdata" / "regression" / "sample-files-complex"
GOLDEN_ROOT = REPO / "tests" / "golden" / "libreoffice"
ACTUAL_ROOT = REPO / "tests" / "output" / "actual"
DIFF_ROOT = REPO / "tests" / "output" / "diff"
REPORT_PATH = REPO / "tests" / "output" / "report.json"

CASES = {
    "image-document": "sample-files.com-image-document.docx",
    "table-document": "sample-files.com-table-document.docx",
    "template": "sample-files.com-template.docx",
    "lists": "sample-files.com-lists.docx",
    "tracked-changes": "sample-files.com-tracked-changes.docx",
    "multi-column": "sample-files.com-multi-column.docx",
    "large-document": "sample-files.com-large-document.docx",
}

DIFF_THRESHOLD = 32  # gray levels; below this a pixel counts as "same"
INK_THRESHOLD = 250  # >= this gray value counts as white/background


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ink_bbox(gray: Image.Image):
    """Bounding box of non-white ink, or None for a blank page."""
    mask = gray.point(lambda v: 255 if v < INK_THRESHOLD else 0)
    return mask.getbbox()


def compare_page(actual: Image.Image, golden: Image.Image, diff_path: Path) -> dict:
    a_gray = ImageOps.grayscale(actual)
    g_gray = ImageOps.grayscale(golden)

    size_match = actual.size == golden.size
    # Align by resizing actual onto golden's grid for pixel metrics.
    a_cmp = a_gray if size_match else a_gray.resize(golden.size, Image.LANCZOS)

    diff = ImageChops.difference(a_cmp, g_gray)
    hist = diff.histogram()
    total = golden.size[0] * golden.size[1]
    mae = sum(i * n for i, n in enumerate(hist)) / total if total else 0.0
    diff_px = sum(hist[DIFF_THRESHOLD:])
    diff_ratio = diff_px / total if total else 0.0

    # Heatmap: red where different, faded golden underneath.
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    mask = diff.point(lambda v: 255 if v >= DIFF_THRESHOLD else 0)
    base = Image.blend(g_gray.convert("RGB"),
                       Image.new("RGB", golden.size, "white"), 0.65)
    red = Image.new("RGB", golden.size, (220, 30, 30))
    base.paste(red, mask=mask)
    base.save(diff_path)

    return {
        "actual_size": list(actual.size),
        "golden_size": list(golden.size),
        "size_match": size_match,
        "ink_bbox_actual": ink_bbox(a_gray),
        "ink_bbox_golden": ink_bbox(g_gray),
        "mae": round(mae, 3),
        "diff_pixel_ratio": round(diff_ratio, 5),
    }


def run_case(case: str, max_pages: Optional[int]) -> dict:
    from docx2img.config import Config
    from docx2img import convert_to_images
    from docx2img.validate.visual import validate_docx

    golden_dir = GOLDEN_ROOT / case
    meta_path = golden_dir / "metadata.json"
    if not meta_path.exists():
        return {"case": case, "error": "golden missing — run generate_lo_golden.py"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    docx = CORPUS / CASES[case]
    if sha256(docx) != meta["input_sha256"]:
        return {"case": case, "error": "input SHA-256 differs from golden metadata"}

    dpi = meta["dpi"]
    golden_pages = sorted(golden_dir.glob("page-*.png"))

    actual_dir = ACTUAL_ROOT / case
    diff_dir = DIFF_ROOT / case
    actual_dir.mkdir(parents=True, exist_ok=True)
    for old in actual_dir.glob("page-*.png"):
        old.unlink()
    for old in diff_dir.glob("page-*-diff.png") if diff_dir.exists() else []:
        old.unlink()

    result: dict = {"case": case, "dpi": dpi, "golden_pages": len(golden_pages)}

    t0 = time.time()
    try:
        images = convert_to_images(docx, Config(dpi=dpi))
    except Exception as exc:
        result["error"] = f"docx2img crashed: {type(exc).__name__}: {exc}"
        return result
    result["render_seconds"] = round(time.time() - t0, 2)
    result["actual_pages"] = len(images)
    result["page_count_match"] = len(images) == len(golden_pages)

    n = min(len(images), len(golden_pages))
    if max_pages is not None:
        n = min(n, max_pages)

    pages = []
    for i in range(len(images) if max_pages is None else min(len(images), max_pages)):
        out = actual_dir / f"page-{i+1:03d}.png"
        images[i].save(out)

    mae_sum = ratio_sum = 0.0
    for i in range(n):
        actual_img = Image.open(actual_dir / f"page-{i+1:03d}.png")
        golden_img = Image.open(golden_pages[i])
        m = compare_page(actual_img, golden_img,
                         diff_dir / f"page-{i+1:03d}-diff.png")
        m["page"] = i + 1
        pages.append(m)
        mae_sum += m["mae"]
        ratio_sum += m["diff_pixel_ratio"]
    result["pages"] = pages
    if n:
        result["mean_mae"] = round(mae_sum / n, 3)
        result["mean_diff_ratio"] = round(ratio_sum / n, 5)

    try:
        vr = validate_docx(docx, Config(dpi=dpi), max_pages=max_pages)
        result["visual_validate"] = {
            "missing_glyphs": len(vr.missing_glyphs),
            "fallback_count": vr.fallback_count,
            "unresolved_count": vr.unresolved_count,
            "blank_pages": vr.blank_pages,
            "sparse_pages": vr.sparse_pages,
        }
    except Exception as exc:
        result["visual_validate"] = {"error": f"{type(exc).__name__}: {exc}"}

    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", action="append", choices=sorted(CASES))
    ap.add_argument("--max-pages", type=int, default=None,
                    help="limit compared pages (useful for large-document)")
    args = ap.parse_args()

    cases = args.case or sorted(CASES)
    results = [run_case(c, args.max_pages) for c in cases]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if REPORT_PATH.exists():
        try:
            existing = {r["case"]: r for r in
                        json.loads(REPORT_PATH.read_text())["results"]}
        except Exception:
            existing = {}
    for r in results:
        existing[r["case"]] = r
    payload = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "results": [existing[c] for c in sorted(existing)]}
    REPORT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    hdr = f"{'case':<16} {'pages A/G':>10} {'size':>6} {'MAE':>8} {'diff%':>8}  notes"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        if "error" in r:
            print(f"{r['case']:<16} {'-':>10} {'-':>6} {'-':>8} {'-':>8}  "
                  f"ERROR: {r['error']}")
            continue
        pg = f"{r['actual_pages']}/{r['golden_pages']}"
        sizes_ok = all(p["size_match"] for p in r.get("pages", []))
        vv = r.get("visual_validate", {})
        notes = []
        if not r["page_count_match"]:
            notes.append("PAGE-COUNT!")
        if vv.get("blank_pages"):
            notes.append(f"blank={vv['blank_pages']}")
        if vv.get("missing_glyphs"):
            notes.append(f"missing_glyphs={vv['missing_glyphs']}")
        if vv.get("unresolved_count"):
            notes.append(f"unresolved={vv['unresolved_count']}")
        print(f"{r['case']:<16} {pg:>10} {'ok' if sizes_ok else 'DIFF':>6} "
              f"{r.get('mean_mae', 0):>8} {r.get('mean_diff_ratio', 0)*100:>7.2f}%"
              f"  {' '.join(notes)}")
    print(f"\nreport: {REPORT_PATH.relative_to(REPO)}")


if __name__ == "__main__":
    main()
