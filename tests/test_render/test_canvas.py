"""Focused tests for page-level canvas decorations."""

from docx2img.config import Config
from docx2img.layout.engine import PageBox
from docx2img.model.section import PageBorderDef, PageBorders, Section
from docx2img.render.canvas import RenderCanvas


def _bordered_page(display: str = "allPages") -> PageBox:
    section = Section()
    section.page_borders = PageBorders(
        display=display,
        offset_from="page",
        top=PageBorderDef(
            style="single", size=8, space=3, color="CC0000"
        ),
        left=PageBorderDef(
            style="single", size=8, space=7, color="0000CC"
        ),
    )
    return PageBox(
        width=80,
        height=60,
        margin_top=10,
        margin_bottom=10,
        margin_left=10,
        margin_right=10,
        section=section,
    )


def test_page_border_uses_each_side_spacing_and_color():
    page = _bordered_page()
    image = RenderCanvas(Config(dpi=72)).render_pages([page])[0]

    assert image.getpixel((40, 3)) == (204, 0, 0)
    assert image.getpixel((7, 30)) == (0, 0, 204)
    assert image.getpixel((3, 30)) == (255, 255, 255)


def test_first_page_border_uses_section_index_not_restarted_label():
    page = _bordered_page(display="firstPage")
    page.page_number = 7
    page.section_page_index = 0
    first = RenderCanvas(Config(dpi=72)).render_pages([page])[0]
    assert first.getpixel((40, 3)) == (204, 0, 0)

    page.section_page_index = 1
    later = RenderCanvas(Config(dpi=72)).render_pages([page])[0]
    assert later.getpixel((40, 3)) == (255, 255, 255)
