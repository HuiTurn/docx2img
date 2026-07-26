#!/usr/bin/env python3
"""Visual regression: docx2img output vs golden references.

Providers:
  libreoffice  → tests/golden/libreoffice/<case>/  (legacy corpus + LO PDF)
  office       → tests/golden/office/<case>/       (Word ExportAsFixedFormat)

Per case:
  1. Render the DOCX with docx2img at the golden's DPI.
  2. Pair pages with the provider golden (no free resize/crop for office).
  3. Emit reference/actual/abs-diff/overlay artifacts + metrics manifest.
  4. Write tests/output/<provider>/report.json

Usage:
  python scripts/run_visual_regression.py --provider office [--case basic_text]
  python scripts/run_visual_regression.py --provider libreoffice [--case lists]

Office baseline policy: record metrics; do NOT apply a global MAE/SSIM pass
threshold on first introduction. Hard differences (page-count / size mismatch
or render crash) are always flagged.
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
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

from PIL import Image  # noqa: E402

from visual_compare import compare_pages_strict  # noqa: E402

CORPUS_LO = REPO / "testdata" / "regression" / "sample-files-complex"
CORPUS_OFFICE = REPO / "testdata" / "regression" / "office-min"

LO_CASES = {
    "image-document": "sample-files.com-image-document.docx",
    "table-document": "sample-files.com-table-document.docx",
    "template": "sample-files.com-template.docx",
    "lists": "sample-files.com-lists.docx",
    "tracked-changes": "sample-files.com-tracked-changes.docx",
    "multi-column": "sample-files.com-multi-column.docx",
    "large-document": "sample-files.com-large-document.docx",
}

OFFICE_CASES = {
    "basic_text": "basic_text.docx",
    "date_field": "date_field.docx",
    "drawingml_text": "drawingml_text.docx",
    "math_bar": "math_bar.docx",
    "page_break": "page_break.docx",
    "shape_fill": "shape_fill.docx",
}

# Back-compat aliases used by the legacy LO-only CLI.
CASES = LO_CASES
GOLDEN_ROOT = REPO / "tests" / "golden" / "libreoffice"
ACTUAL_ROOT = REPO / "tests" / "output" / "actual"
DIFF_ROOT = REPO / "tests" / "output" / "diff"
REPORT_PATH = REPO / "tests" / "output" / "report.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _paths(provider: str):
    if provider == "office":
        return {
            "corpus": CORPUS_OFFICE,
            "cases": OFFICE_CASES,
            "golden": REPO / "tests" / "golden" / "office",
            "actual": REPO / "tests" / "output" / "office" / "actual",
            "diff": REPO / "tests" / "output" / "office" / "diff",
            "overlay": REPO / "tests" / "output" / "office" / "overlay",
            "absdiff": REPO / "tests" / "output" / "office" / "absdiff",
            "report": REPO / "tests" / "output" / "office" / "report.json",
        }
    return {
        "corpus": CORPUS_LO,
        "cases": LO_CASES,
        "golden": REPO / "tests" / "golden" / "libreoffice",
        "actual": REPO / "tests" / "output" / "libreoffice" / "actual",
        "diff": REPO / "tests" / "output" / "libreoffice" / "diff",
        "overlay": REPO / "tests" / "output" / "libreoffice" / "overlay",
        "absdiff": REPO / "tests" / "output" / "libreoffice" / "absdiff",
        "report": REPO / "tests" / "output" / "libreoffice" / "report.json",
    }


def _ensure_office_fixture(case: str, docx: Path) -> None:
    if docx.exists():
        return
    from fixtures.gen_fixtures import (
        make_basic_text,
        make_date_field,
        make_drawingml_text,
        make_math_bar,
        make_page_break,
        make_shape_fill,
    )

    builders = {
        "basic_text": make_basic_text,
        "date_field": make_date_field,
        "drawingml_text": make_drawingml_text,
        "math_bar": make_math_bar,
        "page_break": make_page_break,
        "shape_fill": make_shape_fill,
    }
    builders[case](docx)


def run_case(provider: str, case: str, max_pages: Optional[int]) -> dict:
    from docx2img import __version__ as d2i_version
    from docx2img.config import Config
    from docx2img import convert_to_images
    from docx2img.validate.visual import validate_docx

    P = _paths(provider)
    golden_dir = P["golden"] / case
    meta_path = golden_dir / "metadata.json"
    if not meta_path.exists():
        hint = (
            "generate_office_golden.py"
            if provider == "office"
            else "generate_lo_golden.py"
        )
        return {"case": case, "provider": provider, "error": f"golden missing — run {hint}"}

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    docx = P["corpus"] / P["cases"][case]
    if provider == "office":
        _ensure_office_fixture(case, docx)

    if not docx.exists():
        return {"case": case, "provider": provider, "error": f"missing input {docx}"}

    input_hash = sha256(docx)
    if input_hash != meta.get("input_sha256"):
        return {
            "case": case,
            "provider": provider,
            "error": "input SHA-256 differs from golden metadata",
            "expected_sha256": meta.get("input_sha256"),
            "actual_sha256": input_hash,
        }

    dpi = meta["dpi"]
    golden_pages = sorted(golden_dir.glob("page-*.png"))
    reference_datetime = None
    if meta.get("reference_datetime"):
        from datetime import datetime

        reference_datetime = datetime.fromisoformat(meta["reference_datetime"])
    config_kwargs = {
        "dpi": dpi,
        "color_mode": "RGB",
        "background_color": (255, 255, 255),
    }
    if reference_datetime is not None:
        config_kwargs["reference_datetime"] = reference_datetime
    render_config = Config(**config_kwargs)

    actual_dir = P["actual"] / case
    diff_dir = P["diff"] / case
    overlay_dir = P["overlay"] / case
    absdiff_dir = P["absdiff"] / case
    for d in (actual_dir, diff_dir, overlay_dir, absdiff_dir):
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("page-*"):
            old.unlink()

    # Also copy reference pages beside artifacts for easy inspection.
    ref_dir = P["actual"].parent / "reference" / case
    ref_dir.mkdir(parents=True, exist_ok=True)
    for old in ref_dir.glob("page-*.png"):
        old.unlink()
    for gp in golden_pages:
        (ref_dir / gp.name).write_bytes(gp.read_bytes())

    result: dict = {
        "case": case,
        "provider": provider,
        "dpi": dpi,
        "docx2img_version": d2i_version,
        "input_sha256": input_hash,
        "golden_pages": len(golden_pages),
        "word_version": meta.get("word_version"),
        "libreoffice_version": meta.get("libreoffice_version"),
        "baseline_policy": meta.get("baseline_note"),
        "config": {
            "reference_datetime": (
                reference_datetime.isoformat()
                if reference_datetime is not None
                else Config().reference_datetime.isoformat()
            )
        },
    }

    t0 = time.time()
    try:
        images = convert_to_images(
            docx,
            render_config,
        )
    except Exception as exc:
        result["error"] = f"docx2img crashed: {type(exc).__name__}: {exc}"
        result["hard_diff"] = True
        return result
    result["render_seconds"] = round(time.time() - t0, 2)
    result["actual_pages"] = len(images)
    result["page_count_match"] = len(images) == len(golden_pages)
    if not result["page_count_match"]:
        result["hard_diff"] = True

    # Determinism: second render must be byte-identical PNG payloads.
    images2 = convert_to_images(
        docx,
        render_config,
    )
    det_ok = len(images) == len(images2)
    for i, (a, b) in enumerate(zip(images, images2)):
        import io

        ba = io.BytesIO()
        bb = io.BytesIO()
        a.save(ba, format="PNG")
        b.save(bb, format="PNG")
        if ba.getvalue() != bb.getvalue():
            det_ok = False
            break
    result["deterministic"] = det_ok

    n_save = len(images) if max_pages is None else min(len(images), max_pages)
    for i in range(n_save):
        images[i].save(actual_dir / f"page-{i+1:03d}.png")

    n = min(len(images), len(golden_pages))
    if max_pages is not None:
        n = min(n, max_pages)

    pages = []
    mae_vals = []
    ratio_vals = []
    rmse_vals = []
    ssim_vals = []
    for i in range(n):
        actual_img = Image.open(actual_dir / f"page-{i+1:03d}.png")
        golden_img = Image.open(golden_pages[i])
        m = compare_pages_strict(
            actual_img,
            golden_img,
            diff_path=diff_dir / f"page-{i+1:03d}-diff.png",
            overlay_path=overlay_dir / f"page-{i+1:03d}-overlay.png",
            abs_diff_path=absdiff_dir / f"page-{i+1:03d}-absdiff.png",
        )
        m["page"] = i + 1
        if m.get("hard_size_mismatch"):
            result["hard_diff"] = True
        pages.append(m)
        if m["mae"] is not None:
            mae_vals.append(m["mae"])
        if m["rmse"] is not None:
            rmse_vals.append(m["rmse"])
        if m["diff_pixel_ratio"] is not None:
            ratio_vals.append(m["diff_pixel_ratio"])
        if m["ssim"] is not None:
            ssim_vals.append(m["ssim"])

    result["pages"] = pages
    if mae_vals:
        result["mean_mae"] = round(sum(mae_vals) / len(mae_vals), 3)
    if rmse_vals:
        result["mean_rmse"] = round(sum(rmse_vals) / len(rmse_vals), 3)
    if ratio_vals:
        result["mean_diff_ratio"] = round(sum(ratio_vals) / len(ratio_vals), 5)
    if ssim_vals:
        result["mean_ssim"] = round(sum(ssim_vals) / len(ssim_vals), 6)

    # Office first-introduction: metrics only, no global threshold gate.
    if provider == "office":
        result["pass_threshold_applied"] = False
        result["status"] = "baseline_recorded" if not result.get("hard_diff") else "hard_diff"
    else:
        result["pass_threshold_applied"] = False
        result["status"] = "compared"

    try:
        vr = validate_docx(docx, render_config, max_pages=max_pages)
        result["visual_validate"] = {
            "missing_glyphs": len(vr.missing_glyphs),
            "fallback_count": vr.fallback_count,
            "unresolved_count": vr.unresolved_count,
            "blank_pages": vr.blank_pages,
            "sparse_pages": vr.sparse_pages,
        }
    except Exception as exc:
        result["visual_validate"] = {"error": f"{type(exc).__name__}: {exc}"}

    result["artifacts"] = {
        "reference": str(ref_dir.relative_to(REPO)).replace("\\", "/"),
        "actual": str(actual_dir.relative_to(REPO)).replace("\\", "/"),
        "diff": str(diff_dir.relative_to(REPO)).replace("\\", "/"),
        "overlay": str(overlay_dir.relative_to(REPO)).replace("\\", "/"),
        "absdiff": str(absdiff_dir.relative_to(REPO)).replace("\\", "/"),
    }
    return result


# Legacy entry used by older imports/tests.
def run_case_legacy(case: str, max_pages: Optional[int]) -> dict:
    return run_case("libreoffice", case, max_pages)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--provider",
        choices=("libreoffice", "office"),
        default="libreoffice",
        help="golden provider (default: libreoffice for back-compat)",
    )
    ap.add_argument("--case", action="append")
    ap.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="limit compared pages (useful for large-document)",
    )
    args = ap.parse_args()

    P = _paths(args.provider)
    valid = sorted(P["cases"])
    if args.case:
        bad = [c for c in args.case if c not in P["cases"]]
        if bad:
            ap.error(f"unknown case(s) for provider={args.provider}: {bad}; choose from {valid}")
        cases = args.case
    else:
        cases = valid

    results = [run_case(args.provider, c, args.max_pages) for c in cases]

    report_path = P["report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if report_path.exists():
        try:
            existing = {
                r["case"]: r
                for r in json.loads(report_path.read_text(encoding="utf-8"))["results"]
            }
        except Exception:
            existing = {}
    for r in results:
        existing[r["case"]] = r
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "provider": args.provider,
        "results": [existing[c] for c in sorted(existing)],
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    hdr = (
        f"{'case':<16} {'pages A/G':>10} {'size':>6} {'MAE':>8} "
        f"{'RMSE':>8} {'diff%':>8} {'SSIM':>8}  notes"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        if "error" in r:
            print(
                f"{r['case']:<16} {'-':>10} {'-':>6} {'-':>8} {'-':>8} {'-':>8} {'-':>8}  "
                f"ERROR: {r['error']}"
            )
            continue
        pg = f"{r['actual_pages']}/{r['golden_pages']}"
        sizes_ok = all(p.get("size_match", False) for p in r.get("pages", []))
        vv = r.get("visual_validate", {})
        notes = []
        if r.get("hard_diff"):
            notes.append("HARD-DIFF")
        if not r.get("page_count_match", True):
            notes.append("PAGE-COUNT!")
        if not r.get("deterministic", True):
            notes.append("NON-DETERMINISTIC")
        if vv.get("blank_pages"):
            notes.append(f"blank={vv['blank_pages']}")
        if vv.get("missing_glyphs"):
            notes.append(f"missing_glyphs={vv['missing_glyphs']}")
        if r.get("status") == "baseline_recorded":
            notes.append("baseline")
        mae = r.get("mean_mae")
        rmse = r.get("mean_rmse")
        ratio = r.get("mean_diff_ratio")
        ssim = r.get("mean_ssim")
        print(
            f"{r['case']:<16} {pg:>10} {'ok' if sizes_ok else 'DIFF':>6} "
            f"{(mae if mae is not None else float('nan')):>8} "
            f"{(rmse if rmse is not None else float('nan')):>8} "
            f"{(ratio * 100 if ratio is not None else float('nan')):>7.2f}% "
            f"{(ssim if ssim is not None else float('nan')):>8}  "
            f"{' '.join(notes)}"
        )
    print(f"\nprovider: {args.provider}")
    print(f"report: {report_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
