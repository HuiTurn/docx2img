"""P4 header / footer / page number tests."""

from pathlib import Path

import pytest

from docx2img import convert_to_images, Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.layout.engine import LayoutEngine
from tests.fixtures.gen_fixtures import make_header_footer

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUT = Path(__file__).parent.parent / "output" / "e2e"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_header_footer(FIXTURES / "headers_footers.docx")
    OUTPUT.mkdir(parents=True, exist_ok=True)


class TestHeaderFooter:
    def test_parse_refs_and_bodies(self):
        package = Unpacker(FIXTURES / "headers_footers.docx").unpack()
        assert "rId20" in package.headers
        assert "rId21" in package.footers
        model = DocumentParser(package, Config()).parse()
        section = model.sections[-1]
        assert "default" in section.header_refs
        assert section.header_bodies.get("default")
        assert section.footer_bodies.get("default")

    def test_layout_has_header_footer(self):
        package = Unpacker(FIXTURES / "headers_footers.docx").unpack()
        config = Config(dpi=96)
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()
        assert len(pages) >= 2
        for i, page in enumerate(pages):
            assert page.header_blocks, f"page {i} missing header"
            assert page.footer_blocks, f"page {i} missing footer"
            # Footer should contain page number text
            texts = []
            for b in page.footer_blocks:
                for line in b.lines:
                    for g in line.glyphs:
                        if g.text:
                            texts.append(g.text)
            joined = "".join(texts)
            assert str(page.page_number) in joined
            assert str(page.total_pages) in joined

    def test_render(self):
        images = convert_to_images(FIXTURES / "headers_footers.docx", Config(dpi=120))
        assert len(images) >= 2
        for i, img in enumerate(images):
            img.save(OUTPUT / f"header_footer_{i+1}.png")
            assert img.convert("L").getextrema()[0] < 250
