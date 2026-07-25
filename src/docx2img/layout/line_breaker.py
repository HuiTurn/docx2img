"""Line breaking algorithm for paragraphs"""

import math
from typing import List, Tuple, Any, Optional
from PIL import ImageFont

from ..config import Config
from ..model.paragraph import Paragraph, RunProps
from ..font.manager import FontManager
from .tab_stop import TabStopResolver
from .math_layout import MathLayoutEngine
from .float_layout import FloatLayoutEngine, ExclusionZone
from ..model.enums import TabStopType


def _get_line_box_classes():
    """Lazy import to avoid circular dependency"""
    from .engine import LineBox, GlyphBox
    return LineBox, GlyphBox


class LineBreaker:
    """Line breaking algorithm

    Rules:
    1. English: Break at spaces/hyphens (word-level)
    2. CJK: Can break between any characters (char-level)
    3. Mixed: CJK chars can break, Latin words cannot break internally
    4. Punctuation restrictions:
       - Line start cannot have: ，。、；：！？）】》
       - Line end cannot have: （【《
    """

    CJK_RANGES = [
        (0x4E00, 0x9FFF),
        (0x3400, 0x4DBF),
        (0x3000, 0x303F),
        (0xFF00, 0xFFEF),
        (0x3040, 0x309F),
        (0x30A0, 0x30FF),
        (0xAC00, 0xD7AF),
    ]

    NO_START_CHARS = set("，。、；：！？）】》」』〉,.;:!?)］〕〗〙〛〉》」』】〕］＞％‰′″℃°")
    NO_END_CHARS = set("（【《「『〈(［〔〖〘〚〈《「『【〔［＜￥＄＠＃")

    def __init__(self, config: Config, font_manager: Optional[FontManager] = None):
        self.config = config
        self.font_manager = font_manager or FontManager(config)
        self.tab_resolver = TabStopResolver()
        self.math_layout = MathLayoutEngine(config, self.font_manager)
        self.float_layout = FloatLayoutEngine()

    def is_cjk(self, ch: str) -> bool:
        """Check if character is CJK"""
        if not ch:
            return False
        cp = ord(ch[0])
        return any(lo <= cp <= hi for lo, hi in self.CJK_RANGES)

    def can_break_before(self, ch: str) -> bool:
        """Whether this character may appear at line start"""
        return ch not in self.NO_START_CHARS

    def can_break_after(self, ch: str) -> bool:
        """Whether a break is allowed after this character"""
        return ch not in self.NO_END_CHARS

    def break_paragraph(
        self,
        para: Paragraph,
        available_width: float,
        px_per_pt: float,
        first_line_extra: float = 0.0,
        wrap_zones: Optional[List[ExclusionZone]] = None,
        grid_line_pitch_px: Optional[float] = None,
    ) -> List[Any]:
        """Break paragraph into LineBox objects.

        Args:
            para: Paragraph to break
            available_width: Available width in pixels (after left/right indent)
            px_per_pt: Pixels per point
            first_line_extra: Extra indent for first line in pixels
                (positive = first-line indent, negative = hanging)
            wrap_zones: Optional float exclusion zones in paragraph-local coords
            grid_line_pitch_px: Optional section baseline-grid pitch in pixels
        """
        LineBox, GlyphBox = _get_line_box_classes()
        lines: List[Any] = []
        zones = wrap_zones or []

        # Flatten runs into atomic tokens: (text, props, force_break, image_run, math)
        tokens: List[Tuple] = []
        for run in para.runs:
            if run.image:
                if run.image.wrap_type == "inline":
                    tokens.append(("", None, None, run.image, None))
            elif run.math:
                tokens.append(("", None, None, None, run.math))
            elif run.text and run.text.text:
                tokens.append((run.text.text, run.text.props, None, None, None))
            elif run.brk:
                tokens.append(("", None, run.brk.break_type, None, None))
            elif run.tab:
                tokens.append(("\t", None, None, None, None))

        if not tokens:
            return lines

        # Expand into measurable units (CJK char / Latin word / space / tab)
        units = self._tokenize(tokens, px_per_pt)

        current_units: List[dict] = []
        current_width = 0.0
        line_index = 0
        est_y = 0.0
        wrap_x = 0.0
        max_width = available_width - first_line_extra

        def _resolve_band(y: float, line_h: float, indent_extra: float) -> Tuple[float, float]:
            """Return (wrap_x_offset, max_width) for a horizontal band."""
            left = max(0.0, indent_extra)
            right = available_width
            if not zones:
                return left, max(1.0, right - left)
            segs = self.float_layout.available_segments(y, line_h, 0.0, available_width, zones)
            # Prefer the widest segment that starts at/after left indent
            candidates = [(a, b) for a, b in segs if b > left + 1.0]
            if not candidates:
                return left, 1.0
            a, b = max(candidates, key=lambda s: s[1] - max(s[0], left))
            start = max(a, left)
            return start, max(1.0, b - start)

        def _line_h_est() -> float:
            if current_units:
                return max(u.get("height", 14.0) for u in current_units) or 14.0
            return 14.0

        # Initial band
        wrap_x, max_width = _resolve_band(0.0, 14.0, first_line_extra)

        def flush_line(force: bool = False) -> None:
            nonlocal current_units, current_width, line_index, max_width, est_y, wrap_x
            if not current_units and not force:
                return
            line = self._units_to_line(
                current_units,
                para.props,
                px_per_pt,
                GlyphBox,
                LineBox,
                grid_line_pitch_px=grid_line_pitch_px,
            )
            line._wrap_x = wrap_x  # type: ignore[attr-defined]
            line._wrap_width = max_width  # type: ignore[attr-defined]
            lines.append(line)
            est_y += max(line.height, 1.0)
            current_units = []
            current_width = 0.0
            line_index += 1
            # Skip vertical bands fully blocked by topAndBottom / full-width zones
            for _ in range(32):
                wrap_x, max_width = _resolve_band(est_y, 14.0, 0.0)
                if max_width > 2.0:
                    break
                # Advance past overlapping zones
                next_y = est_y
                for z in zones:
                    if z.y_end > est_y and z.x_start <= 0 and z.x_end >= available_width:
                        next_y = max(next_y, z.y_end)
                if next_y <= est_y:
                    break
                est_y = next_y

        i = 0
        while i < len(units):
            unit = units[i]

            if unit.get("force_break") == "page":
                flush_line()
                # Represent page break as a marker line
                marker = LineBox()
                marker.height = 0
                marker.width = 0
                marker.glyphs = []
                marker._page_break = True  # type: ignore[attr-defined]
                lines.append(marker)
                i += 1
                continue

            if unit.get("force_break") == "line":
                flush_line(force=True)
                i += 1
                continue

            unit_w = unit["width"]

            # Resolve tab width based on current pen position (paragraph-local)
            if unit.get("is_tab"):
                content_right = wrap_x + max_width
                pen = wrap_x + current_width
                target, tab_stop = self.tab_resolver.resolve_tab_stop(
                    pen,
                    para.props.tab_stops,
                    para.props.default_tab_stop,
                    px_per_pt,
                    content_right=content_right,
                )
                follow_w = self._peek_width_after_tab(units, i + 1)
                tab_type = tab_stop.type if tab_stop is not None else TabStopType.LEFT
                if tab_type in (TabStopType.RIGHT, TabStopType.DECIMAL):
                    # Following text is right-aligned at the stop
                    unit_w = max(1.0, target - follow_w - pen)
                elif tab_type == TabStopType.CENTER:
                    unit_w = max(1.0, target - follow_w / 2.0 - pen)
                else:
                    unit_w = max(1.0, target - pen)
                # Keep tab + following page number on one line when possible
                if current_units and current_width + unit_w + follow_w > max_width + 0.5:
                    # Not enough room: wrap before tab (title on its own line)
                    flush_line()
                    continue
                unit = dict(unit)
                unit["width"] = unit_w
                unit["text"] = " "
                unit["is_tab"] = True
                unit["tab_leader"] = self._tab_leader_at(
                    pen, para.props.tab_stops, px_per_pt
                )
                unit["tab_follow_w"] = follow_w


            # Soft wrap when exceeding
            if current_units and current_width + unit_w > max_width:
                prev = current_units[-1]
                # Keep right-tab follower (page number) glued to the tab
                if prev.get("is_tab") and unit_w <= float(prev.get("tab_follow_w") or unit_w) + 1.0:
                    pass
                else:
                    # Try to find a legal break point respecting punctuation rules
                    break_at = self._find_break_index(current_units, unit)
                    if break_at is not None and break_at > 0:
                        keep = current_units[:break_at]
                        rest = current_units[break_at:]
                        current_units = keep
                        flush_line()
                        current_units = rest
                        current_width = sum(u["width"] for u in current_units)
                        continue
                    else:
                        flush_line()
                        continue

            # Avoid ending line with NO_END when next unit would wrap
            current_units.append(unit)
            current_width += unit_w
            i += 1

            # Speculative: if next unit won't fit and last char is NO_END, pull forward
            if i < len(units):
                nxt = units[i]
                if (
                    not nxt.get("force_break")
                    and current_width + nxt["width"] > max_width
                    and current_units
                    and not self.can_break_after(current_units[-1]["text"][-1:])
                ):
                    # Move last unit to next line with the following content
                    pulled = current_units.pop()
                    current_width -= pulled["width"]
                    if current_units:
                        flush_line()
                    current_units = [pulled]
                    current_width = pulled["width"]

            # Avoid starting next line with NO_START: push punctuation back if possible
            # Handled in _find_break_index when wrapping

        flush_line()
        return lines

    def _tokenize(
        self,
        tokens: List[Tuple],
        px_per_pt: float,
    ) -> List[dict]:
        """Convert run tokens into measurable wrap units."""
        units: List[dict] = []

        for item in tokens:
            text, props, force_break = item[0], item[1], item[2]
            image = item[3] if len(item) > 3 else None
            math_run = item[4] if len(item) > 4 else None

            if math_run is not None and math_run.ast is not None:
                size = (props.font_size if props else 12.0)
                mbox = self.math_layout.layout(math_run.ast, size)
                units.append({
                    "text": "",
                    "props": props,
                    "font": None,
                    "width": mbox.width,
                    "height": mbox.height,
                    "force_break": None,
                    "image": None,
                    "math_box": mbox,
                })
                continue

            if image is not None:
                from ..parse.units import Units
                from io import BytesIO
                from PIL import Image as PILImage

                w_px = Units.emu_to_px(image.width_emu, self.config.dpi) if image.width_emu else 0
                h_px = Units.emu_to_px(image.height_emu, self.config.dpi) if image.height_emu else 0
                pil_img = None
                if image.data:
                    try:
                        pil_img = PILImage.open(BytesIO(image.data))
                        if w_px <= 0 or h_px <= 0:
                            w_px, h_px = pil_img.size
                    except Exception:
                        pil_img = None
                if w_px <= 0:
                    w_px = 50
                if h_px <= 0:
                    h_px = 50
                units.append({
                    "text": "",
                    "props": props,
                    "font": None,
                    "width": float(w_px),
                    "height": float(h_px),
                    "force_break": None,
                    "image": pil_img,
                })
                continue

            if force_break:
                units.append({
                    "text": "",
                    "props": props,
                    "font": None,
                    "width": 0.0,
                    "height": 0.0,
                    "force_break": force_break,
                    "image": None,
                })
                continue

            if not text:
                continue

            props = props or RunProps()
            font_size_pt = props.font_size or 12.0

            if props.vertical_align in ("superscript", "subscript"):
                font_size_pt *= 0.65

            buf = ""
            buf_is_cjk: Optional[bool] = None

            def emit_buf():
                nonlocal buf, buf_is_cjk
                if not buf:
                    return
                for seg_text, font in self._segment_by_font(buf, props, font_size_pt, px_per_pt):
                    w, h = self._measure(seg_text, font, props, px_per_pt)
                    units.append({
                        "text": seg_text,
                        "props": props,
                        "font": font,
                        "width": w,
                        "height": h,
                        "force_break": None,
                        "image": None,
                    })
                buf = ""
                buf_is_cjk = None

            for ch in text:
                if ch == "\t":
                    emit_buf()
                    font = self._font_for_text(" ", props, font_size_pt, px_per_pt)
                    space_w, space_h = self._measure(" ", font, props, px_per_pt)
                    units.append({
                        "text": "\t",
                        "props": props,
                        "font": font,
                        "width": space_w * 4,  # placeholder; resolved during break
                        "height": space_h,
                        "force_break": None,
                        "image": None,
                        "is_tab": True,
                    })
                    continue

                if ch == " ":
                    emit_buf()
                    font = self._font_for_text(" ", props, font_size_pt, px_per_pt)
                    w, h = self._measure(" ", font, props, px_per_pt)
                    units.append({
                        "text": " ",
                        "props": props,
                        "font": font,
                        "width": w,
                        "height": h,
                        "force_break": None,
                        "image": None,
                    })
                    continue

                ch_cjk = self.is_cjk(ch)
                if buf_is_cjk is None:
                    buf = ch
                    buf_is_cjk = ch_cjk
                elif ch_cjk:
                    emit_buf()
                    buf = ch
                    buf_is_cjk = True
                    emit_buf()
                else:
                    if buf_is_cjk:
                        emit_buf()
                        buf = ch
                        buf_is_cjk = False
                    else:
                        if ch == "-":
                            buf += ch
                            emit_buf()
                        else:
                            buf += ch

            emit_buf()

        return units

    def _find_break_index(self, current_units: List[dict], next_unit: dict) -> Optional[int]:
        """Find index in current_units where we should break before wrapping next_unit.

        Prefer breaking after spaces / CJK / hyphens. Respect NO_START for next line
        and NO_END for end of current line.
        """
        # Default: break at end of current_units (before next_unit)
        # But if next_unit cannot start a line, try to pull it onto current... 
        # Here we decide where within current_units to split when overflow already happened.

        # Walk backwards looking for a legal break opportunity
        for i in range(len(current_units) - 1, 0, -1):
            prev = current_units[i - 1]
            curr = current_units[i]
            prev_ch = prev["text"][-1:] if prev["text"] else ""
            curr_ch = curr["text"][:1] if curr["text"] else ""

            # Can break after prev?
            if not self.can_break_after(prev_ch):
                continue
            # Can curr start a line?
            if not self.can_break_before(curr_ch):
                continue
            # Prefer break after whitespace or CJK or hyphen
            if (
                prev["text"].endswith(" ")
                or prev["text"].endswith("-")
                or self.is_cjk(prev_ch)
                or curr["text"].startswith(" ")
            ):
                return i

        # Fallback: break before last unit if legal
        if len(current_units) > 1:
            last = current_units[-1]
            prev = current_units[-2]
            if self.can_break_after(prev["text"][-1:] if prev["text"] else "") and self.can_break_before(
                last["text"][:1] if last["text"] else ""
            ):
                return len(current_units) - 1

        return None

    def _units_to_line(
        self,
        units,
        para_props,
        px_per_pt,
        GlyphBox,
        LineBox,
        grid_line_pitch_px: Optional[float] = None,
    ):
        """Build a LineBox from wrap units."""
        line = LineBox()
        x = 0.0
        max_ascent = 0.0
        max_descent = 0.0
        max_height = 0.0
        max_line_gap = 0.0
        has_text = False

        for unit in units:
            text = unit["text"]
            img = unit.get("image")
            mbox = unit.get("math_box")
            if mbox is not None:
                glyph = GlyphBox(
                    text="",
                    x=x,
                    y=0.0,
                    width=unit["width"],
                    height=unit["height"],
                    font=None,
                    props=unit.get("props"),
                    math_box=mbox,
                )
                line.glyphs.append(glyph)
                x += unit["width"]
                max_height = max(max_height, unit["height"])
                max_ascent = max(max_ascent, unit["height"] * 0.8)
                continue

            if img is not None:
                glyph = GlyphBox(
                    text="",
                    x=x,
                    y=0.0,
                    width=unit["width"],
                    height=unit["height"],
                    font=None,
                    props=unit.get("props"),
                    image=img,
                )
                line.glyphs.append(glyph)
                x += unit["width"]
                max_height = max(max_height, unit["height"])
                max_ascent = max(max_ascent, unit["height"])
                continue

            if not text and not unit.get("force_break"):
                continue
            if text == "\t":
                text = " "
            # Tab leaders: fill with dots/underscores visually via text
            leader = unit.get("tab_leader")
            if leader and leader != "none" and unit.get("is_tab"):
                text = self._leader_fill(leader, unit["width"], unit.get("font"))

            font = unit["font"]
            props = unit["props"]
            w = unit["width"]
            h = unit["height"]
            has_text = True

            # Tab leaders: plain black dots — no hyperlink underline/color
            if unit.get("is_tab") and props is not None:
                needs_plain = getattr(props, "underline", False) or (
                    getattr(props, "color", None) not in (None, (0, 0, 0))
                )
                if needs_plain:
                    import copy
                    props = copy.copy(props)
                    props.underline = False
                    props.color = (0, 0, 0)

            ascent = h * 0.8
            descent = h * 0.2
            if font and hasattr(font, "getmetrics"):
                try:
                    metrics = font.getmetrics()
                    ascent = float(metrics[0])
                    descent = float(metrics[1])
                except Exception:
                    pass

            # LibreOffice (and Word) include the font's typographic line gap
            # in the natural line height for auto line spacing.  PIL's
            # getmetrics() only reports ascent+descent, so we look up the hhea
            # lineGap explicitly and add it to the line's natural height.
            line_gap = 0.0
            if props is not None and self.font_manager is not None:
                size_pt = props.font_size or 12.0
                if props.vertical_align in ("superscript", "subscript"):
                    size_pt *= 0.65
                name = (
                    props.font_ascii
                    or props.font_h_ansi
                    or props.font_east_asia
                    or self.config.default_font_ascii
                )
                if name:
                    try:
                        _, _, line_gap = self.font_manager.get_font_metrics(
                            name, size_pt * px_per_pt, bool(props.bold), bool(props.italic)
                        )
                    except Exception:
                        line_gap = 0.0

            glyph = GlyphBox(
                text=text,
                x=x,
                y=0.0,
                width=w,
                height=h,
                font=font,
                props=props,
            )
            line.glyphs.append(glyph)
            x += w
            max_ascent = max(max_ascent, ascent)
            max_descent = max(max_descent, descent)
            max_height = max(max_height, h)
            max_line_gap = max(max_line_gap, line_gap)

        line.width = x
        image_only = not has_text and any(g.image is not None for g in line.glyphs)
        if image_only:
            # Inline images dominate the line: Word/LibreOffice use the image
            # height directly without adding artificial text descent or applying
            # the line-spacing multiplier to the whole image.
            line.ascent = max_height
            line.descent = 0.0
            natural = max_height
        else:
            line.ascent = max_ascent or max_height * 0.8
            line.descent = max_descent or max_height * 0.2
            # Add the font's typographic line gap to the natural line height.
            # LibreOffice includes this leading in the line box for auto line
            # spacing, which is why dense text documents match golden better
            # with the gap included than with PIL's ascent+descent alone.
            natural = line.ascent + line.descent + max_line_gap

        # Line height from paragraph spacing rules
        line.height = self._line_height(
            para_props,
            natural,
            px_per_pt,
            image_only=image_only,
            grid_line_pitch_px=grid_line_pitch_px,
        )
        return line

    def _line_height(
        self,
        para_props,
        natural_height: float,
        px_per_pt: float,
        image_only: bool = False,
        grid_line_pitch_px: Optional[float] = None,
    ) -> float:
        """Compute line box height from paragraph spacing.

        LibreOffice (our golden reference) interprets ``auto`` line spacing as
        a direct multiple of the reference font size.  Single spacing equals
        the font size, so ``w:line=276`` (1.15) yields ``1.15 × font_size``.
        Word adds extra built-in leading (~1.18 × font_size for single), but
        we deliberately follow LibreOffice here to match the visual-regression
        golden references.

        ``exact`` and ``atLeast`` are absolute values in points.  A line that
        contains only an inline image uses the image height directly.
        """
        rule = getattr(para_props, "line_spacing_rule", "auto") or "auto"
        if image_only and rule == "auto":
            resolved = natural_height
        elif rule == "exact" and para_props.line_spacing_exact is not None:
            resolved = para_props.line_spacing_exact * px_per_pt
        elif rule == "atLeast" and para_props.line_spacing_exact is not None:
            resolved = max(natural_height, para_props.line_spacing_exact * px_per_pt)
        else:
            # auto: multiplier (default 1.0 → single spacing)
            #
            # LibreOffice applies ``mult`` only to the font-size-based minimum,
            # not to the font-metric natural height.  This means:
            #   max(natural_height, font_size * mult)
            # NOT:
            #   max(natural_height * mult, font_size * mult)
            # The former matches LO's golden-reference output; the latter
            # over-inflates line height when mult > 1.0 (e.g. docDefaults
            # line=276 → 1.15x caused large-document to render 52 pages
            # instead of LO's 50).
            mult = para_props.line_spacing if para_props.line_spacing else 1.0
            # Use the paragraph-mark font size as the reference for leading.
            ref_font_size = getattr(para_props, "mark_font_size", None) or 12.0
            word_single = ref_font_size * px_per_pt
            if mult <= 1.0 + 1e-6:
                resolved = max(natural_height, word_single)
            else:
                resolved = max(natural_height, word_single * mult)

        # A section document grid fixes baselines at linePitch intervals.
        # Snap the resolved line box upward to a whole grid interval; a
        # larger line therefore occupies two (or more) intervals instead of
        # drifting subsequent baselines off-grid.
        if (
            grid_line_pitch_px
            and grid_line_pitch_px > 0
            and not image_only
            and rule != "exact"
        ):
            intervals = max(
                1,
                int(math.ceil((resolved - 1e-6) / grid_line_pitch_px)),
            )
            return intervals * grid_line_pitch_px
        return resolved

    def _tab_leader_at(self, current_x: float, tab_stops, px_per_pt: float) -> str:
        stops = sorted(tab_stops, key=lambda t: t.position) if tab_stops else []
        for ts in stops:
            if ts.position * px_per_pt > current_x + 0.5:
                return ts.leader or "none"
        return "none"

    def _peek_width_after_tab(self, units: List[dict], start: int) -> float:
        """Width of content glued to a right/center tab (e.g. TOC page number)."""
        if start >= len(units):
            return 0.0
        u = units[start]
        if u.get("force_break") or u.get("is_tab"):
            return 0.0
        return float(u.get("width") or 0.0)

    def _leader_fill(self, leader: str, width: float, font) -> str:
        """Fill a tab gap with a Word-like leader pattern.

        Dotted leaders use ". " (dot + space) rather than packed periods so
        TOC lines match print layout more closely.
        """
        if not font or width <= 0:
            return " "
        if leader == "dot":
            unit = ". "
        elif leader == "middleDot":
            unit = "· "
        elif leader == "hyphen":
            unit = "- "
        elif leader == "underscore":
            unit = "_"
        else:
            return " "
        try:
            uw = float(font.getlength(unit)) if hasattr(font, "getlength") else 0.0
            if uw <= 0:
                bbox = font.getbbox(unit)
                uw = float(bbox[2] - bbox[0])
        except Exception:
            uw = 8.0
        uw = max(1.0, uw)
        n = max(1, int(width / uw))
        filled = unit * n
        # Trim trailing space so the page number sits flush
        return filled.rstrip(" ") if leader != "underscore" else filled[:n]

    def _font_for_text(
        self, text: str, props: RunProps, font_size_pt: float, px_per_pt: float
    ) -> ImageFont.ImageFont:
        size_px = max(1.0, font_size_pt * px_per_pt)
        ch = text[0] if text else " "
        return self.font_manager.get_font_for_char(ch, props, size_px)

    def _segment_by_font(
        self, text: str, props: RunProps, font_size_pt: float, px_per_pt: float
    ):
        """Split text into (segment, font) where each segment shares one covered font."""
        size_px = max(1.0, font_size_pt * px_per_pt)
        if not text:
            return []
        segments = []
        cur = ""
        cur_font = None
        cur_path = None
        for ch in text:
            font = self.font_manager.get_font_for_char(ch, props, size_px)
            path = (getattr(font, "path", None), getattr(font, "index", 0), getattr(font, "size", None))
            if cur_font is None:
                cur_font = font
                cur_path = path
                cur = ch
            elif path == cur_path:
                cur += ch
            else:
                segments.append((cur, cur_font))
                cur, cur_font, cur_path = ch, font, path
        if cur:
            segments.append((cur, cur_font))
        return segments

    def _measure(
        self, text: str, font: ImageFont.ImageFont, props: RunProps, px_per_pt: float
    ) -> Tuple[float, float]:
        if not text:
            return 0.0, 0.0
        try:
            bbox = font.getbbox(text)
            w = float(bbox[2] - bbox[0])
            h = float(bbox[3] - bbox[1])
        except Exception:
            w = len(text) * (props.font_size if props else 12.0) * px_per_pt * 0.5
            h = (props.font_size if props else 12.0) * px_per_pt

        # Character width scaling (w:w, percentage)
        if props and props.scale and props.scale != 100:
            w *= props.scale / 100.0

        # Character spacing
        if props and props.spacing:
            w += props.spacing * px_per_pt * max(0, len(text) - 1)

        return w, h
