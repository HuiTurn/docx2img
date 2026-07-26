"""Multi-paragraph endnotes continue across document-end pages."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_endnote_continuation


def test_long_endnote_paragraphs_continue_on_second_page(tmp_path, caplog):
    docx = make_endnote_continuation(
        tmp_path / "endnote_continuation.docx"
    )
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    assert len(model.endnotes["1"]) == 18

    with caplog.at_level(logging.WARNING):
        pages = LayoutEngine(model, config).layout()

    assert len(pages) == 2
    assert pages[0].endnote_blocks
    assert pages[1].endnote_blocks
    assert pages[1].endnote_continuation
    assert sum(len(page.endnote_blocks) for page in pages) == 18
    first_separator = pages[0].endnote_separator
    continuation_separator = pages[1].endnote_separator
    assert continuation_separator[2] - continuation_separator[0] > (
        first_separator[2] - first_separator[0]
    )
    assert "endnote_layout_overflow" not in caplog.text


def test_long_endnote_render_is_deterministic(tmp_path):
    docx = make_endnote_continuation(
        tmp_path / "endnote_continuation.docx"
    )
    config = Config(dpi=96)
    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 2
    assert all(a.tobytes() == b.tobytes() for a, b in zip(first, second))
