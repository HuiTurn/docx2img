"""Basic footnote parsing, page attachment, and rendering."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_footnote


def test_footnote_reference_and_definition_reach_model(tmp_path):
    docx = make_footnote(tmp_path / "footnote.docx")
    package = Unpacker(docx).unpack()
    assert package.footnotes_xml
    model = DocumentParser(package, Config(dpi=96)).parse()
    assert "1" in model.footnotes
    refs = [
        run.footnote_id
        for paragraph in model.body
        for run in getattr(paragraph, "runs", [])
        if run.footnote_id is not None
    ]
    assert refs == ["1"]


def test_footnote_is_attached_to_page_bottom(tmp_path):
    docx = make_footnote(tmp_path / "footnote.docx")
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    page = LayoutEngine(model, config).layout()[0]
    assert page.footnote_blocks
    body_bottom = max(block.y + block.height for block in page.blocks)
    note_top = min(block.y for block in page.footnote_blocks)
    assert note_top > body_bottom
    assert page.footnote_separator is not None


def test_footnote_render_is_deterministic(tmp_path):
    docx = make_footnote(tmp_path / "footnote.docx")
    config = Config(dpi=96)
    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 1
    assert first[0].tobytes() == second[0].tobytes()
    image = first[0].convert("L")
    lower_half = image.crop((0, image.height // 2, image.width, image.height))
    assert lower_half.getextrema()[0] < 245


def test_missing_footnote_definition_warns_without_crashing(tmp_path, caplog):
    docx = make_footnote(tmp_path / "footnote.docx")
    package = Unpacker(docx).unpack()
    package.footnotes_xml = (
        b'<w:footnotes xmlns:w="http://schemas.openxmlformats.org/'
        b'wordprocessingml/2006/main"/>'
    )
    with caplog.at_level(logging.WARNING):
        model = DocumentParser(package, Config(dpi=96)).parse()
    assert not model.footnotes
    assert "footnote_missing_definition: reference 1" in caplog.text
