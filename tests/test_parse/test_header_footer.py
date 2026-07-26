"""Header/footer field parsing and deterministic expansion tests."""

from datetime import datetime

from docx2img.config import Config
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.parse.header_footer import (
    FIELD_DATE,
    HeaderFooterParser,
)
from docx2img.unpack.unpacker import Unpacker


def test_date_field_stays_placeholder_until_layout_expansion():
    assert (
        HeaderFooterParser.resolve_field_instr(
            ' DATE \\@ "yyyy-MM-dd" ',
            as_placeholder=True,
        )
        == FIELD_DATE
    )


def test_date_field_uses_explicit_reference_datetime():
    expanded = HeaderFooterParser.expand_placeholders(
        f"Rendered {FIELD_DATE}",
        page_num=1,
        total_pages=1,
        reference_datetime=datetime(2042, 3, 5, 6, 7, 8),
    )
    assert expanded == "Rendered 2042-03-05"


def test_default_reference_datetime_is_fixed():
    first = Config().reference_datetime
    second = Config().reference_datetime
    assert first == second == datetime(2000, 1, 1)


def test_date_fixture_expands_reference_time_during_layout(tmp_path):
    from fixtures.gen_fixtures import make_date_field

    docx = make_date_field(tmp_path / "date_field.docx")
    config = Config(dpi=96, reference_datetime=datetime(2042, 3, 5))
    model = DocumentParser(Unpacker(docx).unpack(), config).parse()
    footer = model.sections[0].footer_bodies["default"][0]
    assert FIELD_DATE in "".join(
        run.text.text for run in footer.runs if run.text is not None
    )

    pages = LayoutEngine(model, config).layout()
    footer_text = "".join(
        glyph.text
        for block in pages[0].footer_blocks
        for line in block.lines
        for glyph in line.glyphs
    )
    assert "Reference date: 2042-03-05" in footer_text
    assert FIELD_DATE not in footer_text
