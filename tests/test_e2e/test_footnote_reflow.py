"""Footnote reservation keeps near-full body flow clear of page-bottom notes."""

from copy import deepcopy
import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_footnote, make_footnote_reflow


def _page_has_reference(page) -> bool:
    return any(
        run.footnote_id is not None
        for block in page.blocks
        for run in getattr(block.element, "runs", [])
    )


def test_footnote_reference_paragraph_reflows_to_clear_page(tmp_path, caplog):
    docx = make_footnote_reflow(tmp_path / "footnote_reflow.docx")
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    with caplog.at_level(logging.WARNING):
        pages = LayoutEngine(model, config).layout()

    assert len(pages) == 2
    assert not _page_has_reference(pages[0])
    assert _page_has_reference(pages[1])
    assert not pages[0].footnote_blocks
    assert pages[1].footnote_blocks
    body_bottom = max(block.y + block.height for block in pages[1].blocks)
    assert pages[1].footnote_separator[1] >= body_bottom
    assert "footnote_layout_overlap" not in caplog.text


def test_footnote_reflow_render_is_deterministic(tmp_path):
    docx = make_footnote_reflow(tmp_path / "footnote_reflow.docx")
    config = Config(dpi=96)
    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 2
    assert all(a.tobytes() == b.tobytes() for a, b in zip(first, second))


def test_mixed_oversized_footnote_keeps_visible_warnings(tmp_path, caplog):
    docx = make_footnote(tmp_path / "footnote.docx")
    config = Config(dpi=96)
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    for run in model.footnotes["1"][0].runs:
        if run.text is not None and run.footnote_id is None:
            run.text.text = "oversized footnote text " * 1000
    model.footnotes["1"].append(deepcopy(model.footnotes["1"][0]))
    with caplog.at_level(logging.WARNING):
        pages = LayoutEngine(model, config).layout()
    assert pages[0].footnote_blocks
    assert "footnote_continuation_unresolved" in caplog.text
    assert "footnote_reflow_unresolved" in caplog.text
    assert "footnote_layout_overlap" in caplog.text
