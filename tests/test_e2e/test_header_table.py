"""Header tables use the existing table parse/layout/render pipeline."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.model.table import Table
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_header_table


def test_header_table_reaches_model_layout_and_pixels(tmp_path, caplog):
    docx = make_header_table(tmp_path / "header_table.docx")
    config = Config(dpi=96)

    with caplog.at_level(logging.WARNING):
        model = DocumentParser(Unpacker(docx).unpack(), config).parse()

    header = model.sections[0].header_bodies["default"]
    assert len(header) == 1
    assert isinstance(header[0], Table)
    assert len(header[0].rows) == 1
    assert len(header[0].rows[0].cells) == 2
    assert header[0].rows[0].cells[0].props.shading == (217, 234, 247)
    assert (
        header[0].rows[0].cells[0].blocks[0].runs[0].text.text
        == "Header left"
    )
    assert "header_footer_table_" not in caplog.text

    pages = LayoutEngine(model, config).layout()
    assert len(pages) == 1
    assert len(pages[0].header_blocks) == 1
    assert pages[0].header_blocks[0].table_box is not None

    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 1
    assert first[0].tobytes() == second[0].tobytes()
    rgb = first[0].convert("RGB").tobytes()
    assert any(
        rgb[index + 2] > 230
        and rgb[index + 2] - rgb[index] > 10
        for index in range(0, len(rgb), 3)
    )
