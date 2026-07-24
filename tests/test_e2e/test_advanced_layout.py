"""P6 advanced layout: justify, tabs, float wrap, textbox."""

from pathlib import Path

import pytest

from docx2img import convert_to_images, Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.layout.engine import LayoutEngine
from docx2img.model.enums import Alignment
from docx2img.model.paragraph import Paragraph
from tests.fixtures.gen_fixtures import (
    make_justify_tabs,
    make_float_image,
    make_textbox,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUT = Path(__file__).parent.parent / "output" / "e2e"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_justify_tabs(FIXTURES / "justify_tabs.docx")
    make_float_image(FIXTURES / "float_image.docx")
    make_textbox(FIXTURES / "textbox.docx")
    OUTPUT.mkdir(parents=True, exist_ok=True)


class TestJustifyTabs:
    def test_parse_justify_and_tabs(self):
        package = Unpacker(FIXTURES / "justify_tabs.docx").unpack()
        model = DocumentParser(package, Config()).parse()
        paras = [b for b in model.body if isinstance(b, Paragraph)]
        assert paras[0].props.alignment == Alignment.JUSTIFY
        assert len(paras[1].props.tab_stops) >= 1
        assert any(r.tab for r in paras[1].runs)

    def test_justify_expands_non_last_line(self):
        package = Unpacker(FIXTURES / "justify_tabs.docx").unpack()
        config = Config(dpi=96)
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()
        block = pages[0].blocks[0]
        assert len(block.lines) >= 2
        first = block.lines[0]
        # First line should be stretched close to available width
        assert first.width >= getattr(first, "_wrap_width", block.width) * 0.85 or (
            first.glyphs and first.glyphs[-1].x + first.glyphs[-1].width
            >= block.x + block.width * 0.8
        )

    def test_render_justify_tabs(self):
        images = convert_to_images(FIXTURES / "justify_tabs.docx", Config(dpi=120))
        assert len(images) >= 1
        images[0].save(OUTPUT / "justify_tabs.png")


class TestFloatWrap:
    def test_parse_float(self):
        package = Unpacker(FIXTURES / "float_image.docx").unpack()
        model = DocumentParser(package, Config()).parse()
        para = next(b for b in model.body if isinstance(b, Paragraph))
        imgs = [r.image for r in para.runs if r.image]
        assert len(imgs) == 1
        assert imgs[0].wrap_type == "square"
        assert imgs[0].pos_x is not None

    def test_layout_float_and_narrow_lines(self):
        package = Unpacker(FIXTURES / "float_image.docx").unpack()
        config = Config(dpi=96)
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()
        assert pages[0].float_boxes
        fb = pages[0].float_boxes[0]
        assert fb.width > 20 and fb.height > 20
        # At least one content line should be narrower due to exclusion
        narrow = False
        for block in pages[0].blocks:
            for line in block.lines:
                ww = getattr(line, "_wrap_width", None)
                if ww is not None and ww < block.width * 0.75:
                    narrow = True
        assert narrow

    def test_render_float(self):
        images = convert_to_images(FIXTURES / "float_image.docx", Config(dpi=120))
        pixels = list(images[0].getdata())
        greens = sum(1 for p in pixels if p[1] > 140 and p[0] < 80 and p[2] < 80)
        assert greens > 30
        images[0].save(OUTPUT / "float_image.png")


class TestTextBox:
    def test_parse_and_layout_textbox(self):
        package = Unpacker(FIXTURES / "textbox.docx").unpack()
        model = DocumentParser(package, Config()).parse()
        para = next(b for b in model.body if isinstance(b, Paragraph))
        boxes = [r.textbox for r in para.runs if r.textbox]
        assert len(boxes) == 1
        assert boxes[0].paragraphs

        pages = LayoutEngine(model, Config(dpi=96)).layout()
        assert pages[0].textbox_boxes
        assert pages[0].textbox_boxes[0]["blocks"]

    def test_render_textbox(self):
        images = convert_to_images(FIXTURES / "textbox.docx", Config(dpi=120))
        assert images[0].size[0] > 100
        images[0].save(OUTPUT / "textbox.png")
