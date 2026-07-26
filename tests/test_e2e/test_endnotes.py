"""Basic endnote parsing, document-end layout, and rendering."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_endnote


def test_endnote_reference_and_definition_reach_model(tmp_path):
    docx = make_endnote(tmp_path / "endnote.docx")
    package = Unpacker(docx).unpack()
    assert package.endnotes_xml
    model = DocumentParser(package, Config(dpi=96)).parse()
    assert "1" in model.endnotes
    refs = [
        run.endnote_id
        for paragraph in model.body
        for run in getattr(paragraph, "runs", [])
        if run.endnote_id is not None
    ]
    assert refs == ["1"]


def test_endnote_is_attached_after_document_body(tmp_path):
    docx = make_endnote(tmp_path / "endnote.docx")
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    page = LayoutEngine(model, config).layout()[-1]
    assert page.endnote_blocks
    body_bottom = max(block.y + block.height for block in page.blocks)
    note_top = min(block.y for block in page.endnote_blocks)
    assert note_top > body_bottom
    assert page.endnote_separator is not None


def test_endnote_render_is_deterministic(tmp_path):
    docx = make_endnote(tmp_path / "endnote.docx")
    config = Config(dpi=96)
    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 1
    assert first[0].tobytes() == second[0].tobytes()


def test_missing_endnote_definition_warns_without_crashing(tmp_path, caplog):
    docx = make_endnote(tmp_path / "endnote.docx")
    package = Unpacker(docx).unpack()
    package.endnotes_xml = (
        b'<w:endnotes xmlns:w="http://schemas.openxmlformats.org/'
        b'wordprocessingml/2006/main"/>'
    )
    with caplog.at_level(logging.WARNING):
        model = DocumentParser(package, Config(dpi=96)).parse()
    assert not model.endnotes
    assert "endnote_missing_definition: reference 1" in caplog.text


def test_oversized_endnote_layout_warns(tmp_path, caplog):
    docx = make_endnote(tmp_path / "endnote.docx")
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    model.endnotes["1"] *= 80
    with caplog.at_level(logging.WARNING):
        pages = LayoutEngine(model, config).layout()
    assert pages[-1].endnote_blocks
    assert "endnote_layout_overflow" in caplog.text
