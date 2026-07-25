"""Parse DrawingML images (inline / floating) and text boxes."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..model.paragraph import ImageRun, TextBoxRun
from .namespaces import NS, A, WP, PIC, R_DOC, W, WPG, WPS
from .units import Units


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
        """Parse DrawingML text box (wps:txbx or w:txbxContent)."""
        # WordprocessingML text box content
        txbx = drawing_el.find(f".//{{{W}}}txbxContent")
        if txbx is None:
            # Alternate: a:txBody is shape text — skip for now
            return None

        # Find extent from ancestor inline/anchor
        host = drawing_el.find(f"{{{WP}}}anchor")
        if host is None:
            host = drawing_el.find(f"{{{WP}}}inline")
        cx, cy = self._extent(host) if host is not None else (0, 0)

        wrap_type = "square"
        pos_x = pos_y = 0.0
        if host is not None and host.tag.endswith("anchor"):
            if host.find(f"{{{WP}}}wrapTopAndBottom") is not None:
                wrap_type = "topAndBottom"
            elif host.find(f"{{{WP}}}wrapNone") is not None:
                wrap_type = "inFrontOf"
            pos_h = host.find(f"{{{WP}}}positionH/{{{WP}}}posOffset")
            pos_v = host.find(f"{{{WP}}}positionV/{{{WP}}}posOffset")
            if pos_h is not None and pos_h.text:
                pos_x = Units.emu_to_pt(int(pos_h.text))
            if pos_v is not None and pos_v.text:
                pos_y = Units.emu_to_pt(int(pos_v.text))

        paragraphs = []
        if self._parse_para:
            for child in txbx:
                tag = child.tag.split("}")[-1]
                if tag == "p":
                    para = self._parse_para(child)
                    if para:
                        paragraphs.append(para)

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

        return TextBoxRun(
            paragraphs=paragraphs,
            width_emu=cx,
            height_emu=cy,
            pos_x=pos_x,
            pos_y=pos_y,
            wrap_type=wrap_type,
            fill=fill,
            border_color=border,
        )

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
