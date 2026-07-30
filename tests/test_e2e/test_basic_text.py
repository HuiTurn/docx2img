"""End-to-end P0 tests: docx → PNG."""

from pathlib import Path

import pytest
from PIL import Image

from docx2img import convert, convert_to_images, Config
from docx2img.layout.line_breaker import LineBreaker
from tests.fixtures.gen_fixtures import make_basic_text, make_long_wrap, make_landscape, make_styled

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUT = Path(__file__).parent.parent / "output" / "e2e"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_basic_text(FIXTURES / "basic_text.docx")
    make_long_wrap(FIXTURES / "long_wrap.docx")
    make_landscape(FIXTURES / "landscape.docx")
    make_styled(FIXTURES / "styled_text.docx")
    OUTPUT.mkdir(parents=True, exist_ok=True)


class TestE2EP0:
    def test_basic_text_renders_pages(self):
        images = convert_to_images(FIXTURES / "basic_text.docx", Config(dpi=120))
        assert len(images) >= 2  # hard page break → ≥2 pages
        for img in images:
            assert isinstance(img, Image.Image)
            assert img.size[0] > 100
            assert img.size[1] > 100
            # Not blank: some non-white pixels
            extrema = img.convert("L").getextrema()
            assert extrema[0] < 250

        out = OUTPUT / "basic_text.png"
        convert(FIXTURES / "basic_text.docx", out, dpi=120)
        assert out.exists() or (OUTPUT / "basic_text_1.png").exists()

    def test_long_wrap_multiple_lines(self):
        from docx2img.unpack.unpacker import Unpacker
        from docx2img.parse.document import DocumentParser
        from docx2img.layout.engine import LayoutEngine

        config = Config(dpi=150)
        package = Unpacker(FIXTURES / "long_wrap.docx").unpack()
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()

        assert len(pages) >= 1
        assert len(pages[0].blocks) >= 1
        lines = pages[0].blocks[0].lines
        assert len(lines) > 3  # must wrap

    def test_landscape_dimensions(self):
        images = convert_to_images(FIXTURES / "landscape.docx", Config(dpi=96))
        assert len(images) == 1
        w, h = images[0].size
        assert w > h  # landscape

    def test_alignment_positions(self):
        from docx2img.unpack.unpacker import Unpacker
        from docx2img.parse.document import DocumentParser
        from docx2img.layout.engine import LayoutEngine
        from docx2img.model.enums import Alignment

        config = Config(dpi=96)
        package = Unpacker(FIXTURES / "basic_text.docx").unpack()
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()

        found_center = found_right = False
        for page in pages:
            for block in page.blocks:
                if not hasattr(block.element, "props"):
                    continue
                align = block.element.props.alignment
                if align == Alignment.CENTER and block.lines:
                    line = block.lines[0]
                    assert line.x > page.margin_left
                    found_center = True
                if align == Alignment.RIGHT and block.lines:
                    line = block.lines[0]
                    right_edge = page.width - page.margin_right
                    assert line.x + line.width <= right_edge + 2
                    assert line.x > page.margin_left
                    found_right = True
        assert found_center and found_right

    def test_styled_heading_inherits(self):
        from docx2img.unpack.unpacker import Unpacker
        from docx2img.parse.document import DocumentParser
        from docx2img.model.paragraph import Paragraph

        config = Config(dpi=96)
        package = Unpacker(FIXTURES / "styled_text.docx").unpack()
        model = DocumentParser(package, config).parse()

        assert "Heading1" in model.styles.styles
        heading = model.body[0]
        assert isinstance(heading, Paragraph)
        assert heading.props.style_id == "Heading1"
        assert heading.runs[0].text.props.bold is True
        assert heading.runs[0].text.props.font_size == 16.0
        assert heading.runs[0].text.props.color == (0x2F, 0x54, 0x96)

        body = model.body[1]
        assert isinstance(body, Paragraph)
        emph = [r for r in body.runs if r.text and r.text.text == "emphasized"]
        assert emph and emph[0].text.props.italic is True

        images = convert_to_images(FIXTURES / "styled_text.docx", config)
        assert len(images) >= 1
        assert images[0].convert("L").getextrema()[0] < 250


class TestLineBreakerWrapping:
    def test_wrap_latin_words(self):
        from docx2img.model.paragraph import Paragraph, Run, TextRun, RunProps

        config = Config(dpi=96)
        breaker = LineBreaker(config)
        para = Paragraph()
        props = RunProps(font_size=12)
        para.runs.append(
            Run(text=TextRun(text="one two three four five six seven eight nine ten", props=props))
        )
        lines = breaker.break_paragraph(para, available_width=80, px_per_pt=config.px_per_pt)
        assert len(lines) > 1
        for line in lines:
            assert line.width <= 80 + 30

    def test_wrap_does_not_put_space_at_start_of_continuation(self):
        """Word omits the inter-word space used as the soft-wrap opportunity."""
        from docx2img.model.paragraph import Paragraph, Run, TextRun, RunProps, ParaProps

        config = Config(dpi=150)
        breaker = LineBreaker(config)
        para = Paragraph()
        para.props = ParaProps()
        props = RunProps(font_size=12, font_ascii="Times New Roman")
        para.runs.append(
            Run(
                text=TextRun(
                    text=(
                        "This is an English paragraph that should wrap correctly "
                        "when the line becomes too long for the page width."
                    ),
                    props=props,
                )
            )
        )
        lines = breaker.break_paragraph(
            para, available_width=400, px_per_pt=config.px_per_pt
        )
        assert len(lines) > 1
        for i, line in enumerate(lines):
            text = "".join(g.text or "" for g in line.glyphs)
            if i > 0:
                assert not text.startswith(" "), repr(text)
            assert not text.endswith(" "), repr(text)
    def test_cjk_wrap_keeps_last_fitting_character(self):
        from docx2img.model.paragraph import Paragraph, Run, TextRun, RunProps

        config = Config(dpi=96)
        breaker = LineBreaker(config)
        props = RunProps(font_size=12)
        para = Paragraph(runs=[Run(text=TextRun(text="甲乙丙丁戊己", props=props))])
        units = breaker._tokenize(
            [(para.runs[0].text.text, props, None, None, None)],
            config.px_per_pt,
        )
        char_width = units[0]["width"]

        lines = breaker.break_paragraph(
            para,
            available_width=char_width * 4.5,
            px_per_pt=config.px_per_pt,
        )

        assert "".join(g.text for g in lines[0].glyphs) == "甲乙丙丁"

    def test_justified_cjk_allows_small_width_compression(self):
        from docx2img.model.enums import Alignment
        from docx2img.model.paragraph import Paragraph, Run, TextRun, RunProps

        config = Config(dpi=96)
        breaker = LineBreaker(config)
        props = RunProps(font_size=12)
        text = "甲" * 30
        para = Paragraph(runs=[Run(text=TextRun(text=text, props=props))])
        para.props.alignment = Alignment.JUSTIFY
        units = breaker._tokenize(
            [(text, props, None, None, None)],
            config.px_per_pt,
        )
        char_width = units[0]["width"]

        lines = breaker.break_paragraph(
            para,
            available_width=char_width * 29.8,
            px_per_pt=config.px_per_pt,
        )

        assert len(lines) == 1

    def test_justified_cjk_hangs_closing_punctuation_at_right_edge(self):
        from docx2img.model.enums import Alignment
        from docx2img.model.paragraph import Paragraph, Run, TextRun, RunProps

        config = Config(dpi=96)
        breaker = LineBreaker(config)
        props = RunProps(font_size=12)
        text = "甲" * 28 + "；" + "乙" * 28
        para = Paragraph(runs=[Run(text=TextRun(text=text, props=props))])
        para.props.alignment = Alignment.JUSTIFY
        units = breaker._tokenize(
            [(text, props, None, None, None)],
            config.px_per_pt,
        )
        char_width = units[0]["width"]

        lines = breaker.break_paragraph(
            para,
            available_width=char_width * 27.8,
            px_per_pt=config.px_per_pt,
        )

        assert len(lines) == 2
        assert "".join(g.text for g in lines[0].glyphs).endswith("；")
        assert getattr(lines[0], "_hanging_end_width", 0.0) > 0
