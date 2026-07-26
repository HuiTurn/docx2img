"""P7 OMML math layout / render tests."""

from pathlib import Path

import pytest

from docx2img import convert_to_images, Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.parse.math_omml import OmmlParser
from docx2img.layout.engine import LayoutEngine
from docx2img.layout.math_layout import MathLayoutEngine
from docx2img.model.math_ast import (
    MathAccent,
    MathBar,
    MathBorderBox,
    MathEquationArray,
    MathLimit,
    MathFrac,
    MathSup,
    MathRad,
    MathNary,
)
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

    def test_accent_has_native_ast(self):
        accent = OmmlParser().parse_xml(
            (
                '<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                'officeDocument/2006/math"><m:acc>'
                '<m:accPr><m:chr m:val="~"/></m:accPr>'
                '<m:e><m:r><m:t>xy</m:t></m:r></m:e>'
                '</m:acc></m:oMath>'
            ).encode("utf-8")
        )
        assert isinstance(accent, MathAccent)
        assert accent.char == "~"
        assert accent.body is not None

    def test_malformed_accent_warns_without_crashing(self, caplog):
        with caplog.at_level("WARNING", logger="docx2img.parse.math_omml"):
            accent = OmmlParser().parse_xml(
                b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                b'officeDocument/2006/math"><m:acc><m:accPr>'
                b'<m:chr m:val="~"/></m:accPr></m:acc></m:oMath>'
            )
        assert isinstance(accent, MathAccent)
        assert accent.body is None
        assert "omml_acc_missing_body" in caplog.text

    def test_border_box_has_native_ast(self):
        border = OmmlParser().parse_xml(
            (
                '<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                'officeDocument/2006/math"><m:borderBox>'
                '<m:borderBoxPr><m:hideTop m:val="1"/></m:borderBoxPr>'
                '<m:e><m:r><m:t>xy</m:t></m:r></m:e>'
                '</m:borderBox></m:oMath>'
            ).encode("utf-8")
        )
        assert isinstance(border, MathBorderBox)
        assert border.body is not None
        assert border.hide_top is True
        assert border.hide_bottom is False

    def test_malformed_border_box_warns_without_crashing(self, caplog):
        with caplog.at_level("WARNING", logger="docx2img.parse.math_omml"):
            border = OmmlParser().parse_xml(
                b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                b'officeDocument/2006/math"><m:borderBox/>'
                b"</m:oMath>"
            )
        assert isinstance(border, MathBorderBox)
        assert border.body is None
        assert "omml_border_box_missing_body" in caplog.text

    @pytest.mark.parametrize(
        ("tag", "position"),
        (("limUpp", "upper"), ("limLow", "lower")),
    )
    def test_limit_has_native_ast(self, tag, position):
        limit = OmmlParser().parse_xml(
            (
                '<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                f'officeDocument/2006/math"><m:{tag}>'
                '<m:e><m:r><m:t>lim</m:t></m:r></m:e>'
                '<m:lim><m:r><m:t>x</m:t></m:r></m:lim>'
                f"</m:{tag}></m:oMath>"
            ).encode("utf-8")
        )
        assert isinstance(limit, MathLimit)
        assert limit.base is not None
        assert limit.limit is not None
        assert limit.position == position

    def test_malformed_limit_warns_without_crashing(self, caplog):
        with caplog.at_level("WARNING", logger="docx2img.parse.math_omml"):
            limit = OmmlParser().parse_xml(
                b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                b'officeDocument/2006/math"><m:limLow/>'
                b"</m:oMath>"
            )
        assert isinstance(limit, MathLimit)
        assert limit.base is None
        assert limit.limit is None
        assert "omml_limit_missing_base" in caplog.text
        assert "omml_limit_missing_value" in caplog.text

    def test_equation_array_has_native_rows(self):
        equations = OmmlParser().parse_xml(
            (
                '<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                'officeDocument/2006/math"><m:eqArr>'
                '<m:e><m:r><m:t>a=1</m:t></m:r></m:e>'
                '<m:e><m:r><m:t>b=2</m:t></m:r></m:e>'
                '</m:eqArr></m:oMath>'
            ).encode("utf-8")
        )
        assert isinstance(equations, MathEquationArray)
        assert len(equations.rows) == 2

    def test_malformed_equation_array_warns_without_crashing(self, caplog):
        with caplog.at_level("WARNING", logger="docx2img.parse.math_omml"):
            equations = OmmlParser().parse_xml(
                b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                b'officeDocument/2006/math"><m:eqArr/>'
                b"</m:oMath>"
            )
        assert isinstance(equations, MathEquationArray)
        assert equations.rows == []
        assert "omml_eq_arr_missing_rows" in caplog.text


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

    def test_layout_accent_overlays_mark_without_shifting_body(self):
        body = OmmlParser().parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:r><m:t>xy</m:t></m:r></m:oMath>"
        )
        box = MathLayoutEngine(Config(dpi=96)).layout(
            MathAccent(body=body, char="~"),
            14.0,
        )
        assert len(box.texts) >= 2
        accent = next(text for text in box.texts if text["text"] == "~")
        body_text = next(text for text in box.texts if text["text"] != "~")
        assert accent["y"] == body_text["y"]
        assert box.height == pytest.approx(
            max(
                font.getbbox(text["text"])[3] - font.getbbox(text["text"])[1]
                for text in box.texts
                for font in [text["font"]]
            )
        )

    def test_layout_border_box_draws_four_sides_around_body(self):
        body = OmmlParser().parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:r><m:t>xy</m:t></m:r></m:oMath>"
        )
        box = MathLayoutEngine(Config(dpi=96)).layout(
            MathBorderBox(body=body),
            14.0,
        )
        assert len(box.lines) == 4
        assert min(line["x1"] for line in box.lines) == 0
        assert max(line["x2"] for line in box.lines) == box.width
        border_top = min(line["y1"] for line in box.lines)
        assert border_top > 0
        assert max(line["y2"] for line in box.lines) == box.height
        assert min(text["x"] for text in box.texts) > 0
        for text in box.texts:
            bbox = text["font"].getbbox(text["text"])
            assert text["y"] + bbox[1] > border_top
            assert text["y"] + bbox[3] < box.height

    def test_layout_limit_places_value_above_or_below_base(self):
        base = OmmlParser().parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:r><m:t>lim</m:t></m:r></m:oMath>"
        )
        value = OmmlParser().parse_xml(
            b'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            b"<m:r><m:t>x</m:t></m:r></m:oMath>"
        )
        engine = MathLayoutEngine(Config(dpi=96))
        upper = engine.layout(
            MathLimit(base=base, limit=value, position="upper"),
            14.0,
        )
        lower = engine.layout(
            MathLimit(base=base, limit=value, position="lower"),
            14.0,
        )
        for box, relation in ((upper, "upper"), (lower, "lower")):
            value_text = next(text for text in box.texts if text["text"] == "x")
            base_top = min(
                text["y"] for text in box.texts if text["text"] != "x"
            )
            base_bottom = max(
                text["y"] for text in box.texts if text["text"] != "x"
            )
            if relation == "upper":
                assert value_text["y"] < base_top
            else:
                assert value_text["y"] > base_bottom

    def test_layout_equation_array_places_rows_vertically(self):
        rows = [
            OmmlParser().parse_xml(
                (
                    '<m:oMath xmlns:m="http://schemas.openxmlformats.org/'
                    f'officeDocument/2006/math"><m:r><m:t>{text}</m:t>'
                    "</m:r></m:oMath>"
                ).encode("utf-8")
            )
            for text in ("a=1", "b=2")
        ]
        box = MathLayoutEngine(Config(dpi=96)).layout(
            MathEquationArray(rows=rows),
            14.0,
        )
        row_tops = sorted({text["y"] for text in box.texts})
        assert len(row_tops) == 2
        assert row_tops[1] > row_tops[0]
        assert box.height > 0

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
