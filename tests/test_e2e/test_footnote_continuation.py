"""Multi-paragraph footnotes continue across pages without clipping."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.model.paragraph import Run
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_footnote_continuation


def test_long_footnote_paragraphs_continue_on_second_page(tmp_path, caplog):
    docx = make_footnote_continuation(
        tmp_path / "footnote_continuation.docx"
    )
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    assert len(model.footnotes["1"]) == 18

    with caplog.at_level(logging.WARNING):
        pages = LayoutEngine(model, config).layout()

    assert len(pages) == 2
    assert pages[0].footnote_blocks
    assert pages[1].footnote_blocks
    assert pages[1].footnote_continuation
    assert sum(len(page.footnote_blocks) for page in pages) == 18
    first_separator = pages[0].footnote_separator
    continuation_separator = pages[1].footnote_separator
    assert continuation_separator[2] - continuation_separator[0] > (
        first_separator[2] - first_separator[0]
    )
    assert "footnote_layout_overlap" not in caplog.text


def test_long_footnote_render_is_deterministic(tmp_path):
    docx = make_footnote_continuation(
        tmp_path / "footnote_continuation.docx"
    )
    config = Config(dpi=96)
    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 2
    assert all(a.tobytes() == b.tobytes() for a, b in zip(first, second))


def test_multiple_oversized_footnotes_continue_without_silent_drop(
    tmp_path, caplog
):
    docx = make_footnote_continuation(
        tmp_path / "footnote_continuation.docx"
    )
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    model.footnotes["2"] = list(model.footnotes["1"])
    model.body[0].runs.append(Run(footnote_id="2"))

    with caplog.at_level(logging.WARNING):
        pages = LayoutEngine(model, config).layout()

    assert len(pages) > 1
    assert sum(len(page.footnote_blocks) for page in pages) == 36
    assert "footnote_continuation_multiple_notes" not in caplog.text
    assert "footnote_layout_overlap" not in caplog.text
