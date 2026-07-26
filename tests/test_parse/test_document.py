"""Parser unit tests for P0 document.xml."""

import xml.etree.ElementTree as ET
from pathlib import Path

from docx2img.config import Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.model.enums import Alignment
from docx2img.model.document import DocumentModel
from docx2img.model.paragraph import Paragraph
from docx2img.parse.namespaces import NS
from tests.fixtures.gen_fixtures import make_basic_text, make_tracked_changes

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_basic_text():
    path = make_basic_text(FIXTURES / "basic_text.docx")
    package = Unpacker(path).unpack()
    model = DocumentParser(package, Config()).parse()

    assert len(model.sections) == 1
    assert len(model.body) >= 5

    paras = [b for b in model.body if isinstance(b, Paragraph)]
    assert paras[0].props.alignment == Alignment.CENTER
    assert paras[0].runs[0].text.props.bold is True

    # Find colored / highlighted run
    texts = []
    for p in paras:
        for r in p.runs:
            if r.text:
                texts.append(r.text.text)
                if r.text.props.highlight == "yellow":
                    assert r.text.text == "Highlight"
    assert any("Hello World" in t for t in texts)
    assert any("test paragraph" in t.lower() for t in texts)


def test_parse_tracked_changes():
    path = make_tracked_changes(FIXTURES / "tracked_changes.docx")
    package = Unpacker(path).unpack()
    model = DocumentParser(package, Config()).parse()

    paras = [b for b in model.body if isinstance(b, Paragraph)]
    assert len(paras) == 1
    text = "".join(r.text.text for r in paras[0].runs if r.text)
    assert "Before" in text
    assert "inserted" in text
    assert "after" in text
    assert "deleted" not in text


def test_parse_nested_revision_and_hyperlink_content():
    """Accepted content remains visible through nested transparent wrappers."""
    path = make_basic_text(FIXTURES / "basic_text.docx")
    package = Unpacker(path).unpack()
    parser = DocumentParser(package, Config())
    parser.parse()  # initialize style/drawing resolvers

    xml = f"""
    <w:p xmlns:w="{NS.W}">
      <w:ins>
        <w:hyperlink><w:r><w:t>inserted link</w:t></w:r></w:hyperlink>
      </w:ins>
      <w:moveFrom><w:r><w:t>old location</w:t></w:r></w:moveFrom>
      <w:moveTo>
        <w:smartTag><w:r><w:t>new location</w:t></w:r></w:smartTag>
      </w:moveTo>
      <w:del>
        <w:ins><w:r><w:t>nested deletion</w:t></w:r></w:ins>
      </w:del>
      <w:r><w:lastRenderedPageBreak/><w:t>cached page text</w:t></w:r>
      <w:r><w:t>before line</w:t><w:br/><w:t>after line</w:t></w:r>
    </w:p>
    """
    para = parser._parse_paragraph(ET.fromstring(xml))
    text = "".join(r.text.text for r in para.runs if r.text)

    assert text == (
        "inserted linknew locationcached page textbefore lineafter line"
    )
    breaks = [r.brk.break_type for r in para.runs if r.brk]
    assert breaks == ["page", "line"]


def test_body_sdt_without_content_warns_instead_of_silent_skip(caplog):
    path = make_basic_text(FIXTURES / "basic_text.docx")
    package = Unpacker(path).unpack()
    parser = DocumentParser(package, Config())
    parser.parse()
    model = DocumentModel()
    sdt = ET.fromstring(
        f'<w:sdt xmlns:w="{NS.W}"><w:sdtPr/></w:sdt>'
    )

    parser._parse_body_sdt(sdt, model)

    assert model.body == []
    assert "body_sdt_unsupported: no sdtContent" in caplog.text


def test_parse_page_borders_with_independent_sides():
    path = make_basic_text(FIXTURES / "basic_text.docx")
    package = Unpacker(path).unpack()
    parser = DocumentParser(package, Config())
    xml = f"""
    <w:sectPr xmlns:w="{NS.W}">
      <w:docGrid w:type="lines" w:linePitch="360"/>
      <w:pgBorders w:display="notFirstPage" w:offsetFrom="text">
        <w:top w:val="double" w:sz="12" w:space="3" w:color="112233"/>
        <w:left w:val="dashed" w:sz="8" w:space="7" w:color="auto"/>
      </w:pgBorders>
    </w:sectPr>
    """
    section = parser._parse_section(ET.fromstring(xml))

    assert section.page_borders is not None
    assert section.page_borders.display == "notFirstPage"
    assert section.page_borders.offset_from == "text"
    assert section.page_borders.top.style == "double"
    assert section.page_borders.top.size == 12
    assert section.page_borders.top.space == 3
    assert section.page_borders.top.color == "112233"
    assert section.page_borders.left.space == 7
    assert section.page_borders.right.style == "none"
    assert section.doc_grid_type == "lines"
    assert section.doc_grid_line_pitch == 18.0


def test_parse_page_size():
    path = make_basic_text(FIXTURES / "basic_text.docx")
    package = Unpacker(path).unpack()
    model = DocumentParser(package, Config()).parse()
    section = model.sections[0]
    # A4 ≈ 595.3 x 841.9 pt
    assert abs(section.page_w - 595.3) < 1.0
    assert abs(section.page_h - 841.9) < 1.0
