"""Header/footer field parsing and deterministic expansion tests."""

import logging
from datetime import datetime

from docx2img.config import Config
from docx2img.layout.engine import LayoutEngine
from docx2img.parse.document import DocumentParser
from docx2img.parse.header_footer import (
    FIELD_DATE,
    HeaderFooterParser,
)
from docx2img.parse.namespaces import NS
from docx2img.model.table import Table
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


def test_unsupported_simple_field_without_cache_warns(caplog):
    xml = (
        '<w:ftr xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main">'
        '<w:p><w:fldSimple w:instr=" REF missing "/></w:p></w:ftr>'
    ).encode()
    parser = HeaderFooterParser(lambda elem: "parsed")
    with caplog.at_level(logging.WARNING):
        blocks = parser.parse(xml)
    assert len(blocks) == 1
    assert (
        "header_footer_field_unsupported: REF has no cached result"
        in caplog.text
    )


def test_unsupported_complex_field_without_cache_warns(caplog):
    xml = (
        '<w:ftr xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:p>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText> REF missing </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        "</w:p></w:ftr>"
    ).encode()
    parser = HeaderFooterParser(lambda elem: "parsed")
    with caplog.at_level(logging.WARNING):
        blocks = parser.parse(xml)
    assert len(blocks) == 1
    assert (
        "header_footer_complex_field_unsupported: "
        "REF has no cached result"
        in caplog.text
    )


def test_header_table_without_parser_warns_instead_of_silent_skip(caplog):
    xml = (
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:tbl><w:tr/></w:tbl></w:hdr>'
    ).encode()
    parser = HeaderFooterParser(lambda elem: "parsed")
    with caplog.at_level(logging.WARNING):
        blocks = parser.parse(xml)
    assert blocks == []
    assert (
        "header_footer_table_unsupported: table parser unavailable"
        in caplog.text
    )


def test_malformed_header_table_warns_and_does_not_crash(caplog):
    xml = (
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:tbl/></w:hdr>'
    ).encode()

    def broken_table_parser(_):
        raise ValueError("invalid table width")

    parser = HeaderFooterParser(
        lambda elem: "parsed",
        broken_table_parser,
    )
    with caplog.at_level(logging.WARNING):
        blocks = parser.parse(xml)
    assert blocks == []
    assert (
        "header_footer_table_malformed: invalid table width"
        in caplog.text
    )


def test_empty_header_table_warns_and_is_skipped(caplog):
    xml = (
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:tbl/></w:hdr>'
    ).encode()
    parser = HeaderFooterParser(lambda elem: "parsed", lambda elem: Table())
    with caplog.at_level(logging.WARNING):
        blocks = parser.parse(xml)
    assert blocks == []
    assert "header_footer_table_empty: table has no rows" in caplog.text


def test_header_sdt_without_content_warns_instead_of_silent_skip(caplog):
    xml = (
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:sdt><w:sdtPr/></w:sdt></w:hdr>'
    ).encode()
    parser = HeaderFooterParser(lambda elem: "parsed")
    with caplog.at_level(logging.WARNING):
        blocks = parser.parse(xml)
    assert blocks == []
    assert (
        "header_footer_sdt_unsupported: no sdtContent"
        in caplog.text
    )


def test_header_alternate_content_uses_fallback_for_unknown_requires(caplog):
    xml = (
        f'<w:hdr xmlns:w="{NS.W}" xmlns:mc="{NS.MC}" '
        'xmlns:future="urn:docx2img:future">'
        '<mc:AlternateContent>'
        '<mc:Choice Requires="future"><w:p/></mc:Choice>'
        '<mc:Fallback><w:p/></mc:Fallback>'
        '</mc:AlternateContent></w:hdr>'
    ).encode()
    parser = HeaderFooterParser(lambda elem: "parsed")

    with caplog.at_level(logging.WARNING):
        blocks = parser.parse(xml)

    assert blocks == ["parsed"]
    assert (
        "header_footer_alternate_content_fallback: rendered Fallback; "
        "unsupported Requires=future" in caplog.text
    )


def test_header_alternate_content_without_usable_branch_warns(caplog):
    xml = (
        f'<w:hdr xmlns:w="{NS.W}" xmlns:mc="{NS.MC}" '
        'xmlns:future="urn:docx2img:future">'
        '<mc:AlternateContent>'
        '<mc:Choice Requires="future"><w:p/></mc:Choice>'
        '</mc:AlternateContent></w:hdr>'
    ).encode()
    parser = HeaderFooterParser(lambda elem: "parsed")

    with caplog.at_level(logging.WARNING):
        blocks = parser.parse(xml)

    assert blocks == []
    assert (
        "header_footer_alternate_content_unsupported: no supported Choice "
        "or Fallback" in caplog.text
    )


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
