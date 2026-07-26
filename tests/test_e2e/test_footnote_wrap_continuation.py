"""Automatically wrapped lines inside one footnote can continue."""

import logging

import pytest

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_footnote_wrap_continuation


def test_wrapped_footnote_lines_continue_on_second_page(tmp_path, caplog):
    docx = make_footnote_wrap_continuation(
        tmp_path / "footnote_wrap_continuation.docx"
    )
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    paragraph = model.footnotes["1"][0]
    assert len(model.footnotes["1"]) == 1
    assert all(run.brk is None for run in paragraph.runs)

    with caplog.at_level(logging.WARNING):
        pages = LayoutEngine(model, config).layout()

    assert len(pages) == 2
    assert [len(page.footnote_blocks[0].lines) for page in pages] == [12, 6]
    assert pages[1].footnote_continuation
    assert pages[0].footnote_blocks[0].lines[1].glyphs[0].x == pytest.approx(
        pages[0].margin_left
    )
    assert pages[1].footnote_blocks[0].lines[0].glyphs[0].x == pytest.approx(
        pages[1].margin_left
    )
    assert "footnote_continuation_unresolved" not in caplog.text
    assert "footnote_layout_overlap" not in caplog.text


def test_wrapped_footnote_line_render_is_deterministic(tmp_path):
    docx = make_footnote_wrap_continuation(
        tmp_path / "footnote_wrap_continuation.docx"
    )
    config = Config(dpi=96)
    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 2
    assert all(a.tobytes() == b.tobytes() for a, b in zip(first, second))
