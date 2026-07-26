"""Multiple same-page footnotes share continuation pages safely."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_footnote_multiple_continuation


def test_multiple_footnotes_continue_in_definition_order(tmp_path, caplog):
    docx = make_footnote_multiple_continuation(
        tmp_path / "footnote_multiple_continuation.docx"
    )
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    assert len(model.footnotes["1"]) == 5
    assert len(model.footnotes["2"]) == 13

    with caplog.at_level(logging.WARNING):
        pages = LayoutEngine(model, config).layout()

    assert len(pages) == 2
    assert list(pages[0].footnote_paragraph_overrides) == ["1", "2"]
    assert list(pages[1].footnote_paragraph_overrides) == ["2"]
    assert sum(len(page.footnote_blocks) for page in pages) == 18
    assert pages[1].footnote_continuation
    assert "footnote_continuation_multiple_notes" not in caplog.text
    assert "footnote_layout_overlap" not in caplog.text


def test_multiple_footnote_render_is_deterministic(tmp_path):
    docx = make_footnote_multiple_continuation(
        tmp_path / "footnote_multiple_continuation.docx"
    )
    config = Config(dpi=96)
    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 2
    assert all(a.tobytes() == b.tobytes() for a, b in zip(first, second))
