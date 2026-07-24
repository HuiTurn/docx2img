"""P2 table parse / layout / e2e tests."""

from pathlib import Path

import pytest
from PIL import Image

from docx2img import convert_to_images, Config
from docx2img.unpack.unpacker import Unpacker
from docx2img.parse.document import DocumentParser
from docx2img.layout.engine import LayoutEngine
from docx2img.model.table import Table
from docx2img.model.enums import VerticalMerge
from tests.fixtures.gen_fixtures import (
    make_basic_table,
    make_merged_table,
    make_nested_table,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUT = Path(__file__).parent.parent / "output" / "e2e"


@pytest.fixture(scope="module", autouse=True)
def ensure_fixtures():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_basic_table(FIXTURES / "tables.docx")
    make_merged_table(FIXTURES / "merged_table.docx")
    make_nested_table(FIXTURES / "nested_table.docx")
    OUTPUT.mkdir(parents=True, exist_ok=True)


def _parse(path: Path, dpi: int = 96):
    config = Config(dpi=dpi)
    package = Unpacker(path).unpack()
    model = DocumentParser(package, config).parse()
    return model, config


class TestTableParse:
    def test_basic_3x3(self):
        model, _ = _parse(FIXTURES / "tables.docx")
        tables = [b for b in model.body if isinstance(b, Table)]
        assert len(tables) == 1
        t = tables[0]
        assert len(t.rows) == 3
        assert len(t.col_widths) == 3
        assert len(t.rows[0].cells) == 3
        assert t.rows[0].cells[0].props.shading is not None

    def test_grid_span_and_vmerge(self):
        model, _ = _parse(FIXTURES / "merged_table.docx")
        t = next(b for b in model.body if isinstance(b, Table))
        assert t.rows[0].cells[0].props.grid_span == 2
        assert t.rows[0].cells[1].props.grid_span == 2
        assert t.rows[1].cells[0].props.v_merge == VerticalMerge.RESTART
        assert t.rows[2].cells[0].props.v_merge == VerticalMerge.CONTINUE

    def test_nested_table(self):
        model, _ = _parse(FIXTURES / "nested_table.docx")
        t = next(b for b in model.body if isinstance(b, Table))
        cell0 = t.rows[0].cells[0]
        nested = [b for b in cell0.blocks if isinstance(b, Table)]
        assert len(nested) == 1
        assert len(nested[0].rows) == 1


class TestTableLayout:
    def test_basic_layout_grid(self):
        model, config = _parse(FIXTURES / "tables.docx", dpi=120)
        pages = LayoutEngine(model, config).layout()
        assert pages
        table_blocks = [b for b in pages[0].blocks if b.table_box is not None]
        assert len(table_blocks) == 1
        tb = table_blocks[0].table_box
        assert len(tb.col_widths) == 3
        assert len(tb.row_heights) == 3
        assert len(tb.cells) == 9
        assert tb.width > 100
        assert tb.height > 40

    def test_merged_layout_cell_count(self):
        model, config = _parse(FIXTURES / "merged_table.docx", dpi=120)
        pages = LayoutEngine(model, config).layout()
        tb = next(b.table_box for b in pages[0].blocks if b.table_box)
        # origins: 2 (header) + 4 (row1) + 3 (row2, first is continue) = 9
        assert len(tb.cells) == 9
        # Find vertically merged origin
        vmerged = [c for c in tb.cells if c.row_span > 1]
        assert len(vmerged) == 1
        assert vmerged[0].row_span == 2
        # Find horizontally merged
        hmerged = [c for c in tb.cells if c.col_span > 1]
        assert len(hmerged) >= 2


class TestTableE2E:
    def test_render_basic_table(self):
        images = convert_to_images(FIXTURES / "tables.docx", Config(dpi=120))
        assert len(images) >= 1
        img = images[0]
        assert isinstance(img, Image.Image)
        # Has non-white content
        assert img.convert("L").getextrema()[0] < 250
        img.save(OUTPUT / "tables.png")

    def test_render_merged_table(self):
        images = convert_to_images(FIXTURES / "merged_table.docx", Config(dpi=120))
        assert images[0].convert("L").getextrema()[0] < 250
        images[0].save(OUTPUT / "merged_table.png")

    def test_render_nested_table(self):
        images = convert_to_images(FIXTURES / "nested_table.docx", Config(dpi=120))
        assert images[0].convert("L").getextrema()[0] < 250
        images[0].save(OUTPUT / "nested_table.png")
