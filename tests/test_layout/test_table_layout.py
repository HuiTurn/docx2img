"""Focused table autofit sizing tests."""

import pytest

from docx2img.config import Config
from docx2img.layout.line_breaker import LineBreaker
from docx2img.layout.table_layout import TableLayoutEngine
from docx2img.model.paragraph import Paragraph, Run, RunProps, TextRun
from docx2img.model.table import Cell, Row, Table


def _cell(text: str) -> Cell:
    props = RunProps(font_ascii="Arial", font_h_ansi="Arial", font_size=12.0)
    para = Paragraph(runs=[Run(text=TextRun(text=text, props=props))])
    return Cell(blocks=[para])


def _layout_engine() -> TableLayoutEngine:
    config = Config(dpi=72)
    return TableLayoutEngine(config, LineBreaker(config), None)


def test_autofit_gives_more_width_to_wider_content():
    table = Table(
        rows=[Row(cells=[_cell("A substantially wider value"), _cell("x")])],
        col_widths=[50.0, 50.0],
    )
    table.props.layout = "autofit"

    widths = _layout_engine()._calc_col_widths(
        table, available_width=300.0, px_per_pt=1.0, n_cols=2
    )

    assert sum(widths) == pytest.approx(300.0)
    assert widths[0] > widths[1]


def test_autofit_overflow_falls_back_to_scaled_grid_ratio():
    long_text = "unbreakable" * 20
    table = Table(
        rows=[Row(cells=[_cell(long_text), _cell(long_text)])],
        col_widths=[60.0, 40.0],
    )
    table.props.layout = "autofit"

    widths = _layout_engine()._calc_col_widths(
        table, available_width=100.0, px_per_pt=1.0, n_cols=2
    )

    assert widths == pytest.approx([60.0, 40.0])
