"""P3 multi-section and columns tests."""

from pathlib import Path

import pytest

from docx2img import convert_to_images, Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.layout.engine import LayoutEngine
from tests.fixtures.gen_fixtures import make_two_sections, make_two_columns

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUT = Path(__file__).parent.parent / "output" / "e2e"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_two_sections(FIXTURES / "two_sections.docx")
    make_two_columns(FIXTURES / "two_columns.docx")
    OUTPUT.mkdir(parents=True, exist_ok=True)


class TestMultiSection:
    def test_parse_two_sections(self):
        package = Unpacker(FIXTURES / "two_sections.docx").unpack()
        model = DocumentParser(package, Config()).parse()
        assert len(model.sections) >= 2
        # Second section landscape: w > h
        s2 = model.sections[-1]
        assert s2.page_w > s2.page_h

    def test_layout_different_page_sizes(self):
        package = Unpacker(FIXTURES / "two_sections.docx").unpack()
        config = Config(dpi=72)
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()
        assert len(pages) >= 2
        # At least one landscape page (wider than tall)
        assert any(p.width > p.height for p in pages)
        assert any(p.height >= p.width for p in pages)

    def test_render(self):
        images = convert_to_images(FIXTURES / "two_sections.docx", Config(dpi=96))
        assert len(images) >= 2
        images[0].save(OUTPUT / "section1.png")
        images[1].save(OUTPUT / "section2.png")


class TestColumns:
    def test_parse_col_count(self):
        package = Unpacker(FIXTURES / "two_columns.docx").unpack()
        model = DocumentParser(package, Config()).parse()
        assert model.sections[-1].col_count == 2
        assert model.sections[-1].col_sep is True

    def test_layout_uses_columns(self):
        package = Unpacker(FIXTURES / "two_columns.docx").unpack()
        config = Config(dpi=96)
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()
        assert pages
        page = pages[0]
        mid = page.width / 2
        xs = [b.x for b in page.blocks]
        assert any(x < mid for x in xs)
        assert any(x >= mid * 0.85 for x in xs), f"no right-column blocks, xs={xs}"
        # Column content width should be ~half
        assert any(b.width < page.width * 0.55 for b in page.blocks)

    def test_render_columns(self):
        images = convert_to_images(FIXTURES / "two_columns.docx", Config(dpi=120))
        assert images[0].convert("L").getextrema()[0] < 250
        images[0].save(OUTPUT / "two_columns.png")
