"""Unsupported complex fields retain their cached display result visibly."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_hyperlink_complex_field


def test_complex_hyperlink_field_retains_cached_result_and_warns(
    tmp_path, caplog
):
    docx = make_hyperlink_complex_field(
        tmp_path / "hyperlink_complex_field.docx"
    )
    config = Config(dpi=96)

    with caplog.at_level(logging.WARNING):
        model = DocumentParser(Unpacker(docx).unpack(), config).parse()

    footer = model.sections[0].footer_bodies["default"][0]
    cached = next(
        run.text
        for run in footer.runs
        if run.text is not None
        and run.text.text == "Cached destination"
    )
    assert cached.props.color == (5, 99, 193)
    assert cached.props.underline
    assert (
        "header_footer_complex_field_cached: HYPERLINK rendered cached result"
        in caplog.text
    )

    pages = LayoutEngine(model, config).layout()
    footer_text = "".join(
        glyph.text
        for block in pages[0].footer_blocks
        for line in block.lines
        for glyph in line.glyphs
    )
    assert footer_text == "Link: Cached destination"


def test_complex_hyperlink_cached_render_is_deterministic(tmp_path):
    docx = make_hyperlink_complex_field(
        tmp_path / "hyperlink_complex_field.docx"
    )
    config = Config(dpi=96)
    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 1
    assert first[0].tobytes() == second[0].tobytes()
