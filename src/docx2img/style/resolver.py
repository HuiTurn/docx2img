"""Style inheritance resolver."""

from __future__ import annotations

import copy
from typing import Dict, Optional, Set, Tuple

from ..model.style import Style, StyleTable
from ..model.paragraph import RunProps, ParaProps
from .theme_resolver import ThemeResolver


class StyleResolver:
    """Resolve final paragraph/run properties via inheritance chain.

    Priority (low → high):
      docDefaults → basedOn chain → current style → direct formatting
    """

    # When True, table-style pPr (spacing fields only) is applied to cell
    # paragraphs between docDefaults and the paragraph-style chain.
    #
    # Round 5 experiments enabled this by default (golden row heights
    # implied LO applies table-style pPr) but caused regressions on
    # template / tracked-changes / table-document (page count drops).
    # The empirical side-effect on dense tables outweighed the benefit,
    # so the flag stays DISABLED for the Round 5 baseline.  The
    # parameter / chain / table_style stack in document.py are retained
    # so a future ``Config.word_compatible`` flag can toggle this on.
    _apply_table_style_ppr: bool = False

    def __init__(
        self,
        style_table: StyleTable,
        theme_colors: Optional[Dict[str, Tuple[int, int, int]]] = None,
        theme_fonts: Optional[Dict[str, str]] = None,
        default_rpr: Optional[RunProps] = None,
        default_ppr: Optional[ParaProps] = None,
    ):
        self.styles = style_table
        self.default_rpr = default_rpr or RunProps()
        self.default_ppr = default_ppr or ParaProps()
        self.theme = ThemeResolver(theme_colors or {}, theme_fonts or {})
        self._cache: Dict[str, tuple] = {}

    def resolve_para(self, style_id: str, direct: ParaProps,
                     direct_set: Optional[Set[str]] = None,
                     table_style_id: Optional[str] = None) -> ParaProps:
        """Resolve final paragraph properties.

        OOXML application order (ECMA-376 §17.7.2, low → high):
          docDefaults → table style pPr → paragraph style chain → direct pPr.
        ``table_style_id`` is the w:tblStyle of the innermost containing
        table, applied only for paragraphs inside table cells.
        """
        result = copy.deepcopy(self.default_ppr)

        # Table style paragraph properties (e.g. TableGrid's after=0/line=240)
        # sit between docDefaults and the paragraph style hierarchy per
        # ECMA-376 §17.7.2.  LibreOffice applies the table-style *spacing*
        # fields to cell paragraphs — verified by golden row heights showing
        # table-doc rows fully compressed (no after-spacing) and large-doc
        # rows carrying the full inherited after-spacing.  However, LO does
        # NOT apply the table-style *line* rule inside cells; if we merge
        # line_spacing here, rows shrink below LO baseline (24px vs 30px at
        # 150dpi), causing table-document to under-paginate (4→2).  Keep
        # line fields out of the merge.
        if table_style_id and self._apply_table_style_ppr:
            for sid in self._build_chain(table_style_id):
                style = self.styles.get(sid)
                if style and style.type == "table" and style.para_set:
                    spacing_fields = {
                        f for f in style.para_set
                        if f in ("space_before", "space_after")
                    }
                    if spacing_fields:
                        result = self._merge_ppr(
                            result, style.para_props, spacing_fields
                        )

        # Default paragraph style (e.g. Normal) if no explicit style
        if not style_id and self.styles.default_paragraph:
            style_id = self.styles.default_paragraph.style_id

        chain = self._build_chain(style_id)
        for sid in chain:
            style = self.styles.get(sid)
            if style:
                result = self._merge_ppr(result, style.para_props, style.para_set)

        result = self._merge_ppr(result, direct, direct_set)

        # Paragraph mark font size: direct pPr/rPr > style chain rPr > docDefaults.
        # Used for empty-paragraph height and character-unit indent resolution.
        if result.mark_font_size is None:
            for sid in reversed(chain):
                style = self.styles.get(sid)
                if (
                    style
                    and style.run_props is not None
                    and style.run_set
                    and "font_size" in style.run_set
                ):
                    result.mark_font_size = style.run_props.font_size
                    break
        if result.mark_font_size is None:
            result.mark_font_size = self.default_rpr.font_size

        # Track whether space_after came only from docDefaults.  LibreOffice
        # (our golden reference) drops docDefaults-only after-spacing for
        # paragraphs inside table cells, while style-chain / direct spacing
        # is kept.  Layout uses this flag for cell paragraphs.
        explicit_after = False
        for sid in chain:
            style = self.styles.get(sid)
            if style and style.para_set and "space_after" in style.para_set:
                explicit_after = True
                break
        if not explicit_after:
            dset = direct_set
            if dset is None and direct is not None:
                dset = _diff_fields(ParaProps(), direct)
            if dset and "space_after" in dset:
                explicit_after = True
        result.space_after_default_only = not explicit_after
        return result

    def resolve_run(
        self,
        char_style_id: str,
        para_style_id: str,
        direct: RunProps,
        direct_set: Optional[Set[str]] = None,
    ) -> RunProps:
        """Resolve final run properties."""
        result = copy.deepcopy(self.default_rpr)

        # Paragraph style rPr
        if not para_style_id and self.styles.default_paragraph:
            para_style_id = self.styles.default_paragraph.style_id

        for sid in self._build_chain(para_style_id):
            style = self.styles.get(sid)
            if style:
                result = self._merge_rpr(result, style.run_props, style.run_set)

        # Character style
        if char_style_id:
            for sid in self._build_chain(char_style_id):
                style = self.styles.get(sid)
                if style:
                    result = self._merge_rpr(result, style.run_props, style.run_set)

        result = self._merge_rpr(result, direct, direct_set)
        result = self.theme.apply_fonts(result)
        result = self.theme.apply_color(result)

        # Print / image export: suppress Hyperlink character-style chrome
        # (theme blue + underline). Word's on-screen view shows it; printed
        # pages and PDF exports typically render TOC / links as body text.
        if char_style_id and self._is_hyperlink_style(char_style_id):
            dset = direct_set or set()
            if "color" not in dset:
                result.color = (0, 0, 0)
                if hasattr(result, "_color_raw"):
                    try:
                        delattr(result, "_color_raw")
                    except Exception:
                        result._color_raw = None  # type: ignore[attr-defined]
            if "underline" not in dset and "underline_style" not in dset:
                result.underline = False

        return result

    def _is_hyperlink_style(self, style_id: str) -> bool:
        """True if style_id resolves to the built-in Hyperlink character style."""
        for sid in self._build_chain(style_id):
            style = self.styles.get(sid)
            if style and (style.name or "").strip().lower() == "hyperlink":
                return True
        return False

    def _build_chain(self, style_id: str) -> list:
        """Build basedOn chain from root → leaf."""
        if not style_id:
            return []
        chain = []
        visited = set()
        sid = style_id
        while sid and sid not in visited:
            visited.add(sid)
            chain.append(sid)
            style = self.styles.get(sid)
            sid = style.based_on if style else None
        chain.reverse()
        return chain

    def _merge_ppr(
        self, base: ParaProps, overlay: ParaProps, fields: Optional[Set[str]]
    ) -> ParaProps:
        if overlay is None:
            return base
        out = copy.deepcopy(base)
        if fields is None:
            # Merge all non-default-ish fields — fallback when set unknown
            fields = _diff_fields(ParaProps(), overlay)
        for name in fields:
            if hasattr(overlay, name):
                setattr(out, name, copy.deepcopy(getattr(overlay, name)))
        return out

    def _merge_rpr(
        self, base: RunProps, overlay: RunProps, fields: Optional[Set[str]]
    ) -> RunProps:
        if overlay is None:
            return base
        out = copy.deepcopy(base)
        if fields is None:
            fields = _diff_fields(RunProps(), overlay)
        for name in fields:
            if hasattr(overlay, name):
                setattr(out, name, copy.deepcopy(getattr(overlay, name)))
        # Preserve raw color metadata for theme resolution
        if hasattr(overlay, "_color_raw"):
            out._color_raw = overlay._color_raw  # type: ignore[attr-defined]
        return out


def _diff_fields(blank, obj) -> Set[str]:
    """Fields where obj differs from a blank default instance."""
    result = set()
    for name in vars(blank):
        if name.startswith("_"):
            continue
        if getattr(obj, name) != getattr(blank, name):
            result.add(name)
    return result
