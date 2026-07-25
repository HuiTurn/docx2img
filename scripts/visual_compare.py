"""Shared page-pair visual metrics for regression providers.

Hard rules for the Word/office provider:
  - identical DPI / page size / white background expected
  - size or page-count mismatch is a hard difference (no free resize/crop/align)
  - metrics: MAE, RMSE, changed-pixel ratio; SSIM when computable
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageChops, ImageOps, ImageStat

DIFF_THRESHOLD = 32  # gray levels; below this a pixel counts as "same"
INK_THRESHOLD = 250  # >= this gray value counts as white/background


def ink_bbox(gray: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """Bounding box of non-white ink, or None for a blank page."""
    mask = gray.point(lambda v: 255 if v < INK_THRESHOLD else 0)
    return mask.getbbox()


def edge_overflow(
    ink: Optional[Tuple[int, int, int, int]],
    size: Tuple[int, int],
    margin_px: int = 2,
) -> dict:
    """Report whether ink touches page edges (within margin_px)."""
    w, h = size
    if ink is None:
        return {
            "touches_left": False,
            "touches_top": False,
            "touches_right": False,
            "touches_bottom": False,
        }
    l, t, r, b = ink
    return {
        "touches_left": l <= margin_px,
        "touches_top": t <= margin_px,
        "touches_right": r >= w - margin_px,
        "touches_bottom": b >= h - margin_px,
    }


def _ssim_grayscale(a: Image.Image, b: Image.Image) -> Optional[float]:
    """Lightweight global SSIM on 8-bit grayscale (no numpy dependency).

    Downscales to max side 256 before the single-window luminance formula so
    page-sized images stay practical without numpy. Returns None if sizes
    differ or variance is degenerate.
    """
    if a.size != b.size:
        return None
    max_side = 256
    w, h = a.size
    scale = max(w, h) / max_side if max(w, h) > max_side else 1.0
    if scale > 1.0:
        nw, nh = max(1, int(w / scale)), max(1, int(h / scale))
        a = a.resize((nw, nh), Image.BILINEAR)
        b = b.resize((nw, nh), Image.BILINEAR)
    pa = list(a.get_flattened_data() if hasattr(a, "get_flattened_data") else a.getdata())
    pb = list(b.get_flattened_data() if hasattr(b, "get_flattened_data") else b.getdata())
    n = len(pa)
    if n == 0:
        return None
    mean_a = sum(pa) / n
    mean_b = sum(pb) / n
    var_a = sum((x - mean_a) ** 2 for x in pa) / n
    var_b = sum((x - mean_b) ** 2 for x in pb) / n
    cov = sum((pa[i] - mean_a) * (pb[i] - mean_b) for i in range(n)) / n
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    denom = (mean_a ** 2 + mean_b ** 2 + c1) * (var_a + var_b + c2)
    if denom == 0:
        return None
    num = (2 * mean_a * mean_b + c1) * (2 * cov + c2)
    return round(num / denom, 6)


def compare_pages_strict(
    actual: Image.Image,
    reference: Image.Image,
    *,
    diff_path: Optional[Path] = None,
    overlay_path: Optional[Path] = None,
    abs_diff_path: Optional[Path] = None,
) -> dict:
    """Compare two pages without resizing or cropping.

    When sizes differ, pixel metrics are omitted and ``hard_size_mismatch``
    is set True.
    """
    a_rgb = actual.convert("RGB")
    r_rgb = reference.convert("RGB")
    a_gray = ImageOps.grayscale(a_rgb)
    r_gray = ImageOps.grayscale(r_rgb)

    a_ink = ink_bbox(a_gray)
    r_ink = ink_bbox(r_gray)
    result = {
        "actual_size": list(a_rgb.size),
        "reference_size": list(r_rgb.size),
        "size_match": a_rgb.size == r_rgb.size,
        "hard_size_mismatch": a_rgb.size != r_rgb.size,
        "ink_bbox_actual": list(a_ink) if a_ink else None,
        "ink_bbox_reference": list(r_ink) if r_ink else None,
        "edge_overflow_actual": edge_overflow(a_ink, a_rgb.size),
        "edge_overflow_reference": edge_overflow(r_ink, r_rgb.size),
        "mae": None,
        "rmse": None,
        "diff_pixel_ratio": None,
        "ssim": None,
    }

    if a_rgb.size != r_rgb.size:
        # Still emit a diagnostic overlay at the reference canvas size with
        # actual pasted at (0,0) clipped — labelled hard mismatch, not a metric.
        if overlay_path is not None:
            overlay_path.parent.mkdir(parents=True, exist_ok=True)
            canvas = Image.new("RGBA", r_rgb.size, (255, 255, 255, 255))
            act = a_rgb.convert("RGBA")
            canvas.paste(act, (0, 0))
            red = Image.new("RGBA", r_rgb.size, (220, 30, 30, 90))
            canvas = Image.alpha_composite(canvas, red)
            canvas.save(overlay_path)
        return result

    diff = ImageChops.difference(a_gray, r_gray)
    hist = diff.histogram()
    total = r_rgb.size[0] * r_rgb.size[1]
    mae = sum(i * n for i, n in enumerate(hist)) / total if total else 0.0
    mse = sum((i * i) * n for i, n in enumerate(hist)) / total if total else 0.0
    rmse = math.sqrt(mse)
    diff_px = sum(hist[DIFF_THRESHOLD:])
    diff_ratio = diff_px / total if total else 0.0

    result["mae"] = round(mae, 3)
    result["rmse"] = round(rmse, 3)
    result["diff_pixel_ratio"] = round(diff_ratio, 5)
    result["ssim"] = _ssim_grayscale(a_gray, r_gray)

    if abs_diff_path is not None:
        abs_diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff.save(abs_diff_path)

    if diff_path is not None:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        mask = diff.point(lambda v: 255 if v >= DIFF_THRESHOLD else 0)
        base = Image.blend(
            r_gray.convert("RGB"),
            Image.new("RGB", r_rgb.size, "white"),
            0.65,
        )
        red = Image.new("RGB", r_rgb.size, (220, 30, 30))
        base.paste(red, mask=mask)
        base.save(diff_path)

    if overlay_path is not None:
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        ref_rgba = r_rgb.convert("RGBA")
        act_rgba = a_rgb.convert("RGBA")
        act_rgba.putalpha(110)
        out = Image.alpha_composite(ref_rgba, act_rgba)
        out.save(overlay_path)

    return result


def mean_channel_stats(img: Image.Image) -> dict:
    """Simple RGB mean stats (useful for blank-page diagnostics)."""
    rgb = img.convert("RGB")
    stat = ImageStat.Stat(rgb)
    return {"mean_rgb": [round(v, 2) for v in stat.mean]}
