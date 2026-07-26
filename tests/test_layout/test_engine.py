"""Tests for layout engine"""

import pytest
from src.docx2img.config import Config
from src.docx2img.model.document import DocumentModel
from src.docx2img.model.paragraph import Paragraph, Run, TextRun, ParaProps, RunProps
from src.docx2img.model.section import Section
from src.docx2img.layout.engine import LayoutEngine


class TestLayoutEngine:
    """Test cases for LayoutEngine"""

    def test_create_layout_engine(self):
        """Test creating layout engine"""
        config = Config()
        document = DocumentModel()
        engine = LayoutEngine(document, config)
        assert engine is not None

    def test_canvas_page_ceil_matches_word_pdf_raster(self):
        """Final PNG size must ceil to Word PDF→pdftoppm pixels @150dpi."""
        from src.docx2img.render.canvas import RenderCanvas

        config = Config(dpi=150)
        section = Section()
        # Standard OOXML A4: 11906 × 16838 twips → 595.3 × 841.9 pt
        section.page_w = 11906 / 20.0
        section.page_h = 16838 / 20.0
        document = DocumentModel(sections=[section])
        pages = LayoutEngine(document, config).layout()
        images = RenderCanvas(config).render_pages(pages)
        assert images[0].size == (1241, 1754)

    def test_layout_empty_document(self):
        """Test layout with empty document"""
        config = Config()
        document = DocumentModel()
        engine = LayoutEngine(document, config)
        pages = engine.layout()
        assert len(pages) == 1  # Should have at least one empty page

    def test_layout_single_paragraph(self):
        """Test layout with single paragraph"""
        config = Config()
        
        # Create a simple paragraph
        para = Paragraph()
        para.props = ParaProps()
        
        # Add a text run
        run_props = RunProps()
        run_props.font_size = 12.0
        run_props.color = (0, 0, 0)
        
        text_run = TextRun(text="Hello World", props=run_props)
        run = Run(text=text_run)
        para.runs.append(run)
        
        # Add section
        section = Section()
        section.page_w = 595.0  # A4 width in points
        section.page_h = 842.0  # A4 height in points
        
        document = DocumentModel()
        document.body.append(para)
        document.sections.append(section)
        
        engine = LayoutEngine(document, config)
        pages = engine.layout()
        
        assert len(pages) >= 1
        assert len(pages[0].blocks) >= 1

    def test_layout_multiple_paragraphs(self):
        """Test layout with multiple paragraphs"""
        config = Config()
        
        # Create multiple paragraphs
        paragraphs = []
        for i in range(3):
            para = Paragraph()
            para.props = ParaProps()
            
            run_props = RunProps()
            run_props.font_size = 12.0
            text_run = TextRun(text=f"Paragraph {i}", props=run_props)
            run = Run(text=text_run)
            para.runs.append(run)
            
            paragraphs.append(para)
        
        section = Section()
        document = DocumentModel()
        document.body.extend(paragraphs)
        document.sections.append(section)
        
        engine = LayoutEngine(document, config)
        pages = engine.layout()
        
        assert len(pages) >= 1
        assert len(pages[0].blocks) >= 3

    def test_empty_paragraph_snaps_to_section_document_grid(self):
        """Blank paragraph marks consume one document-grid interval."""
        config = Config()
        section = Section(
            doc_grid_type="lines",
            doc_grid_line_pitch=18.0,
        )
        document = DocumentModel(body=[Paragraph()], sections=[section])

        pages = LayoutEngine(document, config).layout()

        assert pages[0].blocks[0].height == pytest.approx(
            18.0 * config.px_per_pt
        )

    def test_page_break_only_paragraph_has_mark_height(self):
        """A paragraph containing only w:br type=page occupies its mark line
        height (LibreOffice behaviour) so it can itself overflow to the next
        page and produce a blank page before the break fires."""
        from src.docx2img.model.paragraph import BreakRun

        config = Config()
        para = Paragraph()
        para.props = ParaProps()
        para.runs.append(Run(brk=BreakRun(break_type="page")))

        section = Section()
        document = DocumentModel()
        document.body.append(para)
        document.sections.append(section)

        engine = LayoutEngine(document, config)
        blocks = engine._layout_paragraph(para, 0, 400.0, config.dpi / 72.0)
        assert len(blocks) == 1
        assert blocks[0].page_break_after is True
        # Non-zero: paragraph mark line height (was 0.0 before the fix)
        assert blocks[0].height > 5.0

    def test_page_break_paragraph_overflow_makes_blank_page(self):
        """When the break-only paragraph does not fit on the current page it
        moves to the next (blank) page and breaks from there → 3 pages.

        Verified against Word 16.0 (ExportAsFixedFormat → PDF): a manual page
        break paragraph that overflows an already-full page produces a *blank*
        intermediate page before the tail (see the ``page_break`` office golden
        fixture). Geometry here is made deterministic with ``exact`` line
        spacing so the calibration does not depend on font metrics or the
        auto line-height formula: 10 fillers × 20pt exactly fill the 200pt of
        usable height, leaving no room for the 12.48pt break-mark line.
        """
        from src.docx2img.model.paragraph import BreakRun

        config = Config()
        section = Section()
        section.page_w = 595.0
        section.page_h = 300.0
        section.margin_top = 50.0
        section.margin_bottom = 50.0  # usable height = 200pt

        document = DocumentModel()
        # 10 fillers × 20pt (exact) == 200pt → page 1 is filled to the edge.
        for i in range(10):
            para = Paragraph()
            para.props = ParaProps(
                line_spacing_exact=20.0,
                line_spacing_rule="exact",
                space_after=0.0,
            )
            rp = RunProps()
            rp.font_size = 14.0
            para.runs.append(Run(text=TextRun(text=f"Filler {i}", props=rp)))
            document.body.append(para)
        # Break-only paragraph: its mark line (>5pt) cannot fit on page 1.
        brk_para = Paragraph()
        brk_para.props = ParaProps()
        brk_para.runs.append(Run(brk=BreakRun(break_type="page")))
        document.body.append(brk_para)
        # Content after the break
        tail = Paragraph()
        tail.props = ParaProps()
        rp = RunProps()
        rp.font_size = 14.0
        tail.runs.append(Run(text=TextRun(text="After break", props=rp)))
        document.body.append(tail)
        document.sections.append(section)

        engine = LayoutEngine(document, config)
        pages = engine.layout()

        def _page_text(page):
            return [
                g.text
                for b in page.blocks
                for ln in b.lines
                for g in ln.glyphs
                if g.text and g.text.strip()
            ]

        # Page 1: 10 fillers; page 2: invisible break para (blank); page 3: tail
        assert len(pages) == 3
        assert _page_text(pages[0]), "page 1 should be full of filler text"
        assert not _page_text(pages[1]), "page 2 must be blank (break mark only)"
        assert "After" in _page_text(pages[2])

    def test_generated_page_break_fixture_preserves_blank_middle_page(self, tmp_path):
        """The minimal OOXML office fixture keeps Word's blank middle page.

        Unlike the exact-height unit case above, this exercises parsing and
        the real docDefaults spacing where only the break paragraph's trailing
        spacing crosses the page boundary.
        """
        import io

        from tests.fixtures.gen_fixtures import make_page_break
        from src.docx2img.parse.document import DocumentParser
        from src.docx2img.render.canvas import RenderCanvas
        from src.docx2img.unpack.unpacker import Unpacker

        docx = make_page_break(tmp_path / "page_break.docx")
        config = Config(dpi=150)
        document = DocumentParser(Unpacker(docx).unpack(), config).parse()

        page_break_runs = [
            run
            for para in document.body
            if isinstance(para, Paragraph)
            for run in para.runs
            if run.brk is not None and run.brk.break_type == "page"
        ]
        assert len(page_break_runs) == 1

        pages = LayoutEngine(document, config).layout()
        assert len(pages) == 3
        assert not LayoutEngine._block_has_ink(pages[1].blocks[0])

        def _png_bytes():
            rendered = RenderCanvas(config).render_pages(
                LayoutEngine(document, config).layout()
            )
            payloads = []
            for image in rendered:
                payload = io.BytesIO()
                image.save(payload, format="PNG")
                payloads.append(payload.getvalue())
            return payloads

        assert _png_bytes() == _png_bytes()

    def test_float_only_paragraph_keeps_anchor_block(self):
        """An inkless paragraph must not discard its anchored drawing."""
        from src.docx2img.model.paragraph import ImageRun

        para = Paragraph(
            runs=[
                Run(
                    image=ImageRun(
                        media_ref="rId1",
                        width_emu=914400,
                        height_emu=457200,
                        wrap_type="inFrontOf",
                    )
                )
            ]
        )
        engine = LayoutEngine(DocumentModel(), Config())
        blocks = engine._layout_paragraph(
            para, 0.0, 400.0, engine.config.px_per_pt
        )

        assert len(blocks) == 1
        assert len(blocks[0].float_boxes) == 1
        assert blocks[0].height >= blocks[0].float_boxes[0].height

    def test_anchored_objects_are_not_duplicated_across_page_segments(self):
        """A manual break splits text blocks but not paragraph-level anchors."""
        from src.docx2img.model.paragraph import BreakRun, ImageRun

        props = RunProps(font_size=12.0)
        para = Paragraph(
            runs=[
                Run(
                    image=ImageRun(
                        media_ref="rId1",
                        width_emu=12700,
                        height_emu=12700,
                        wrap_type="square",
                    )
                ),
                Run(text=TextRun(text="before", props=props)),
                Run(brk=BreakRun(break_type="page")),
                Run(text=TextRun(text="after", props=props)),
            ]
        )
        engine = LayoutEngine(DocumentModel(), Config())
        blocks = engine._layout_paragraph(
            para, 0.0, 400.0, engine.config.px_per_pt
        )

        assert len(blocks) == 2
        assert sum(len(block.float_boxes) for block in blocks) == 1

    def test_layout_with_spacing(self):
        """Test layout respects paragraph spacing"""
        config = Config()
        
        para = Paragraph()
        props = ParaProps()
        props.space_before = 10.0  # 10 pt before
        props.space_after = 20.0   # 20 pt after
        para.props = props
        
        run_props = RunProps()
        text_run = TextRun(text="Test", props=run_props)
        run = Run(text=text_run)
        para.runs.append(run)
        
        section = Section()
        document = DocumentModel()
        document.body.append(para)
        document.sections.append(section)
        
        engine = LayoutEngine(document, config)
        pages = engine.layout()

        assert len(pages) >= 1
        block = pages[0].blocks[0]
        # Block height should include spacing
        assert block.height > 0


class TestContinuousSections:
    """`w:type="continuous"` sections keep flowing on the current page."""

    def _make_para(self, text, section_break=None):
        para = Paragraph()
        para.props = ParaProps()
        run_props = RunProps()
        run_props.font_size = 12.0
        para.runs.append(Run(text=TextRun(text=text, props=run_props)))
        para.section_break = section_break
        return para

    def _make_doc(self, sec1, sec2, texts1=("Alpha", "Beta"),
                  texts2=("Gamma", "Delta")):
        """Two-section document: last para of section 1 carries the break."""
        document = DocumentModel()
        paras1 = [self._make_para(t) for t in texts1]
        paras1[-1].section_break = sec1
        paras2 = [self._make_para(t) for t in texts2]
        document.body.extend(paras1 + paras2)
        document.sections.extend([sec1, sec2])
        return document

    def test_continuous_section_stays_on_same_page(self):
        from src.docx2img.model.enums import SectionType
        sec1 = Section()
        sec2 = Section()
        sec2.section_type = SectionType.CONTINUOUS
        document = self._make_doc(sec1, sec2)
        pages = LayoutEngine(document, Config()).layout()
        assert len(pages) == 1
        # Section-2 content flows below section-1 content on the same page
        assert len(pages[0].blocks) == 4

    def test_next_page_section_forces_new_page(self):
        from src.docx2img.model.enums import SectionType
        sec1 = Section()
        sec2 = Section()
        sec2.section_type = SectionType.NEXT_PAGE
        # Enough section-2 content that the sparse-page merge pass keeps it.
        document = self._make_doc(
            sec1, sec2, texts2=tuple(f"Line {i}" for i in range(12)))
        pages = LayoutEngine(document, Config()).layout()
        assert len(pages) == 2
        # Section-2 content starts at the top of the new page
        assert pages[1].blocks[0].y == pages[1].margin_top

    def test_continuous_with_different_page_size_breaks(self):
        """Continuous break cannot merge onto a different physical page."""
        from src.docx2img.model.enums import SectionType
        sec1 = Section()
        sec2 = Section()
        sec2.section_type = SectionType.CONTINUOUS
        sec2.page_w = sec1.page_w * 1.5  # different geometry
        document = self._make_doc(sec1, sec2)
        pages = LayoutEngine(document, Config()).layout()
        assert len(pages) == 2

    def test_continuous_multicolumn_flows_midpage(self):
        """1-col intro → continuous 2-col section shares the page."""
        from src.docx2img.model.enums import SectionType
        sec1 = Section()
        sec2 = Section()
        sec2.section_type = SectionType.CONTINUOUS
        sec2.col_count = 2
        sec2.col_space = 36.0
        sec2.col_equal_width = True
        document = self._make_doc(
            sec1, sec2, texts2=("C1", "C2", "C3", "C4"))
        pages = LayoutEngine(document, Config()).layout()
        assert len(pages) == 1
        # Column content starts below the intro paragraphs, not at margin_top
        intro_bottom = max(
            b.y + b.height for b in pages[0].blocks[:2])
        col_blocks = pages[0].blocks[2:]
        assert all(b.y >= intro_bottom - 0.5 for b in col_blocks)

    def test_balanced_columns_before_continuous_break(self):
        """2-col section followed by a continuous section balances columns."""
        from src.docx2img.model.enums import SectionType
        sec1 = Section()
        sec1.col_count = 2
        sec1.col_space = 36.0
        sec1.col_equal_width = True
        sec2 = Section()
        sec2.section_type = SectionType.CONTINUOUS
        document = self._make_doc(
            sec1, sec2,
            texts1=("A1", "A2", "A3", "A4"), texts2=("Tail",))
        pages = LayoutEngine(document, Config()).layout()
        assert len(pages) == 1
        col_blocks = pages[0].blocks[:4]
        xs = {round(b.x) for b in col_blocks}
        # Balanced: content occupies both columns instead of only the first
        assert len(xs) == 2, f"expected 2 distinct column x positions, got {xs}"
        # Continuous tail starts below the balanced columns
        tail = pages[0].blocks[4]
        assert tail.y >= max(b.y + b.height for b in col_blocks) - 0.5


class TestColumnGeometries:
    """Tests for column_geometries gap clamping fix."""

    def _make_section(self, col_count=2, col_space=36.0):
        s = Section()
        s.col_count = col_count
        s.col_space = col_space
        s.col_equal_width = True
        return s

    def test_normal_gap(self):
        """Normal column gap produces positive widths."""
        from src.docx2img.layout.column_layout import column_geometries
        sec = self._make_section(col_count=2, col_space=36.0)
        geoms = column_geometries(sec, 900.0, 2.083)
        assert len(geoms) == 2
        assert all(w > 0 for _, w in geoms)

    def test_absurd_gap_falls_back(self):
        """Absurdly large col_space (e.g., EMU-in-twips) falls back to default."""
        from src.docx2img.layout.column_layout import column_geometries
        sec = self._make_section(col_count=2, col_space=18000.0)
        geoms = column_geometries(sec, 900.0, 2.083)
        assert len(geoms) == 2
        # After fallback to ~36pt gap, each column should be > 300px
        for x, w in geoms:
            assert w > 300, f"column width {w} too narrow (gap not corrected?)"

    def test_single_column_returns_full_width(self):
        """Single column always returns full content width."""
        from src.docx2img.layout.column_layout import column_geometries
        sec = self._make_section(col_count=1)
        geoms = column_geometries(sec, 900.0, 2.083)
        assert geoms == [(0.0, 900.0)]

    def test_three_columns_positive(self):
        """Three columns with reasonable gap all have positive width."""
        from src.docx2img.layout.column_layout import column_geometries
        sec = self._make_section(col_count=3, col_space=24.0)
        geoms = column_geometries(sec, 900.0, 2.083)
        assert len(geoms) == 3
        assert all(w > 0 for _, w in geoms)
        # Columns should be left-to-right with increasing x
        xs = [x for x, _ in geoms]
        assert xs == sorted(xs)

    def test_gap_is_clamped_to_tiny_content_width(self):
        """Even the default gap must not make narrow columns negative."""
        from src.docx2img.layout.column_layout import column_geometries

        sec = self._make_section(col_count=2, col_space=36.0)
        geoms = column_geometries(sec, 20.0, 2.0)
        assert all(w >= 1.0 for _, w in geoms)
        assert geoms[-1][0] + geoms[-1][1] <= 20.0 + 0.01

    def test_zero_width_unequal_columns_fall_back_to_equal(self):
        """Malformed explicit columns do not divide by zero."""
        from src.docx2img.layout.column_layout import column_geometries
        from src.docx2img.model.section import ColumnDef

        sec = self._make_section(col_count=2, col_space=12.0)
        sec.col_equal_width = False
        sec.columns = [ColumnDef(width=0.0), ColumnDef(width=0.0)]
        geoms = column_geometries(sec, 300.0, 1.0)
        assert all(w > 0 for _, w in geoms)


class TestSparsePageMerge:
    """Tests for _merge_sparse_pages — absorbs near-empty trailing pages."""

    def _make_pages(self, prev_fill=0.10, cur_fill=0.04, same_section=True,
                    cur_has_floats=False, prev_has_floats=False,
                    cur_has_header=False, cur_has_footer=False):
        """Build a minimal two-page list with the requested geometry.

        Fills are ratios of content_h / usable_h for each page.
        """
        from src.docx2img.layout.engine import PageBox, BlockBox

        sec = Section()
        sec.page_w = 595.0
        sec.page_h = 842.0

        page_geom = dict(width=595.0, height=842.0,
                          margin_top=72.0, margin_bottom=72.0,
                          margin_left=72.0, margin_right=72.0,
                          section=sec)
        usable = 842.0 - 72.0 - 72.0

        prev = PageBox(**page_geom)
        b1 = BlockBox()
        b1.height = prev_fill * usable
        b1.y = 72.0
        prev.blocks.append(b1)
        if prev_has_floats:
            prev.float_boxes.append("ignore")  # type: ignore[arg-type]

        cur = PageBox(**page_geom)
        if same_section:
            cur.section = sec
        else:
            cur.section = Section()
        b2 = BlockBox()
        b2.height = max(cur_fill * usable, 1.0)
        b2.y = 72.0
        cur.blocks.append(b2)
        if cur_has_floats:
            cur.float_boxes.append("ignore")  # type: ignore[arg-type]
        if cur_has_header:
            cur.header_blocks.append(BlockBox())
        if cur_has_footer:
            cur.footer_blocks.append(BlockBox())

        return [prev, cur]

    def test_tiny_trailing_page_merged(self):
        """A tiny trailing page (<5%) folds back into the previous page."""
        pages = self._make_pages(prev_fill=0.10, cur_fill=0.04)
        merged = LayoutEngine._merge_sparse_pages(pages)
        assert len(merged) == 1
        assert len(merged[0].blocks) == 2

    def test_normal_trailing_page_not_merged(self):
        """A page at >5% fill stays separate — don't over-merge."""
        pages = self._make_pages(prev_fill=0.10, cur_fill=0.40)
        merged = LayoutEngine._merge_sparse_pages(pages)
        assert len(merged) == 2

    def test_full_prev_page_not_merged(self):
        """An already-overflowing previous page won't absorb the trailing page."""
        # 99% + 2% = 101% > 100% → no room, so keep separate
        pages = self._make_pages(prev_fill=0.99, cur_fill=0.02)
        merged = LayoutEngine._merge_sparse_pages(pages)
        assert len(merged) == 2

    def test_trailing_page_with_header_kept(self):
        """Trailing page that owns a header stays separate."""
        pages = self._make_pages(prev_fill=0.10, cur_fill=0.04,
                                  cur_has_header=True)
        merged = LayoutEngine._merge_sparse_pages(pages)
        assert len(merged) == 2

    def test_trailing_page_with_footer_kept(self):
        """Trailing page that owns a footer stays separate."""
        pages = self._make_pages(prev_fill=0.10, cur_fill=0.04,
                                  cur_has_footer=True)
        merged = LayoutEngine._merge_sparse_pages(pages)
        assert len(merged) == 2

    def test_trailing_page_with_floats_kept(self):
        """Float-bearing pages cannot be merged safely."""
        pages = self._make_pages(prev_fill=0.10, cur_fill=0.04,
                                  cur_has_floats=True)
        merged = LayoutEngine._merge_sparse_pages(pages)
        assert len(merged) == 2

    def test_cross_section_merged(self):
        """Different sections can also be merged when geometry / decoration allow."""
        pages = self._make_pages(prev_fill=0.10, cur_fill=0.04,
                                  same_section=False)
        merged = LayoutEngine._merge_sparse_pages(pages)
        assert len(merged) == 1

    def test_merge_translates_lines_and_glyphs_with_block(self):
        """Absorbed content keeps its internal absolute coordinates aligned."""
        from src.docx2img.layout.engine import GlyphBox, LineBox

        pages = self._make_pages(prev_fill=0.10, cur_fill=0.04)
        moved = pages[1].blocks[0]
        old_y = moved.y
        line = LineBox(y=old_y + 2.0, height=10.0)
        glyph = GlyphBox(text="tail", y=old_y + 3.0)
        line.glyphs.append(glyph)
        moved.lines.append(line)

        expected_y = pages[0].blocks[0].y + pages[0].blocks[0].height
        merged = LayoutEngine._merge_sparse_pages(pages)

        assert len(merged) == 1
        assert moved.y == pytest.approx(expected_y)
        delta = expected_y - old_y
        assert line.y == pytest.approx(old_y + 2.0 + delta)
        assert glyph.y == pytest.approx(old_y + 3.0 + delta)

    def test_different_horizontal_margins_are_not_merged(self):
        """Pages with different text geometry cannot safely share blocks."""
        pages = self._make_pages(prev_fill=0.10, cur_fill=0.04)
        pages[1].margin_left += 12.0
        merged = LayoutEngine._merge_sparse_pages(pages)
        assert len(merged) == 2


class TestPageStamping:
    def test_page_number_restart_and_section_local_index(self):
        """Page labels restart per pgNumType while first-page state stays local."""
        from src.docx2img.layout.engine import PageBox

        first = Section()
        second = Section()
        second.page_num_start = 7
        pages = [
            PageBox(section=first),
            PageBox(section=first),
            PageBox(section=second),
            PageBox(section=second),
        ]
        engine = LayoutEngine(DocumentModel(), Config())
        engine._stamp_and_attach_pages(pages)

        assert [p.page_number for p in pages] == [1, 2, 7, 8]
        assert [p.section_page_index for p in pages] == [0, 1, 0, 1]
        assert all(p.total_pages == 4 for p in pages)


class TestLineHeightFormula:
    """Verify _line_height auto-spacing matches Word behaviour.

    OOXML ``auto`` multiplies the single-line calculation by ``line/240``.
    Word scales the content natural height:

        max(natural_height * mult, mark_font_size * px_per_pt * mult)

    LibreOffice used ``max(natural, font_size * mult)`` (no natural inflation);
    that under-spaces Word-authoritative goldens.
    """

    def setup_method(self):
        from src.docx2img.layout.line_breaker import LineBreaker
        from src.docx2img.config import Config
        self.lb = LineBreaker(Config())

    def _props(self, **kw):
        p = type('P', (), kw)()
        for k, v in kw.items():
            setattr(p, k, v)
        return p

    def test_auto_single_spacing(self):
        """mult=1.0 → max(natural, mark_floor)"""
        px = 150 / 72
        props = self._props(line_spacing=1.0, line_spacing_rule="auto",
                            mark_font_size=11)
        result = self.lb._line_height(props, natural_height=12.0, px_per_pt=px)
        expected = max(12.0 * 1.0, 11.0 * px * 1.0)
        assert abs(result - expected) < 0.5

    def test_auto_115_scales_ascent_descent_not_linegap(self):
        """mult scales ascent+descent natural; callers must omit hhea lineGap."""
        px = 150 / 72
        props = self._props(line_spacing=1.15, line_spacing_rule="auto",
                            mark_font_size=10)
        # Simulated ascent+descent only (29px), not ascent+descent+gap.
        natural = 29.0
        result = self.lb._line_height(props, natural_height=natural, px_per_pt=px)
        expected = max(natural * 1.15, 10.0 * px * 1.15)
        assert abs(result - expected) < 0.5
        # Including a ~1px lineGap in natural would overshoot Word.
        with_gap = self.lb._line_height(props, natural_height=30.0, px_per_pt=px)
        assert with_gap > result


    def test_auto_large_natural_is_scaled(self):
        """When natural dominates the mark floor, mult still scales it."""
        px = 150 / 72
        props = self._props(line_spacing=1.0, line_spacing_rule="auto",
                            mark_font_size=10)
        result = self.lb._line_height(props, natural_height=25.0, px_per_pt=px)
        assert result == 25.0  # mult=1.0 → natural unchanged

        props15 = self._props(line_spacing=1.5, line_spacing_rule="auto",
                              mark_font_size=10)
        result15 = self.lb._line_height(props15, natural_height=25.0, px_per_pt=px)
        assert abs(result15 - 25.0 * 1.5) < 0.5

    def test_exact_spacing_unchanged(self):
        """exact rule uses absolute value, unaffected by formula change."""
        px = 150 / 72
        props = self._props(line_spacing_exact=18.0, line_spacing_rule="exact")
        result = self.lb._line_height(props, natural_height=12.0, px_per_pt=px)
        assert abs(result - 18.0 * px) < 0.5

    def test_atleast_uses_max(self):
        """atLeast takes max(natural, absolute)."""
        px = 150 / 72
        props = self._props(line_spacing_exact=20.0, line_spacing_rule="atLeast")
        result = self.lb._line_height(props, natural_height=12.0, px_per_pt=px)
        assert result == max(12.0, 20.0 * px)

    def test_image_only_returns_natural(self):
        """Image-only lines use natural height directly (auto rule)."""
        props = self._props(line_spacing=1.15, line_spacing_rule="auto",
                            mark_font_size=11)
        result = self.lb._line_height(props, natural_height=100.0,
                                       px_per_pt=2, image_only=True)
        assert result == 100.0

    def test_document_grid_snaps_text_to_whole_pitch(self):
        """A resolved 12pt line occupies one 18pt document-grid interval."""
        props = self._props(
            line_spacing=1.0,
            line_spacing_rule="auto",
            mark_font_size=12,
        )
        result = self.lb._line_height(
            props,
            natural_height=12.0,
            px_per_pt=2.0,
            grid_line_pitch_px=36.0,
        )
        assert result == 36.0

    def test_exact_spacing_overrides_document_grid(self):
        """OOXML exact line spacing opts the paragraph out of the line grid."""
        props = self._props(
            line_spacing_exact=12.0,
            line_spacing_rule="exact",
        )
        result = self.lb._line_height(
            props,
            natural_height=16.0,
            px_per_pt=2.0,
            grid_line_pitch_px=36.0,
        )
        assert result == 24.0
