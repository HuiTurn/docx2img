"""P5 list numbering tests."""

from pathlib import Path

import pytest

from docx2img import convert_to_images, Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.layout.engine import LayoutEngine
from docx2img.layout.list_layout import NumberingEngine
from docx2img.model.enums import NumberFormat
from docx2img.model.numbering import NumberingTable, AbstractNum, NumberingInstance, LevelDef
from docx2img.model.paragraph import Paragraph
from tests.fixtures.gen_fixtures import make_lists

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUT = Path(__file__).parent.parent / "output" / "e2e"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_lists(FIXTURES / "lists.docx")
    OUTPUT.mkdir(parents=True, exist_ok=True)


class TestNumberingEngine:
    def test_decimal_and_letter(self):
        table = NumberingTable()
        abs1 = AbstractNum(abstract_num_id=1)
        abs1.levels[0] = LevelDef(level=0, format=NumberFormat.DECIMAL, start=1, text="%1.")
        abs1.levels[1] = LevelDef(level=1, format=NumberFormat.LOWER_LETTER, start=1, text="%2)")
        table.abstract_nums[1] = abs1
        table.instances[2] = NumberingInstance(num_id=2, abstract_num_id=1)

        eng = NumberingEngine(table)
        assert eng.next_label(2, 0)[0] == "1."
        assert eng.next_label(2, 0)[0] == "2."
        assert eng.next_label(2, 1)[0] == "a)"
        assert eng.next_label(2, 0)[0] == "3."  # resets level 1


class TestListsE2E:
    def test_parse_numbering(self):
        package = Unpacker(FIXTURES / "lists.docx").unpack()
        model = DocumentParser(package, Config()).parse()
        assert 1 in model.numbering.instances
        assert 2 in model.numbering.instances
        paras = [b for b in model.body if isinstance(b, Paragraph) and b.props.num_id]
        assert len(paras) >= 5

    def test_layout_labels(self):
        package = Unpacker(FIXTURES / "lists.docx").unpack()
        config = Config(dpi=96)
        model = DocumentParser(package, config).parse()
        pages = LayoutEngine(model, config).layout()
        labels = []
        for block in pages[0].blocks:
            if block.lines and block.lines[0].glyphs:
                labels.append(block.lines[0].glyphs[0].text.strip())
        # Expect bullet and 1. 2. a) 3.
        assert any("•" in t for t in labels)
        assert any(t.startswith("1.") for t in labels)
        assert any(t.startswith("2.") for t in labels)
        assert any("a)" in t for t in labels)

    def test_render(self):
        images = convert_to_images(FIXTURES / "lists.docx", Config(dpi=120))
        images[0].save(OUTPUT / "lists.png")
        assert images[0].convert("L").getextrema()[0] < 250
