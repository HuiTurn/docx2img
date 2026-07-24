"""Parse DrawingML images (inline / floating) and text boxes."""

from __future__ import annotations

from typing import Optional, Dict, Callable

from ..model.paragraph import ImageRun, TextBoxRun
from .namespaces import NS, A, WP, PIC, R_DOC, W
from .units import Units


class DrawingParser:
    """Parse w:drawing → ImageRun or TextBoxRun."""

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
        # Prefer image blip; textboxes handled separately
        if drawing_el.find(f".//{{{A}}}blip") is None:
            return None
        inline = drawing_el.find(f"{{{WP}}}inline")
        if inline is not None:
            return self._parse_inline(inline)

        anchor = drawing_el.find(f"{{{WP}}}anchor")
        if anchor is not None:
            return self._parse_anchor(anchor)
        return None

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

        return TextBoxRun(
            paragraphs=paragraphs,
            width_emu=cx,
            height_emu=cy,
            pos_x=pos_x,
            pos_y=pos_y,
            wrap_type=wrap_type,
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
