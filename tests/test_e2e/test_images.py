"""P3 inline image tests."""

from pathlib import Path

import pytest
from PIL import Image

from docx2img import convert_to_images, Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.layout.engine import LayoutEngine
from docx2img.model.paragraph import Paragraph
from tests.fixtures.gen_fixtures import make_inline_image

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUT = Path(__file__).parent.parent / "output" / "e2e"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_inline_image(FIXTURES / "images.docx")
    OUTPUT.mkdir(parents=True, exist_ok=True)


class TestInlineImage:
    def test_parse_image_run(self):
        package = Unpacker(FIXTURES / "images.docx").unpack()
        assert any("image1" in k or k.endswith(".png") for k in package.media)
        model = DocumentParser(package, Config()).parse()
        para = next(b for b in model.body if isinstance(b, Paragraph))
        images = [r for r in para.runs if r.image]
        assert len(images) == 1
        assert images[0].image.width_emu > 0
        assert images[0].image.data is not None
        assert images[0].image.wrap_type == "inline"

    def test_layout_image_glyph(self):
        package = Unpacker(FIXTURES / "images.docx").unpack()
        config = Config(dpi=96)
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()
        glyphs = []
        for block in pages[0].blocks:
            for line in block.lines:
                glyphs.extend(line.glyphs)
        img_glyphs = [g for g in glyphs if g.image is not None]
        assert len(img_glyphs) == 1
        assert img_glyphs[0].width > 20
        assert img_glyphs[0].height > 20

    def test_render_image(self):
        images = convert_to_images(FIXTURES / "images.docx", Config(dpi=120))
        assert len(images) >= 1
        img = images[0]
        # Blue-ish pixels from the fixture PNG should appear
        pixels = list(img.getdata())
        blues = sum(1 for p in pixels if p[2] > 180 and p[0] < 100)
        assert blues > 50
        img.save(OUTPUT / "images.png")
