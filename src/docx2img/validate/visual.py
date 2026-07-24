"""Visual validation helpers for rendered pages / glyphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from collections import Counter

from PIL import Image, ImageDraw


@dataclass
class GlyphIssue:
    char: str
    codepoint: str
    font_path: Optional[str]
    page: int
    reason: str


@dataclass
class VisualReport:
    pages: int = 0
    glyphs_checked: int = 0
    missing_glyphs: List[GlyphIssue] = field(default_factory=list)
    blank_pages: List[int] = field(default_factory=list)
    sparse_pages: List[int] = field(default_factory=list)
    fallback_count: int = 0
    unresolved_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.missing_glyphs and self.unresolved_count == 0

    def summary(self) -> str:
        miss = Counter(i.char for i in self.missing_glyphs)
        top = ", ".join(f"{c!r}×{n}" for c, n in miss.most_common(8)) or "none"
        return (
            f"pages={self.pages} glyphs={self.glyphs_checked} "
            f"missing={len(self.missing_glyphs)} [{top}] "
            f"fallback={self.fallback_count} unresolved={self.unresolved_count} "
            f"blank={self.blank_pages} sparse={self.sparse_pages}"
        )


def _nonwhite_ratio(img: Image.Image, threshold: int = 250) -> float:
    px = list(img.getdata())
    if not px:
        return 0.0
    nw = 0
    for p in px:
        v = p[0] if isinstance(p, tuple) else p
        if v < threshold:
            nw += 1
    return nw / len(px)


def validate_pages(
    pages_layout,
    images: List[Image.Image],
    font_manager=None,
    *,
    blank_ratio: float = 0.002,
    sparse_ratio: float = 0.005,
) -> VisualReport:
    """Validate layout glyphs against font cmap + page ink density."""
    report = VisualReport(pages=len(images))

    if font_manager is not None:
        for ch, req, used, path in font_manager._missing_log:
            if used is None:
                report.unresolved_count += 1
            else:
                report.fallback_count += 1

    for pi, page in enumerate(pages_layout or []):
        for block in getattr(page, "blocks", []) or []:
            for line in getattr(block, "lines", []) or []:
                for g in getattr(line, "glyphs", []) or []:
                    text = g.text or ""
                    if not text.strip() or g.image is not None or getattr(g, "math_box", None):
                        continue
                    font = g.font
                    for ch in text:
                        if ch.isspace():
                            continue
                        report.glyphs_checked += 1
                        if font_manager is not None and not font_manager.font_has_char(font, ch):
                            report.missing_glyphs.append(GlyphIssue(
                                char=ch,
                                codepoint=hex(ord(ch)),
                                font_path=getattr(font, "path", None),
                                page=pi + 1,
                                reason="cmap_miss",
                            ))

    for i, img in enumerate(images):
        ratio = _nonwhite_ratio(img)
        if ratio < blank_ratio:
            report.blank_pages.append(i + 1)
        elif ratio < sparse_ratio and img.size[1] > 400:
            report.sparse_pages.append(i + 1)

    return report


def validate_docx(docx_path, config=None, max_pages: Optional[int] = None) -> VisualReport:
    """End-to-end visual validation for one docx."""
    from ..config import Config
    from ..unpack.unpacker import Unpacker
    from ..parse.document import DocumentParser
    from ..layout.engine import LayoutEngine
    from ..render.canvas import RenderCanvas

    if config is None:
        config = Config(dpi=96)
    package = Unpacker(docx_path).unpack()
    model = DocumentParser(package, config).parse()
    engine = LayoutEngine(model, config)
    engine.font_manager.clear_missing_log()
    pages = engine.layout()
    if max_pages is not None:
        pages = pages[:max_pages]
    images = RenderCanvas(config).render_pages(pages)
    return validate_pages(pages, images, engine.font_manager)
