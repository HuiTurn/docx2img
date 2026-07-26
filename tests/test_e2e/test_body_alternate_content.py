"""Block-level markup-compatibility choices preserve visible body content."""

import logging

from docx2img import Config, convert_to_images
from docx2img.layout.engine import LayoutEngine
from docx2img.model.paragraph import Paragraph
from docx2img.parse.document import DocumentParser
from docx2img.unpack.unpacker import Unpacker
from tests.fixtures.gen_fixtures import make_body_alternate_content


def test_body_alternate_content_reaches_model_layout_and_pixels(
    tmp_path, caplog
):
    docx = make_body_alternate_content(
        tmp_path / "body_alternate_content.docx"
    )
    config = Config(dpi=96)

    with caplog.at_level(logging.WARNING):
        model = DocumentParser(Unpacker(docx).unpack(), config).parse()

    assert len(model.body) == 1
    assert isinstance(model.body[0], Paragraph)
    assert "".join(
        run.text.text for run in model.body[0].runs if run.text is not None
    ) == "Alternate body choice"
    assert (
        "body_alternate_content_choice: rendered Choice for supported "
        "Requires=w" in caplog.text
    )

    pages = LayoutEngine(model, config).layout()
    assert len(pages) == 1
    assert len(pages[0].blocks) == 1

    first = convert_to_images(docx, config)
    second = convert_to_images(docx, config)
    assert len(first) == len(second) == 1
    assert first[0].tobytes() == second[0].tobytes()
