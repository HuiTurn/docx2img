"""Header content controls expose their visible cached content."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.model.paragraph import Paragraph
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_header_sdt


def test_header_sdt_content_reaches_model_layout_and_pixels(tmp_path, caplog):
    docx = make_header_sdt(tmp_path / "header_sdt.docx")
    config = Config(dpi=96)

    with caplog.at_level(logging.WARNING):
        model = DocumentParser(Unpacker(docx).unpack(), config).parse()

    header = model.sections[0].header_bodies["default"]
    assert len(header) == 1
    assert isinstance(header[0], Paragraph)
    assert "".join(
        run.text.text for run in header[0].runs if run.text is not None
    ) == "Controlled header"
    assert (
        "header_footer_sdt_fallback: rendered content without "
        "control appearance"
        in caplog.text
    )

    pages = LayoutEngine(model, config).layout()
    assert len(pages) == 1
    assert len(pages[0].header_blocks) == 1

    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 1
    assert first[0].tobytes() == second[0].tobytes()
