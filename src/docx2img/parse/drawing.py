"""Parse DrawingML images (inline / floating) and text boxes."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from ..model.enums import Alignment
from ..model.paragraph import (
    BreakRun,
    ImageRun,
    Paragraph,
    ParaProps,
    Run,
    RunProps,
    TextBoxRun,
    TextRun,
)
from .namespaces import (
    NS, A, WP, PIC, R_DOC, W, WPG, WPS, VML, OFFICE, WORD_VML
)
from .units import Units

logger = logging.getLogger(__name__)


class DrawingParser:
    """Parse w:drawing → ImageRun, TextBoxRun, or group contents."""

    def __init__(
        self,
        media: Optional[Dict[str, bytes]] = None,
        rels: Optional[Dict[str, str]] = None,
        para_parser: Optional[Callable] = None,
    ):
        self.media = media or {}
        self.rels = rels or {}
        self._parse_para = para_parser

    def parse(self, drawing_el) -> Optional[ImageRun]:
        """Parse w:drawing → ImageRun (for simple image drawings)."""
        # Check for WordprocessingGroup first — handled by parse_group()
        grp = drawing_el.find(f".//{{{WPG}}}wgp")
        if grp is not None:
            return None  # Use parse_group() instead

        if drawing_el.find(f".//{{{A}}}blip") is None:
            return None
        inline = drawing_el.find(f"{{{WP}}}inline")
        if inline is not None:
            return self._parse_inline(inline)

        anchor = drawing_el.find(f"{{{WP}}}anchor")
        if anchor is not None:
            return self._parse_anchor(anchor)
        return None

    def parse_group(self, drawing_el) -> Optional[Dict[str, Any]]:
        """Parse w:drawing containing wpg:wgp → dict with image + textboxes + lines.

        Returns dict with keys:
          - 'image': ImageRun or None
          - 'textboxes': list of TextBoxRun
          - 'lines': list of line shape dicts
          - 'group_extent': (cx, cy) EMU of the group
        """
        grp = drawing_el.find(f".//{{{WPG}}}wgp")
        if grp is None:
            return None

        # Get inline/ancestor extent for the whole group
        host = drawing_el.find(f"{{{WP}}}inline")
        group_cx, group_cy = self._extent(host) if host is not None else (0, 0)

        result = {
            "image": None,
            "textboxes": [],
            "lines": [],
            "group_extent": (group_cx, group_cy),
        }
        transform = self._group_transform(grp)

        # Iterate over all children of the group
        for child in grp:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag == "pic":
                # Picture element (e.g., logo)
                img = self._parse_pic_element(child)
                if img:
                    self._transform_group_image(img, transform)
                    result["image"] = img

            elif tag == "wsp":
                # WordprocessingShape — could be textbox or line/shape
                shape_info = self._parse_wps_shape(child)
                if shape_info is not None:
                    if isinstance(shape_info, TextBoxRun):
                        self._transform_group_textbox(shape_info, transform)
                        result["textboxes"].append(shape_info)
                    elif isinstance(shape_info, dict) and shape_info.get("type") == "line":
                        self._transform_group_line(shape_info, transform)
                        result["lines"].append(shape_info)

        return result

    def parse_vml(self, pict_el) -> List[Dict[str, Any]]:
        """Parse legacy ``w:pict`` VML shapes into paragraph group items.

        WPS and older Word documents frequently store flowcharts, captions,
        text-over-image frames and connector arrows as VML rather than
        DrawingML.  Their positions are paragraph-relative point values in the
        CSS-like ``style`` attribute.
        """
        result: List[Dict[str, Any]] = []
        for child in list(pict_el):
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag not in ("shape", "rect", "oval", "line"):
                continue

            style = self._parse_vml_style(child.get("style", ""))
            x = self._vml_length(style.get("margin-left", style.get("left", "0")))
            y = self._vml_length(style.get("margin-top", style.get("top", "0")))
            width = self._vml_length(style.get("width", "0"))
            height = self._vml_length(style.get("height", "0"))
            z_index = self._vml_int(style.get("z-index"), 0)
            flip = set((style.get("flip") or "").lower().split())
            rotation = self._vml_rotation(style.get("rotation"))

            if tag == "line":
                line = self._vml_line_item(
                    child, x, y, width, height, flip, rotation, z_index
                )
                result.append({"type": "line", "data": line})
                continue

            textbox = child.find(f".//{{{W}}}txbxContent")
            spt = child.get(f"{{{OFFICE}}}spt", "")
            if not spt:
                type_ref = child.get("type", "")
                match = re.search(r"_t(\d+)$", type_ref)
                spt = match.group(1) if match else ""

            if textbox is None:
                # Built-in VML shape types 32–35 are connector variants.
                if spt in {"32", "33", "34", "35"}:
                    line = self._vml_line_item(
                        child, x, y, width, height, flip, rotation, z_index,
                        connector_type=spt,
                    )
                    result.append({"type": "line", "data": line})
                continue

            paragraphs = []
            if self._parse_para:
                for para_el in textbox:
                    if para_el.tag.split("}")[-1] == "p":
                        para = self._parse_para(para_el)
                        if para:
                            paragraphs.append(para)

            if tag == "oval":
                shape_type = "oval"
            elif tag == "rect":
                shape_type = "rect"
            else:
                shape_type = {
                    "110": "diamond",
                    "202": "none",
                }.get(spt, "rect")
            fill = self._vml_fill(child)
            border = self._vml_border(child)
            wrap = child.find(f"{{{WORD_VML}}}wrap")
            wrap_type = (
                wrap.get("type", "square")
                if wrap is not None
                else "inFrontOf"
            )
            inset_el = child.find(f"{{{VML}}}textbox")
            insets = self._vml_insets(
                inset_el.get("inset", "") if inset_el is not None else ""
            )
            tb = TextBoxRun(
                paragraphs=paragraphs,
                width_emu=int(round(width * Units.EMU_PER_PT)),
                height_emu=int(round(height * Units.EMU_PER_PT)),
                pos_x=x,
                pos_y=y,
                wrap_type=wrap_type,
                fill=fill,
                border_color=border,
                shape_type=shape_type,
                z_index=z_index,
                affects_flow=False,
                insets=insets,
            )
            result.append({"type": "textbox", "data": tb})
        return result

    @staticmethod
    def _parse_vml_style(style: str) -> Dict[str, str]:
        parsed: Dict[str, str] = {}
        for declaration in (style or "").split(";"):
            key, sep, value = declaration.partition(":")
            if sep:
                parsed[key.strip().lower()] = value.strip()
        return parsed

    @staticmethod
    def _vml_length(value: Optional[str]) -> float:
        """Return a VML CSS length in points."""
        if value is None:
            return 0.0
        match = re.match(
            r"^\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*(pt|px|in|cm|mm)?\s*$",
            str(value),
            re.I,
        )
        if not match:
            return 0.0
        number = float(match.group(1))
        unit = (match.group(2) or "pt").lower()
        factors = {
            "pt": 1.0,
            "px": 72.0 / 96.0,
            "in": 72.0,
            "cm": 72.0 / 2.54,
            "mm": 72.0 / 25.4,
        }
        return number * factors[unit]

    @staticmethod
    def _vml_int(value: Optional[str], default: int = 0) -> int:
        try:
            return int(float(value)) if value is not None else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _vml_rotation(value: Optional[str]) -> float:
        if not value:
            return 0.0
        raw = str(value).strip().lower()
        try:
            if raw.endswith("f"):
                return float(raw[:-1]) / 65536.0
            return float(raw)
        except ValueError:
            return 0.0

    @staticmethod
    def _vml_bool(value: Optional[str], default: bool = True) -> bool:
        if value is None:
            return default
        return str(value).strip().lower() not in {"f", "false", "0", "off", "no"}

    @staticmethod
    def _vml_color(value: Optional[str], default: Optional[tuple] = None):
        if not value:
            return default
        raw = value.strip().lower()
        named = {
            "black": (0, 0, 0),
            "white": (255, 255, 255),
            "red": (255, 0, 0),
            "green": (0, 128, 0),
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
        }
        if raw in named:
            return named[raw]
        raw = raw.lstrip("#")
        if len(raw) == 6:
            try:
                return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                pass
        return default

    def _vml_fill(self, shape_el) -> Optional[tuple]:
        if not self._vml_bool(shape_el.get("filled"), True):
            return None
        fill_el = shape_el.find(f"{{{VML}}}fill")
        if fill_el is not None and not self._vml_bool(fill_el.get("on"), True):
            return None
        value = shape_el.get("fillcolor")
        if not value and fill_el is not None:
            value = fill_el.get("color") or fill_el.get("color2")
        return self._vml_color(value, (255, 255, 255))

    def _vml_border(self, shape_el) -> Optional[tuple]:
        if not self._vml_bool(shape_el.get("stroked"), True):
            return None
        stroke = shape_el.find(f"{{{VML}}}stroke")
        if stroke is not None and not self._vml_bool(stroke.get("on"), True):
            return None
        value = shape_el.get("strokecolor")
        if not value and stroke is not None:
            value = stroke.get("color")
        return self._vml_color(value, (0, 0, 0))

    def _vml_line_item(
        self,
        shape_el,
        x: float,
        y: float,
        width: float,
        height: float,
        flip: set,
        rotation: float,
        z_index: int,
        connector_type: str = "20",
    ) -> Dict[str, Any]:
        if width == 0.0 and height == 0.0:
            start = self._vml_pair(shape_el.get("from"))
            end = self._vml_pair(shape_el.get("to"))
            if start is not None and end is not None:
                x, y = start
                width, height = end[0] - start[0], end[1] - start[1]

        if connector_type == "34":
            points = [
                (0.0, 0.0),
                (width * 0.5, 0.0),
                (width * 0.5, height),
                (width, height),
            ]
        elif connector_type in {"33", "35"} and abs(width) > 0.5 and abs(height) > 0.5:
            points = [(0.0, 0.0), (width, 0.0), (width, height)]
        else:
            points = [(0.0, 0.0), (width, height)]

        rotate_180 = abs((rotation % 360.0) - 180.0) < 0.01
        transformed = []
        for px, py in points:
            if "x" in flip:
                px = width - px
            if "y" in flip:
                py = height - py
            if rotate_180:
                px, py = width - px, height - py
            transformed.append((px, py))

        stroke = shape_el.find(f"{{{VML}}}stroke")
        arrow_end = (
            stroke is not None
            and (stroke.get("endarrow") or "").lower() not in {"", "none"}
        )
        line_width = self._vml_length(
            shape_el.get("strokeweight")
            or (stroke.get("weight") if stroke is not None else None)
            or "0.75pt"
        )
        return {
            "type": "line",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "points": transformed,
            "line_width_pt": line_width,
            "color": self._vml_border(shape_el) or (0, 0, 0),
            "arrow_end": arrow_end,
            "z_index": z_index,
            "affects_flow": False,
        }

    def _vml_pair(self, value: Optional[str]) -> Optional[tuple]:
        if not value or "," not in value:
            return None
        first, second = value.split(",", 1)
        return self._vml_length(first), self._vml_length(second)

    def _vml_insets(self, value: str) -> tuple:
        defaults = (3.6, 1.8, 3.6, 1.8)
        if not value:
            return defaults
        parts = [self._vml_length(item) for item in value.split(",")]
        if len(parts) == 4:
            return tuple(parts)
        return defaults

    @staticmethod
    def _group_transform(grp) -> tuple:
        """Return group child-space → parent-space transform in EMUs."""
        xfrm = grp.find(f"{{{WPG}}}grpSpPr/{{{A}}}xfrm")

        def pair(name: str, first: str, second: str) -> tuple:
            elem = xfrm.find(f"{{{A}}}{name}") if xfrm is not None else None
            if elem is None:
                return (0, 0)
            return (
                int(elem.get(first, 0) or 0),
                int(elem.get(second, 0) or 0),
            )

        off_x, off_y = pair("off", "x", "y")
        ext_x, ext_y = pair("ext", "cx", "cy")
        child_x, child_y = pair("chOff", "x", "y")
        child_w, child_h = pair("chExt", "cx", "cy")
        scale_x = ext_x / child_w if ext_x > 0 and child_w > 0 else 1.0
        scale_y = ext_y / child_h if ext_y > 0 and child_h > 0 else 1.0
        return (off_x, off_y, child_x, child_y, scale_x, scale_y)

    @staticmethod
    def _transform_point(x_emu: float, y_emu: float, transform: tuple) -> tuple:
        off_x, off_y, child_x, child_y, scale_x, scale_y = transform
        return (
            off_x + (x_emu - child_x) * scale_x,
            off_y + (y_emu - child_y) * scale_y,
        )

    def _transform_group_image(self, image: ImageRun, transform: tuple) -> None:
        x, y = self._transform_point(
            image.pos_x * Units.EMU_PER_PT,
            image.pos_y * Units.EMU_PER_PT,
            transform,
        )
        image.pos_x = Units.emu_to_pt(x)
        image.pos_y = Units.emu_to_pt(y)
        image.width_emu = int(round(image.width_emu * transform[4]))
        image.height_emu = int(round(image.height_emu * transform[5]))

    def _transform_group_textbox(
        self, textbox: TextBoxRun, transform: tuple
    ) -> None:
        x, y = self._transform_point(
            textbox.pos_x * Units.EMU_PER_PT,
            textbox.pos_y * Units.EMU_PER_PT,
            transform,
        )
        textbox.pos_x = Units.emu_to_pt(x)
        textbox.pos_y = Units.emu_to_pt(y)
        textbox.width_emu = int(round(textbox.width_emu * transform[4]))
        textbox.height_emu = int(round(textbox.height_emu * transform[5]))

    def _transform_group_line(self, line: dict, transform: tuple) -> None:
        x_emu = line["x"] * Units.EMU_PER_PT
        y_emu = line["y"] * Units.EMU_PER_PT
        x, y = self._transform_point(x_emu, y_emu, transform)
        line["x"] = Units.emu_to_pt(x)
        line["y"] = Units.emu_to_pt(y)
        line["width"] *= transform[4]
        line["height"] *= transform[5]

    def _parse_pic_element(self, pic_el) -> Optional[ImageRun]:
        """Extract ImageRun from pic:pic within a group."""
        blip = pic_el.find(f".//{{{A}}}blip")
        if blip is None:
            return None

        rid = blip.get(f"{{{R_DOC}}}embed") or blip.get(f"{{{NS.R}}}embed", "")
        data = self._resolve_media(rid) if rid else None

        # Get position/size from pic:spPr/a:xfrm
        xfrm = pic_el.find(f".//{{{A}}}xfrm")
        cx = cy = 0
        pos_x_emu = pos_y_emu = 0
        if xfrm is not None:
            ext_el = xfrm.find(f"{{{A}}}ext")
            off_el = xfrm.find(f"{{{A}}}off")
            if ext_el is not None:
                cx = int(ext_el.get("cx", 0) or 0)
                cy = int(ext_el.get("cy", 0) or 0)
            if off_el is not None:
                pos_x_emu = int(off_el.get("x", 0) or 0)
                pos_y_emu = int(off_el.get("y", 0) or 0)

        return ImageRun(
            media_ref=rid or "",
            data=data,
            width_emu=cx,
            height_emu=cy,
            wrap_type="inFrontOf",  # Group children are absolutely positioned
            pos_x=Units.emu_to_pt(pos_x_emu),
            pos_y=Units.emu_to_pt(pos_y_emu),
        )

    def _parse_wps_shape(self, wsp_el):
        """Parse wps:wsp → TextBoxRun or line shape dict."""
        # Check for text box content
        txbx = wsp_el.find(f"{{{WPS}}}txbx")
        if txbx is not None:
            txbx_content = txbx.find(f"{{{W}}}txbxContent")
            if txbx_content is not None:
                return self._extract_textbox(wsp_el, txbx_content)

        # Check for line shape (custGeom with path, no fill, has line)
        sp_pr = wsp_el.find(f"{{{WPS}}}spPr")
        if sp_pr is not None:
            ln = sp_pr.find(f"{{{A}}}ln")
            no_fill = sp_pr.find(f"{{{A}}}noFill")
            cust_geom = sp_pr.find(f"{{{A}}}custGeom")
            # It's a line if it has custom geometry with line but no fill
            if ln is not None and (no_fill is not None or cust_geom is not None):
                return self._extract_line_shape(wsp_el, sp_pr)

        return None

    def _extract_textbox(self, wsp_el, txbx_content) -> TextBoxRun:
        """Extract TextBoxRun from wps:wsp with txbxContent."""
        # Position and size from wps:spPr/a:xfrm
        sp_pr = wsp_el.find(f"{{{WPS}}}spPr")
        cx = cy = 0
        pos_x_emu = pos_y_emu = 0
        if sp_pr is not None:
            xfrm = sp_pr.find(f"{{{A}}}xfrm")
            if xfrm is not None:
                ext_el = xfrm.find(f"{{{A}}}ext")
                off_el = xfrm.find(f"{{{A}}}off")
                if ext_el is not None:
                    cx = int(ext_el.get("cx", 0) or 0)
                    cy = int(ext_el.get("cy", 0) or 0)
                if off_el is not None:
                    pos_x_emu = int(off_el.get("x", 0) or 0)
                    pos_y_emu = int(off_el.get("y", 0) or 0)

        paragraphs = []
        if self._parse_para:
            for child in txbx_content:
                tag = child.tag.split("}")[-1]
                if tag == "p":
                    para = self._parse_para(child)
                    if para:
                        paragraphs.append(para)

        fill, border = self._shape_fill_and_border(sp_pr)
        return TextBoxRun(
            paragraphs=paragraphs,
            width_emu=cx,
            height_emu=cy,
            pos_x=Units.emu_to_pt(pos_x_emu),
            pos_y=Units.emu_to_pt(pos_y_emu),
            wrap_type="inFrontOf",  # Group children are absolutely positioned
            fill=fill,
            border_color=border,
        )

    @staticmethod
    def _shape_fill_and_border(sp_pr) -> tuple:
        """Extract explicit solid fill and outline colors from shape props."""

        def solid_color(container) -> Optional[tuple]:
            if container is None:
                return None
            solid = container.find(f"{{{A}}}solidFill")
            srgb = (
                solid.find(f"{{{A}}}srgbClr")
                if solid is not None
                else None
            )
            if srgb is None:
                return None
            val = srgb.get("val", "")
            if len(val) != 6:
                return None
            try:
                return tuple(int(val[i : i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return None

        fill = solid_color(sp_pr)
        line = sp_pr.find(f"{{{A}}}ln") if sp_pr is not None else None
        border = solid_color(line)
        return fill, border

    def _extract_line_shape(self, wsp_el, sp_pr) -> dict:
        """Extract line shape info from wps:wsp."""
        xfrm = sp_pr.find(f"{{{A}}}xfrm")
        cx = cy = 0
        pos_x_emu = pos_y_emu = 0
        if xfrm is not None:
            ext_el = xfrm.find(f"{{{A}}}ext")
            off_el = xfrm.find(f"{{{A}}}off")
            if ext_el is not None:
                cx = int(ext_el.get("cx", 0) or 0)
                cy = int(ext_el.get("cy", 0) or 0)
            if off_el is not None:
                pos_x_emu = int(off_el.get("x", 0) or 0)
                pos_y_emu = int(off_el.get("y", 0) or 0)

        # Extract line properties
        ln = sp_pr.find(f"{{{A}}}ln")
        line_w = 12700  # default ~1pt in EMU
        color = (0, 0, 0)
        if ln is not None:
            w_attr = ln.get("w")
            if w_attr:
                line_w = int(w_attr)
            solid_fill = ln.find(f"{{{A}}}solidFill")
            if solid_fill is not None:
                srgb = solid_fill.find(f"{{{A}}}srgbClr")
                if srgb is not None:
                    val = srgb.get("val", "000000")
                    if len(val) == 6:
                        color = (int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))

        return {
            "type": "line",
            "x": Units.emu_to_pt(pos_x_emu),
            "y": Units.emu_to_pt(pos_y_emu),
            "width": Units.emu_to_pt(cx),
            "height": Units.emu_to_pt(cy),
            "line_width": line_w,
            "color": color,
        }

    def parse_textbox(self, drawing_el) -> Optional[TextBoxRun]:
        """Parse w:txbxContent or native DrawingML a:txBody shape text."""
        # WordprocessingML text box content
        txbx = drawing_el.find(f".//{{{W}}}txbxContent")
        tx_body = (
            drawing_el.find(f".//{{{A}}}txBody") if txbx is None else None
        )
        if txbx is None and tx_body is None:
            return None

        # Find extent from ancestor inline/anchor
        host = drawing_el.find(f"{{{WP}}}anchor")
        if host is None:
            host = drawing_el.find(f"{{{WP}}}inline")
        cx, cy = self._extent(host) if host is not None else (0, 0)

        wrap_type = "square"
        pos_x = pos_y = 0.0
        relative_x = "column"
        align_x = None
        if host is not None and host.tag.endswith("anchor"):
            if host.find(f"{{{WP}}}wrapTopAndBottom") is not None:
                wrap_type = "topAndBottom"
            elif host.find(f"{{{WP}}}wrapNone") is not None:
                wrap_type = "inFrontOf"
            pos_h_el = host.find(f"{{{WP}}}positionH")
            if pos_h_el is not None:
                relative_x = pos_h_el.get("relativeFrom", "column")
                align_el = pos_h_el.find(f"{{{WP}}}align")
                if align_el is not None and align_el.text:
                    align_x = align_el.text.strip()
                else:
                    pos_h = pos_h_el.find(f"{{{WP}}}posOffset")
                    if pos_h is not None and pos_h.text:
                        pos_x = Units.emu_to_pt(int(pos_h.text))
            pos_v = host.find(f"{{{WP}}}positionV/{{{WP}}}posOffset")
            if pos_v is not None and pos_v.text:
                pos_y = Units.emu_to_pt(int(pos_v.text))

        paragraphs = []
        if txbx is not None and self._parse_para:
            for child in txbx:
                tag = child.tag.split("}")[-1]
                if tag == "p":
                    para = self._parse_para(child)
                    if para:
                        paragraphs.append(para)
        elif tx_body is not None:
            paragraphs = self._parse_drawingml_text_body(tx_body)

        margins = (0.0, 0.0, 0.0, 0.0)
        vertical_anchor = "top"
        auto_fit = False
        if tx_body is not None:
            body_pr = tx_body.find(f"{{{A}}}bodyPr")
            if body_pr is not None:
                margin_names = ("lIns", "tIns", "rIns", "bIns")
                parsed_margins = []
                for name in margin_names:
                    try:
                        parsed_margins.append(
                            Units.emu_to_pt(int(body_pr.get(name, "0")))
                        )
                    except ValueError:
                        parsed_margins.append(0.0)
                        logger.warning(
                            "drawingml_txbody_invalid_inset: invalid %s=%r",
                            name,
                            body_pr.get(name),
                        )
                margins = tuple(parsed_margins)
                vertical_anchor = {
                    "t": "top",
                    "ctr": "center",
                    "b": "bottom",
                }.get(body_pr.get("anchor", "t"), "top")
                if body_pr.find(f"{{{A}}}spAutoFit") is not None:
                    auto_fit = True

        # Preserve the shape's background fill and outline so standalone text
        # boxes / autoshapes are not rendered as bare text.  Word emits these
        # on wps:wsp/wps:spPr; legacy w:txbxContent without a wps:wsp (and
        # shapes that use a:noFill) correctly yield fill/border = None.
        fill, border = None, None
        wsp = drawing_el.find(f".//{{{WPS}}}wsp")
        if wsp is not None:
            sp_pr = wsp.find(f"{{{WPS}}}spPr")
            if sp_pr is not None:
                fill, border = self._shape_fill_and_border(sp_pr)
            body_pr = wsp.find(f"{{{WPS}}}bodyPr")
            if body_pr is not None and body_pr.find(f"{{{A}}}spAutoFit") is not None:
                auto_fit = True

        return TextBoxRun(
            paragraphs=paragraphs,
            width_emu=cx,
            height_emu=cy,
            pos_x=pos_x,
            pos_y=pos_y,
            wrap_type=wrap_type,
            relative_x=relative_x,
            align_x=align_x,
            auto_fit=auto_fit,
            fill=fill,
            border_color=border,
            margin_left=margins[0],
            margin_top=margins[1],
            margin_right=margins[2],
            margin_bottom=margins[3],
            vertical_anchor=vertical_anchor,
        )

    def _parse_drawingml_text_body(self, tx_body) -> list:
        """Convert the supported ``a:txBody`` subset to paragraph IR."""
        paragraphs = []
        unsupported_visible = set()

        for p_el in tx_body.findall(f"{{{A}}}p"):
            p_pr = p_el.find(f"{{{A}}}pPr")
            alignment = Alignment.LEFT
            if p_pr is not None:
                alignment = {
                    "l": Alignment.LEFT,
                    "ctr": Alignment.CENTER,
                    "r": Alignment.RIGHT,
                    "just": Alignment.JUSTIFY,
                    "justLow": Alignment.JUSTIFY,
                    "dist": Alignment.DISTRIBUTE,
                    "thaiDist": Alignment.DISTRIBUTE,
                }.get(p_pr.get("algn", "l"), Alignment.LEFT)

            paragraph = Paragraph(props=ParaProps(alignment=alignment))
            for child in p_el:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag in ("pPr", "endParaRPr"):
                    continue
                if tag in ("r", "fld"):
                    text_el = child.find(f"{{{A}}}t")
                    if text_el is not None and text_el.text is not None:
                        if tag == "fld":
                            logger.warning(
                                "drawingml_txbody_field_cached: rendering "
                                "cached a:fld text without field evaluation"
                            )
                        paragraph.runs.append(
                            Run(
                                text=TextRun(
                                    text=text_el.text,
                                    props=self._parse_drawingml_run_props(
                                        child.find(f"{{{A}}}rPr")
                                    ),
                                )
                            )
                        )
                    elif self._has_visible_text(child):
                        unsupported_visible.add(tag)
                    continue
                if tag == "br":
                    paragraph.runs.append(Run(brk=BreakRun("line")))
                    continue
                if self._has_visible_text(child):
                    unsupported_visible.add(tag)

            paragraphs.append(paragraph)

        if not paragraphs and self._has_visible_text(tx_body):
            unsupported_visible.add("txBody")
        if unsupported_visible:
            logger.warning(
                "drawingml_txbody_unsupported: visible text in unsupported "
                "DrawingML node(s): %s",
                ", ".join(sorted(unsupported_visible)),
            )
        return paragraphs

    @staticmethod
    def _has_visible_text(element) -> bool:
        return any(text.strip() for text in element.itertext() if text)

    @staticmethod
    def _parse_drawingml_run_props(r_pr) -> RunProps:
        props = RunProps()
        if r_pr is None:
            return props

        size = r_pr.get("sz")
        if size:
            try:
                props.font_size = int(size) / 100.0
            except ValueError:
                logger.warning(
                    "drawingml_txbody_invalid_size: invalid a:rPr sz=%r", size
                )

        props.bold = r_pr.get("b", "0") in ("1", "true", "on")
        props.italic = r_pr.get("i", "0") in ("1", "true", "on")

        underline = r_pr.get("u")
        if underline and underline != "none":
            props.underline = True
            props.underline_style = underline

        strike = r_pr.get("strike")
        props.strike = strike == "sngStrike"
        props.double_strike = strike == "dblStrike"

        solid = r_pr.find(f"{{{A}}}solidFill")
        srgb = solid.find(f"{{{A}}}srgbClr") if solid is not None else None
        if solid is not None and srgb is None:
            logger.warning(
                "drawingml_txbody_unsupported_color: only direct srgbClr "
                "run colors are currently supported"
            )
        if srgb is not None:
            value = srgb.get("val", "")
            if len(value) == 6:
                try:
                    props.color = tuple(
                        int(value[index : index + 2], 16)
                        for index in (0, 2, 4)
                    )
                except ValueError:
                    logger.warning(
                        "drawingml_txbody_invalid_color: invalid srgbClr=%r",
                        value,
                    )

        latin = r_pr.find(f"{{{A}}}latin")
        east_asia = r_pr.find(f"{{{A}}}ea")
        complex_script = r_pr.find(f"{{{A}}}cs")
        if latin is not None and latin.get("typeface"):
            props.font_ascii = latin.get("typeface")
            props.font_h_ansi = latin.get("typeface")
        if east_asia is not None and east_asia.get("typeface"):
            props.font_east_asia = east_asia.get("typeface")
        if complex_script is not None and complex_script.get("typeface"):
            props.font_cs = complex_script.get("typeface")

        return props

    def _parse_inline(self, el) -> Optional[ImageRun]:
        cx, cy = self._extent(el)
        rid = self._blip_rid(el)
        data = self._resolve_media(rid) if rid else None
        return ImageRun(
            media_ref=rid or "",
            data=data,
            width_emu=cx,
            height_emu=cy,
            wrap_type="inline",
        )

    def _parse_anchor(self, el) -> Optional[ImageRun]:
        cx, cy = self._extent(el)
        rid = self._blip_rid(el)
        data = self._resolve_media(rid) if rid else None

        wrap_type = "square"
        if el.find(f"{{{WP}}}wrapNone") is not None:
            behind = el.get("behindDoc", "0")
            wrap_type = "behind" if behind in ("1", "true") else "inFrontOf"
        elif el.find(f"{{{WP}}}wrapTopAndBottom") is not None:
            wrap_type = "topAndBottom"
        elif el.find(f"{{{WP}}}wrapTight") is not None:
            wrap_type = "tight"
        elif el.find(f"{{{WP}}}wrapSquare") is not None:
            wrap_type = "square"

        pos_x = pos_y = None
        pos_h = el.find(f"{{{WP}}}positionH")
        pos_v = el.find(f"{{{WP}}}positionV")
        relative_x = relative_y = "column"
        if pos_h is not None:
            relative_x = pos_h.get("relativeFrom", "column")
            off = pos_h.find(f"{{{WP}}}posOffset")
            if off is not None and off.text:
                pos_x = Units.emu_to_pt(int(off.text))
        if pos_v is not None:
            relative_y = pos_v.get("relativeFrom", "paragraph")
            off = pos_v.find(f"{{{WP}}}posOffset")
            if off is not None and off.text:
                pos_y = Units.emu_to_pt(int(off.text))

        # Text distances (EMU) — Word keeps the anchor paragraph's text clear
        # of a wrapNone/inFrontOf object by these amounts.
        dist_l = dist_r = 0.0
        for attr, _name in (("distL", "l"), ("distR", "r")):
            raw = el.get(attr)
            if raw:
                try:
                    val = Units.emu_to_pt(int(raw))
                except ValueError:
                    val = 0.0
                if attr == "distL":
                    dist_l = val
                else:
                    dist_r = val

        return ImageRun(
            media_ref=rid or "",
            data=data,
            width_emu=cx,
            height_emu=cy,
            wrap_type=wrap_type,
            pos_x=pos_x,
            pos_y=pos_y,
            relative_x=relative_x,
            relative_y=relative_y,
            dist_l=dist_l,
            dist_r=dist_r,
        )

    def _extent(self, el):
        extent = el.find(f"{{{WP}}}extent")
        if extent is None:
            return 0, 0
        return int(extent.get("cx", 0) or 0), int(extent.get("cy", 0) or 0)

    def _blip_rid(self, el) -> Optional[str]:
        blip = el.find(f".//{{{A}}}blip")
        if blip is None:
            return None
        return blip.get(f"{{{R_DOC}}}embed") or blip.get(f"{{{NS.R}}}embed")

    def _resolve_media(self, rid: str) -> Optional[bytes]:
        if not rid:
            return None
        target = self.rels.get(rid, "")
        # Normalize target like "media/image1.png"
        target = target.lstrip("/")
        if target.startswith("word/"):
            target = target[5:]
        if target in self.media:
            return self.media[target]
        # Fallback keys
        name = target.split("/")[-1] if target else ""
        for key, data in self.media.items():
            if key.endswith(name) or key == f"media_{name}":
                return data
        return self.media.get(rid)
