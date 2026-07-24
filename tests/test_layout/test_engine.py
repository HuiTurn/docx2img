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
