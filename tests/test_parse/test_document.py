"""Parser unit tests for P0 document.xml."""

from pathlib import Path

from docx2img.config import Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.model.enums import Alignment
from docx2img.model.paragraph import Paragraph
from tests.fixtures.gen_fixtures import make_basic_text

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


def test_parse_page_size():
    path = make_basic_text(FIXTURES / "basic_text.docx")
    package = Unpacker(path).unpack()
    model = DocumentParser(package, Config()).parse()
    section = model.sections[0]
    # A4 ≈ 595.3 x 841.9 pt
    assert abs(section.page_w - 595.3) < 1.0
    assert abs(section.page_h - 841.9) < 1.0
