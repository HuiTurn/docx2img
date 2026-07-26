"""P7 OMML math layout / render tests."""

from pathlib import Path

import pytest

from docx2img import convert_to_images, Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.parse.math_omml import OmmlParser
from docx2img.layout.engine import LayoutEngine
from docx2img.layout.math_layout import MathLayoutEngine
from docx2img.model.math_ast import MathBar, MathFrac, MathSup, MathRad, MathNary
from docx2img.model.paragraph import Paragraph
from tests.fixtures.gen_fixtures import make_math

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUT = Path(__file__).parent.parent / "output" / "e2e"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_math(FIXTURES / "math.docx")
    OUTPUT.mkdir(parents=True, exist_ok=True)


class TestOmmlParser:
    def test_frac_sup_rad_nary(self):
        p = OmmlParser()
        frac = p.parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num>"
            b"<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:oMath>"
        )
        assert isinstance(frac, MathFrac)

        sup = p.parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e>"
            b"<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:oMath>"
        )
        assert isinstance(sup, MathSup)

        rad = p.parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:rad><m:deg/><m:e><m:r><m:t>2</m:t></m:r></m:e></m:rad></m:oMath>"
        )
        assert isinstance(rad, MathRad)

        nary = p.parse_xml(
            (
                '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
                '<m:nary><m:naryPr><m:chr m:val="∑"/></m:naryPr>'
                "<m:sub><m:r><m:t>i</m:t></m:r></m:sub>"
                "<m:sup><m:r><m:t>n</m:t></m:r></m:sup>"
                "<m:e><m:r><m:t>i</m:t></m:r></m:e></m:nary></m:oMath>"
            ).encode("utf-8")
        )
        assert isinstance(nary, MathNary)
        assert nary.char == "∑"

    def test_bar_has_native_ast_and_position(self):
        bar = OmmlParser().parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b'<m:bar><m:barPr><m:pos m:val="bot"/></m:barPr>'
            b"<m:e><m:r><m:t>xy</m:t></m:r></m:e></m:bar></m:oMath>"
        )
        assert isinstance(bar, MathBar)
        assert bar.position == "bottom"
        assert bar.body is not None


class TestMathLayoutRender:
    def test_layout_boxes_nonzero(self):
        config = Config(dpi=96)
        eng = MathLayoutEngine(config)
        p = OmmlParser()
        node = p.parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num>"
            b"<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:oMath>"
        )
        box = eng.layout(node, 14.0)
        assert box.width > 5
        assert box.height > 10
        assert box.texts or box.lines or box.children

    def test_layout_bar_draws_rule_on_requested_side(self):
        parser = OmmlParser()
        body = parser.parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:r><m:t>x</m:t></m:r></m:oMath>"
        )
        engine = MathLayoutEngine(Config(dpi=96))
        top = engine.layout(MathBar(body=body), 14.0)
        bottom = engine.layout(MathBar(body=body, position="bottom"), 14.0)

        assert len(top.lines) == len(bottom.lines) == 1
        assert top.lines[0]["y1"] < min(text["y"] for text in top.texts)
        assert bottom.lines[0]["y1"] > max(text["y"] for text in bottom.texts)

    def test_parse_docx_math_runs(self):
        package = Unpacker(FIXTURES / "math.docx").unpack()
        model = DocumentParser(package, Config()).parse()
        maths = []
        for b in model.body:
            if isinstance(b, Paragraph):
                for r in b.runs:
                    if r.math:
                        maths.append(r.math)
        assert len(maths) >= 3

    def test_layout_math_glyphs(self):
        package = Unpacker(FIXTURES / "math.docx").unpack()
        config = Config(dpi=96)
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()
        math_glyphs = []
        for block in pages[0].blocks:
            for line in block.lines:
                math_glyphs.extend(g for g in line.glyphs if g.math_box is not None)
        assert len(math_glyphs) >= 2
        assert all(g.width > 0 and g.height > 0 for g in math_glyphs)

    def test_render_math(self):
        images = convert_to_images(FIXTURES / "math.docx", Config(dpi=120))
        assert len(images) >= 1
        assert images[0].size[0] > 100
        images[0].save(OUTPUT / "math.png")
