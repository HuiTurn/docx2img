"""Math layout — compute boxes for OMML AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Any

from PIL import ImageFont

from ..config import Config
from ..font.manager import FontManager
from ..model.math_ast import (
    MathNode, MathChar, MathRunSeq, MathFrac, MathRad, MathSup, MathSub,
    MathSubSup, MathNary, MathDelim, MathMatrix, MathFunc, MathBar,
    MathAccent, MathBorderBox, MathLimit,
)


@dataclass
class MathBox:
    x: float = 0.0
    y: float = 0.0  # top
    width: float = 0.0
    height: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0
    # drawable parts
    texts: List[dict] = field(default_factory=list)  # {text,x,y,font,italic}
    lines: List[dict] = field(default_factory=list)  # {x1,y1,x2,y2,width}
    children: List["MathBox"] = field(default_factory=list)


class MathLayoutEngine:
    def __init__(self, config: Config, font_manager: Optional[FontManager] = None):
        self.config = config
        self.font_manager = font_manager or FontManager(config)

    def layout(self, node: MathNode, base_size_pt: float = 12.0) -> MathBox:
        px = self.config.px_per_pt
        return self._layout(node, base_size_pt * px)

    def _layout(self, node: Optional[MathNode], size_px: float) -> MathBox:
        if node is None:
            return MathBox()
        if isinstance(node, MathChar):
            return self._char(node, size_px)
        if isinstance(node, MathRunSeq):
            return self._seq(node, size_px)
        if isinstance(node, MathFrac):
            return self._frac(node, size_px)
        if isinstance(node, MathRad):
            return self._rad(node, size_px)
        if isinstance(node, MathBar):
            return self._bar(node, size_px)
        if isinstance(node, MathAccent):
            return self._accent(node, size_px)
        if isinstance(node, MathBorderBox):
            return self._border_box(node, size_px)
        if isinstance(node, MathLimit):
            return self._limit(node, size_px)
        if isinstance(node, MathSup):
            return self._sup(node, size_px)
        if isinstance(node, MathSub):
            return self._sub(node, size_px)
        if isinstance(node, MathSubSup):
            return self._subsup(node, size_px)
        if isinstance(node, MathNary):
            return self._nary(node, size_px)
        if isinstance(node, MathDelim):
            return self._delim(node, size_px)
        if isinstance(node, MathMatrix):
            return self._matrix(node, size_px)
        if isinstance(node, MathFunc):
            return self._func(node, size_px)
        return MathBox()

    def _font(self, size_px: float, italic: bool = False, bold: bool = False):
        return self.font_manager.get_font(
            "Times New Roman", max(1.0, size_px), bold, italic
        )

    def _char(self, node: MathChar, size_px: float) -> MathBox:
        italic = node.style in ("i", "bi")
        bold = node.style in ("b", "bi")
        font = self._font(size_px, italic, bold)
        try:
            bbox = font.getbbox(node.char)
            w = float(bbox[2] - bbox[0])
            h = float(bbox[3] - bbox[1])
            ascent = float(font.getmetrics()[0]) if hasattr(font, "getmetrics") else h * 0.8
        except Exception:
            w, h, ascent = size_px * 0.5, size_px, size_px * 0.8
        box = MathBox(width=w, height=h, ascent=ascent, descent=h - ascent)
        box.texts.append({"text": node.char, "x": 0, "y": 0, "font": font})
        return box

    def _seq(self, node: MathRunSeq, size_px: float) -> MathBox:
        boxes = [self._layout(c, size_px) for c in node.children]
        return self._hstack(boxes)

    def _hstack(self, boxes: List[MathBox], gap: float = 0.0) -> MathBox:
        if not boxes:
            return MathBox()
        ascent = max(b.ascent for b in boxes)
        descent = max(b.descent for b in boxes)
        x = 0.0
        out = MathBox(ascent=ascent, descent=descent, height=ascent + descent)
        for b in boxes:
            # Align baselines
            dy = ascent - b.ascent
            for t in b.texts:
                out.texts.append({**t, "x": t["x"] + x, "y": t["y"] + dy})
            for ln in b.lines:
                out.lines.append({
                    **ln,
                    "x1": ln["x1"] + x, "x2": ln["x2"] + x,
                    "y1": ln["y1"] + dy, "y2": ln["y2"] + dy,
                })
            for ch in b.children:
                ch.x += x
                ch.y += dy
                out.children.append(ch)
            x += b.width + gap
        out.width = x - gap if boxes else 0
        return out

    def _frac(self, node: MathFrac, size_px: float) -> MathBox:
        num = self._layout(node.numerator, size_px * 0.9)
        den = self._layout(node.denominator, size_px * 0.9)
        gap = size_px * 0.15
        rule = max(1.0, size_px * 0.06)
        width = max(num.width, den.width) + size_px * 0.2
        out = MathBox(width=width)
        # Place numerator
        nx = (width - num.width) / 2
        for t in num.texts:
            out.texts.append({**t, "x": t["x"] + nx, "y": t["y"]})
        for ln in num.lines:
            out.lines.append({
                **ln,
                "x1": ln["x1"] + nx, "x2": ln["x2"] + nx,
            })
        ny = num.height
        # Rule
        out.lines.append({
            "x1": size_px * 0.05, "y1": ny + gap,
            "x2": width - size_px * 0.05, "y2": ny + gap,
            "width": rule,
        })
        # Denominator
        dy = ny + gap * 2 + rule
        dx = (width - den.width) / 2
        for t in den.texts:
            out.texts.append({**t, "x": t["x"] + dx, "y": t["y"] + dy})
        for ln in den.lines:
            out.lines.append({
                **ln,
                "x1": ln["x1"] + dx, "x2": ln["x2"] + dx,
                "y1": ln["y1"] + dy, "y2": ln["y2"] + dy,
            })
        out.height = dy + den.height
        out.ascent = ny + gap
        out.descent = out.height - out.ascent
        return out

    def _rad(self, node: MathRad, size_px: float) -> MathBox:
        rad = self._layout(node.radicand, size_px)
        deg = self._layout(node.degree, size_px * 0.55) if node.degree else MathBox()
        tick = size_px * 0.55
        out = MathBox()
        # Degree
        for t in deg.texts:
            out.texts.append({**t, "x": t["x"], "y": t["y"]})
        # Radical symbol as text
        font = self._font(size_px * 1.1)
        sym = "√"
        try:
            sw = float(font.getbbox(sym)[2] - font.getbbox(sym)[0])
        except Exception:
            sw = size_px * 0.7
        sx = max(deg.width - sw * 0.3, 0)
        out.texts.append({"text": sym, "x": sx, "y": 0, "font": font})
        # Overbar
        bar_y = size_px * 0.1
        content_x = sx + sw * 0.85
        for t in rad.texts:
            out.texts.append({**t, "x": t["x"] + content_x, "y": t["y"] + size_px * 0.15})
        for ln in rad.lines:
            out.lines.append({
                **ln,
                "x1": ln["x1"] + content_x, "x2": ln["x2"] + content_x,
                "y1": ln["y1"] + size_px * 0.15, "y2": ln["y2"] + size_px * 0.15,
            })
        out.lines.append({
            "x1": content_x, "y1": bar_y,
            "x2": content_x + rad.width + size_px * 0.1, "y2": bar_y,
            "width": max(1.0, size_px * 0.07),
        })
        out.width = content_x + rad.width + size_px * 0.15
        out.height = max(rad.height + size_px * 0.25, size_px * 1.2, deg.height)
        out.ascent = out.height * 0.8
        out.descent = out.height - out.ascent
        return out

    def _bar(self, node: MathBar, size_px: float) -> MathBox:
        body = self._layout(node.body, size_px)
        bottom = node.position == "bottom"
        gap = max(1.0, size_px * (0.56 if bottom else 0.08))
        rule = max(1.0, size_px * 0.06)
        offset = gap + rule
        body_y = 0.0 if bottom else offset
        line_y = body.height + gap if bottom else rule / 2.0
        out = MathBox(
            width=body.width,
            height=body.height + offset,
            ascent=body.ascent + (0.0 if bottom else offset),
            descent=body.descent + (offset if bottom else 0.0),
        )
        for text in body.texts:
            out.texts.append({**text, "y": text["y"] + body_y})
        for line in body.lines:
            out.lines.append({
                **line,
                "y1": line["y1"] + body_y,
                "y2": line["y2"] + body_y,
            })
        out.lines.append({
            "x1": 0.0,
            "y1": line_y,
            "x2": body.width,
            "y2": line_y,
            "width": rule,
        })
        return out

    def _accent(self, node: MathAccent, size_px: float) -> MathBox:
        body = self._layout(node.body, size_px)
        accent = self._char(MathChar(node.char, style="p"), size_px * 0.75)
        width = max(body.width, accent.width)
        body_x = (width - body.width) / 2.0
        accent_x = (width - accent.width) / 2.0
        out = MathBox(
            width=width,
            height=max(body.height, accent.height),
            ascent=body.ascent,
            descent=body.descent,
        )
        for text in accent.texts:
            out.texts.append({
                **text,
                "x": text["x"] + accent_x,
            })
        for text in body.texts:
            out.texts.append({
                **text,
                "x": text["x"] + body_x,
            })
        for line in body.lines:
            out.lines.append({
                **line,
                "x1": line["x1"] + body_x,
                "x2": line["x2"] + body_x,
            })
        return out

    def _border_box(self, node: MathBorderBox, size_px: float) -> MathBox:
        body = self._layout(node.body, size_px)
        padding_x = max(1.0, size_px * 0.20)
        border_top = max(1.0, size_px * 0.20)
        inner_top = max(1.0, size_px * 0.20)
        inner_bottom = max(1.0, size_px * 0.16)
        rule = max(1.0, size_px * 0.06)

        ink_top = 0.0
        ink_bottom = body.height
        if body.texts:
            bounds = []
            for text in body.texts:
                try:
                    bbox = text["font"].getbbox(text["text"])
                    bounds.append((
                        text["y"] + bbox[1],
                        text["y"] + bbox[3],
                    ))
                except Exception:
                    bounds.append((text["y"], text["y"] + body.height))
            ink_top = min(bound[0] for bound in bounds)
            ink_bottom = max(bound[1] for bound in bounds)
        if body.lines:
            ink_top = min(
                ink_top,
                min(min(line["y1"], line["y2"]) for line in body.lines),
            )
            ink_bottom = max(
                ink_bottom,
                max(max(line["y1"], line["y2"]) for line in body.lines),
            )

        body_y = border_top + inner_top - ink_top
        border_bottom = body_y + ink_bottom + inner_bottom
        width = body.width + padding_x * 2.0
        height = border_bottom
        out = MathBox(
            width=width,
            height=height,
            ascent=body.ascent + body_y,
            descent=height - body.ascent - body_y,
        )
        for text in body.texts:
            out.texts.append({
                **text,
                "x": text["x"] + padding_x,
                "y": text["y"] + body_y,
            })
        for line in body.lines:
            out.lines.append({
                **line,
                "x1": line["x1"] + padding_x,
                "x2": line["x2"] + padding_x,
                "y1": line["y1"] + body_y,
                "y2": line["y2"] + body_y,
            })

        def add_line(x1: float, y1: float, x2: float, y2: float) -> None:
            out.lines.append({
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "width": rule,
            })

        if not node.hide_top:
            add_line(0.0, border_top, width, border_top)
        if not node.hide_bottom:
            add_line(0.0, border_bottom, width, border_bottom)
        if not node.hide_left:
            add_line(0.0, border_top, 0.0, border_bottom)
        if not node.hide_right:
            add_line(width, border_top, width, border_bottom)
        if node.strike_horizontal:
            middle_y = (border_top + border_bottom) / 2.0
            add_line(0.0, middle_y, width, middle_y)
        if node.strike_vertical:
            add_line(width / 2.0, border_top, width / 2.0, border_bottom)
        if node.strike_bottom_left_top_right:
            add_line(0.0, border_bottom, width, border_top)
        if node.strike_top_left_bottom_right:
            add_line(0.0, border_top, width, border_bottom)
        return out

    def _limit(self, node: MathLimit, size_px: float) -> MathBox:
        base = self._layout(node.base, size_px)
        value = self._layout(node.limit, size_px * 0.70)
        gap = max(0.0, size_px * 0.10)
        width = max(base.width, value.width)
        base_x = (width - base.width) / 2.0
        value_x = (width - value.width) / 2.0
        upper = node.position == "upper"
        value_y = 0.0 if upper else base.height + gap
        base_y = value.height + gap if upper else 0.0
        height = max(
            base_y + base.height,
            value_y + value.height,
        )
        out = MathBox(
            width=width,
            height=height,
            ascent=base.ascent + base_y,
            descent=height - base.ascent - base_y,
        )

        def append_box(box: MathBox, dx: float, dy: float) -> None:
            for text in box.texts:
                out.texts.append({
                    **text,
                    "x": text["x"] + dx,
                    "y": text["y"] + dy,
                })
            for line in box.lines:
                out.lines.append({
                    **line,
                    "x1": line["x1"] + dx,
                    "x2": line["x2"] + dx,
                    "y1": line["y1"] + dy,
                    "y2": line["y2"] + dy,
                })

        append_box(base, base_x, base_y)
        append_box(value, value_x, value_y)
        return out

    def _sup(self, node: MathSup, size_px: float) -> MathBox:
        base = self._layout(node.base, size_px)
        sup = self._layout(node.superscript, size_px * 0.65)
        out = MathBox()
        for t in base.texts:
            out.texts.append({**t})
        for ln in base.lines:
            out.lines.append({**ln})
        lift = size_px * 0.35
        for t in sup.texts:
            out.texts.append({**t, "x": t["x"] + base.width, "y": t["y"] - lift})
        for ln in sup.lines:
            out.lines.append({
                **ln,
                "x1": ln["x1"] + base.width, "x2": ln["x2"] + base.width,
                "y1": ln["y1"] - lift, "y2": ln["y2"] - lift,
            })
        out.width = base.width + sup.width
        out.height = max(base.height, sup.height + lift)
        out.ascent = max(base.ascent, lift + sup.height * 0.5)
        out.descent = out.height - out.ascent
        return out

    def _sub(self, node: MathSub, size_px: float) -> MathBox:
        base = self._layout(node.base, size_px)
        sub = self._layout(node.subscript, size_px * 0.65)
        out = MathBox()
        for t in base.texts:
            out.texts.append({**t})
        for ln in base.lines:
            out.lines.append({**ln})
        drop = size_px * 0.25
        for t in sub.texts:
            out.texts.append({**t, "x": t["x"] + base.width, "y": t["y"] + drop})
        for ln in sub.lines:
            out.lines.append({
                **ln,
                "x1": ln["x1"] + base.width, "x2": ln["x2"] + base.width,
                "y1": ln["y1"] + drop, "y2": ln["y2"] + drop,
            })
        out.width = base.width + sub.width
        out.height = max(base.height, sub.height + drop)
        out.ascent = base.ascent
        out.descent = max(base.descent, drop + sub.height * 0.5)
        return out

    def _subsup(self, node: MathSubSup, size_px: float) -> MathBox:
        # Approximate as sup then conceptually share base — layout base once
        base = self._layout(node.base, size_px)
        sub = self._layout(node.subscript, size_px * 0.65)
        sup = self._layout(node.superscript, size_px * 0.65)
        out = MathBox()
        for t in base.texts:
            out.texts.append({**t})
        lift, drop = size_px * 0.35, size_px * 0.25
        for t in sup.texts:
            out.texts.append({**t, "x": t["x"] + base.width, "y": t["y"] - lift})
        for t in sub.texts:
            out.texts.append({**t, "x": t["x"] + base.width, "y": t["y"] + drop})
        out.width = base.width + max(sub.width, sup.width)
        out.height = max(base.height, sup.height + lift, sub.height + drop)
        out.ascent = max(base.ascent, lift + sup.height * 0.5)
        out.descent = max(base.descent, drop + sub.height * 0.5)
        return out

    def _nary(self, node: MathNary, size_px: float) -> MathBox:
        big = self._layout(MathChar(node.char, style="p"), size_px * 1.6)
        lo = self._layout(node.lower, size_px * 0.55)
        up = self._layout(node.upper, size_px * 0.55)
        body = self._layout(node.body, size_px)
        op_w = max(big.width, lo.width, up.width)
        out = MathBox()
        # upper
        ux = (op_w - up.width) / 2
        for t in up.texts:
            out.texts.append({**t, "x": t["x"] + ux, "y": t["y"]})
        # operator
        oy = up.height
        ox = (op_w - big.width) / 2
        for t in big.texts:
            out.texts.append({**t, "x": t["x"] + ox, "y": t["y"] + oy})
        # lower
        ly = oy + big.height
        lx = (op_w - lo.width) / 2
        for t in lo.texts:
            out.texts.append({**t, "x": t["x"] + lx, "y": t["y"] + ly})
        # body
        by = up.height + (big.height - body.ascent) * 0.3
        for t in body.texts:
            out.texts.append({**t, "x": t["x"] + op_w + size_px * 0.15, "y": t["y"] + by})
        for ln in body.lines:
            out.lines.append({
                **ln,
                "x1": ln["x1"] + op_w + size_px * 0.15,
                "x2": ln["x2"] + op_w + size_px * 0.15,
                "y1": ln["y1"] + by, "y2": ln["y2"] + by,
            })
        out.width = op_w + size_px * 0.15 + body.width
        out.height = max(ly + lo.height, by + body.height)
        out.ascent = out.height * 0.7
        out.descent = out.height - out.ascent
        return out

    def _delim(self, node: MathDelim, size_px: float) -> MathBox:
        body = self._layout(node.body, size_px)
        h = max(body.height, size_px)
        font = self._font(h * 0.95)
        left = self._char(MathChar(node.open_chr, "p"), h * 0.9)
        right = self._char(MathChar(node.close_chr, "p"), h * 0.9)
        # Force fonts
        left.texts = [{"text": node.open_chr, "x": 0, "y": 0, "font": font}]
        right.texts = [{"text": node.close_chr, "x": 0, "y": 0, "font": font}]
        try:
            left.width = float(font.getbbox(node.open_chr)[2] - font.getbbox(node.open_chr)[0])
            right.width = float(font.getbbox(node.close_chr)[2] - font.getbbox(node.close_chr)[0])
        except Exception:
            pass
        left.height = right.height = h
        left.ascent = right.ascent = body.ascent
        return self._hstack([left, body, right], gap=size_px * 0.05)

    def _matrix(self, node: MathMatrix, size_px: float) -> MathBox:
        grid = [[self._layout(c, size_px) for c in row] for row in node.rows]
        if not grid:
            return MathBox()
        ncols = max(len(r) for r in grid)
        col_w = [0.0] * ncols
        row_h = [0.0] * len(grid)
        for r, row in enumerate(grid):
            for c, cell in enumerate(row):
                col_w[c] = max(col_w[c], cell.width)
                row_h[r] = max(row_h[r], cell.height)
        pad = size_px * 0.25
        out = MathBox()
        y = 0.0
        for r, row in enumerate(grid):
            x = 0.0
            for c, cell in enumerate(row):
                for t in cell.texts:
                    out.texts.append({**t, "x": t["x"] + x, "y": t["y"] + y})
                x += col_w[c] + pad
            y += row_h[r] + pad
        out.width = sum(col_w) + pad * (ncols - 1)
        out.height = y - pad
        out.ascent = out.height * 0.8
        out.descent = out.height - out.ascent
        return out

    def _func(self, node: MathFunc, size_px: float) -> MathBox:
        name = MathRunSeq(children=[MathChar(c, "p") for c in node.name])
        name_box = self._layout(name, size_px)
        arg = self._layout(node.arg, size_px)
        return self._hstack([name_box, arg], gap=size_px * 0.1)
