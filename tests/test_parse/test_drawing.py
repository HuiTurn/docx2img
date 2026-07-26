"""DrawingML group / standalone shape text parsing tests."""

import xml.etree.ElementTree as ET

import pytest

from docx2img.model.enums import Alignment
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


def test_parse_textbox_extracts_shape_fill_and_border():
    """Standalone DrawingML text box / autoshape must keep its fill + outline.

    Word emits shape text as ``wps:wsp/wps:txbx/w:txbxContent`` wrapped in a
    ``wps:spPr`` that carries ``a:solidFill`` (background) and ``a:ln``
    (outline).  The group path already extracts these; the standalone path
    must do the same so the coloured rectangle is not dropped.
    """
    xml = f"""
    <w:drawing xmlns:w="{NS.W}" xmlns:r="{R_DOC}" xmlns:a="{A}"
               xmlns:wp="{WP}" xmlns:wps="{WPS}">
      <wp:anchor>
        <wp:positionH relativeFrom="column"><wp:posOffset>100000</wp:posOffset></wp:positionH>
        <wp:positionV relativeFrom="paragraph"><wp:posOffset>200000</wp:posOffset></wp:positionV>
        <wp:extent cx="2286000" cy="1143000"/>
        <wp:wrapNone/>
        <a:graphic><a:graphicData
            uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
          <wps:wsp>
            <wps:spPr>
              <a:xfrm><a:off x="0" y="0"/><a:ext cx="2286000" cy="1143000"/></a:xfrm>
              <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
              <a:solidFill><a:srgbClr val="FFCC00"/></a:solidFill>
              <a:ln w="25400"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:ln>
            </wps:spPr>
            <wps:txbx><w:txbxContent><w:p/></w:txbxContent></wps:txbx>
            <wps:bodyPr/>
          </wps:wsp>
        </a:graphicData></a:graphic>
      </wp:anchor>
    </w:drawing>
    """
    parser = DrawingParser(para_parser=lambda _elem: Paragraph())
    tbox = parser.parse_textbox(ET.fromstring(xml))

    assert tbox is not None
    assert tbox.paragraphs == [Paragraph()]
    assert tbox.width_emu == 2286000
    assert tbox.height_emu == 1143000
    # Background fill (a:solidFill) and outline (a:ln) must be preserved.
    assert tbox.fill == (255, 204, 0)
    assert tbox.border_color == (255, 0, 0)


def test_parse_textbox_no_shape_props_yields_no_fill():
    """Legacy w:txbxContent with no wps:wsp must not invent a fill."""
    xml = f"""
    <w:drawing xmlns:w="{NS.W}" xmlns:wp="{WP}">
      <wp:anchor>
        <wp:extent cx="1828800" cy="914400"/>
        <w:txbxContent xmlns:w="{NS.W}"><w:p/></w:txbxContent>
      </wp:anchor>
    </w:drawing>
    """
    parser = DrawingParser(para_parser=lambda _elem: Paragraph())
    tbox = parser.parse_textbox(ET.fromstring(xml))

    assert tbox is not None
    assert tbox.fill is None
    assert tbox.border_color is None


def test_parse_textbox_converts_drawingml_txbody_to_native_model():
    """Generic DrawingML shape text must not disappear outside wps:txbx."""
    xml = f"""
    <w:drawing xmlns:w="{NS.W}" xmlns:a="{A}" xmlns:wp="{WP}">
      <wp:anchor>
        <wp:positionH relativeFrom="column"><wp:posOffset>100000</wp:posOffset></wp:positionH>
        <wp:positionV relativeFrom="paragraph"><wp:posOffset>200000</wp:posOffset></wp:positionV>
        <wp:extent cx="2743200" cy="914400"/>
        <wp:wrapNone/>
        <a:graphic><a:graphicData>
          <a:txSp>
            <a:txBody>
              <a:bodyPr lIns="91440" tIns="45720" rIns="91440"
                        bIns="45720" anchor="ctr"/>
              <a:lstStyle/>
              <a:p>
                <a:pPr algn="ctr"/>
                <a:r>
                  <a:rPr lang="en-US" sz="1800" b="1">
                    <a:solidFill><a:srgbClr val="C00000"/></a:solidFill>
                    <a:latin typeface="Times New Roman"/>
                  </a:rPr>
                  <a:t>DrawingML txBody</a:t>
                </a:r>
              </a:p>
            </a:txBody>
            <a:xfrm><a:off x="0" y="0"/><a:ext cx="2743200" cy="914400"/></a:xfrm>
          </a:txSp>
        </a:graphicData></a:graphic>
      </wp:anchor>
    </w:drawing>
    """
    tbox = DrawingParser().parse_textbox(ET.fromstring(xml))

    assert tbox is not None
    assert tbox.width_emu == 2743200
    assert tbox.height_emu == 914400
    assert tbox.wrap_type == "inFrontOf"
    assert tbox.margin_left == pytest.approx(7.2)
    assert tbox.margin_top == pytest.approx(3.6)
    assert tbox.margin_right == pytest.approx(7.2)
    assert tbox.margin_bottom == pytest.approx(3.6)
    assert tbox.vertical_anchor == "center"
    assert len(tbox.paragraphs) == 1
    paragraph = tbox.paragraphs[0]
    assert paragraph.props.alignment is Alignment.CENTER
    assert len(paragraph.runs) == 1
    text = paragraph.runs[0].text
    assert text is not None
    assert text.text == "DrawingML txBody"
    assert text.props.font_size == 18.0
    assert text.props.bold is True
    assert text.props.color == (192, 0, 0)
    assert text.props.font_ascii == "Times New Roman"
    assert text.props.font_h_ansi == "Times New Roman"


def test_parse_textbox_warns_when_visible_txbody_content_is_unsupported(caplog):
    """Unsupported visible shape text must degrade visibly, without crashing."""
    xml = f"""
    <w:drawing xmlns:w="{NS.W}" xmlns:a="{A}" xmlns:wp="{WP}">
      <wp:inline>
        <wp:extent cx="1000" cy="1000"/>
        <a:graphic><a:graphicData>
          <a:txBody>
            <a:bodyPr/><a:lstStyle/>
            <a:p><a:futureText><a:t>must not vanish silently</a:t></a:futureText></a:p>
          </a:txBody>
        </a:graphicData></a:graphic>
      </wp:inline>
    </w:drawing>
    """

    with caplog.at_level("WARNING", logger="docx2img.parse.drawing"):
        tbox = DrawingParser().parse_textbox(ET.fromstring(xml))

    assert tbox is not None
    assert len(tbox.paragraphs) == 1
    assert tbox.paragraphs[0].runs == []
    assert "drawingml_txbody_unsupported" in caplog.text


def test_parse_txbody_warns_for_cached_field_and_unsupported_theme_color(caplog):
    """Visible approximations remain rendered but are never silent."""
    xml = f"""
    <w:drawing xmlns:w="{NS.W}" xmlns:a="{A}" xmlns:wp="{WP}">
      <wp:inline>
        <wp:extent cx="1000" cy="1000"/>
        <a:graphic><a:graphicData>
          <a:txBody>
            <a:bodyPr/><a:lstStyle/>
            <a:p><a:fld id="{{field-id}}" type="slidenum">
              <a:rPr><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:rPr>
              <a:t>7</a:t>
            </a:fld></a:p>
          </a:txBody>
        </a:graphicData></a:graphic>
      </wp:inline>
    </w:drawing>
    """

    with caplog.at_level("WARNING", logger="docx2img.parse.drawing"):
        tbox = DrawingParser().parse_textbox(ET.fromstring(xml))

    assert tbox is not None
    assert tbox.paragraphs[0].runs[0].text.text == "7"
    assert "drawingml_txbody_field_cached" in caplog.text
    assert "drawingml_txbody_unsupported_color" in caplog.text
