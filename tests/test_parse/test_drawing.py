"""DrawingML group parsing tests."""

import xml.etree.ElementTree as ET

import pytest

from docx2img.model.paragraph import Paragraph
from docx2img.parse.drawing import DrawingParser
from docx2img.parse.namespaces import A, NS, PIC, R_DOC, WP, WPG, WPS


def test_parse_group_applies_child_coordinate_transform():
    xml = f"""
    <w:drawing xmlns:w="{NS.W}" xmlns:r="{R_DOC}" xmlns:a="{A}"
               xmlns:wp="{WP}" xmlns:pic="{PIC}"
               xmlns:wpg="{WPG}" xmlns:wps="{WPS}">
      <wp:inline>
        <wp:extent cx="2000" cy="1000"/>
        <a:graphic><a:graphicData><wpg:wgp>
          <wpg:grpSpPr><a:xfrm>
            <a:off x="100" y="200"/><a:ext cx="2000" cy="1000"/>
            <a:chOff x="10" y="20"/><a:chExt cx="1000" cy="500"/>
          </a:xfrm></wpg:grpSpPr>
          <pic:pic>
            <pic:blipFill><a:blip r:embed="rId1"/></pic:blipFill>
            <pic:spPr><a:xfrm>
              <a:off x="110" y="70"/><a:ext cx="200" cy="100"/>
            </a:xfrm></pic:spPr>
          </pic:pic>
          <wps:wsp>
            <wps:spPr>
              <a:xfrm><a:off x="210" y="120"/><a:ext cx="300" cy="100"/></a:xfrm>
              <a:solidFill><a:srgbClr val="112233"/></a:solidFill>
              <a:ln><a:solidFill><a:srgbClr val="445566"/></a:solidFill></a:ln>
            </wps:spPr>
            <wps:txbx><w:txbxContent><w:p/></w:txbxContent></wps:txbx>
          </wps:wsp>
          <wps:wsp>
            <wps:spPr>
              <a:xfrm><a:off x="10" y="20"/><a:ext cx="1000" cy="0"/></a:xfrm>
              <a:custGeom/><a:noFill/>
              <a:ln w="12700"><a:solidFill><a:srgbClr val="ABCDEF"/></a:solidFill></a:ln>
            </wps:spPr>
          </wps:wsp>
        </wpg:wgp></a:graphicData></a:graphic>
      </wp:inline>
    </w:drawing>
    """
    parser = DrawingParser(
        media={"media/image1.png": b"image-bytes"},
        rels={"rId1": "media/image1.png"},
        para_parser=lambda _elem: Paragraph(),
    )
    group = parser.parse_group(ET.fromstring(xml))

    assert group is not None
    assert group["group_extent"] == (2000, 1000)

    image = group["image"]
    assert image is not None
    assert image.data == b"image-bytes"
    assert image.pos_x == pytest.approx(300 / 12700)
    assert image.pos_y == pytest.approx(300 / 12700)
    assert image.width_emu == 400
    assert image.height_emu == 200

    textbox = group["textboxes"][0]
    assert textbox.pos_x == pytest.approx(500 / 12700)
    assert textbox.pos_y == pytest.approx(400 / 12700)
    assert textbox.width_emu == 600
    assert textbox.height_emu == 200
    assert textbox.fill == (17, 34, 51)
    assert textbox.border_color == (68, 85, 102)
    assert len(textbox.paragraphs) == 1

    line = group["lines"][0]
    assert line["x"] == pytest.approx(100 / 12700)
    assert line["y"] == pytest.approx(200 / 12700)
    assert line["width"] == pytest.approx(2000 / 12700)
    assert line["color"] == (171, 205, 239)
