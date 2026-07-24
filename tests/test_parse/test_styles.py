"""Unit tests for P1 style / theme resolution."""

from docx2img.model.style import Style, StyleTable
from docx2img.model.paragraph import RunProps, ParaProps
from docx2img.model.enums import Alignment
from docx2img.style.resolver import StyleResolver
from docx2img.style.theme_resolver import ThemeResolver
from docx2img.parse.styles import StylesParser
from docx2img.parse.theme import ThemeParser


STYLES_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:eastAsia="SimSun" w:hAnsi="Calibri"/>
        <w:sz w:val="22"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="160" w:line="276" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>

  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>

  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="480" w:after="0"/>
      <w:outlineLvl w:val="0"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="2F5496"/>
      <w:sz w:val="32"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="BaseA">
    <w:name w:val="Base A"/>
    <w:rPr>
      <w:sz w:val="20"/>
      <w:color w:val="FF0000"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="MidB">
    <w:name w:val="Mid B"/>
    <w:basedOn w:val="BaseA"/>
    <w:rPr>
      <w:i/>
      <w:sz w:val="28"/>
    </w:rPr>
  </w:style>

  <w:style w:type="paragraph" w:styleId="LeafC">
    <w:name w:val="Leaf C"/>
    <w:basedOn w:val="MidB"/>
    <w:rPr>
      <w:b/>
    </w:rPr>
  </w:style>

  <w:style w:type="character" w:styleId="Emphasis">
    <w:name w:val="Emphasis"/>
    <w:rPr>
      <w:i/>
    </w:rPr>
  </w:style>
</w:styles>
"""

THEME_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
  <a:themeElements>
    <a:clrScheme name="Office">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="44546A"/></a:dk2>
      <a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>
      <a:accent1><a:srgbClr val="5B9BD5"/></a:accent1>
      <a:accent2><a:srgbClr val="ED7D31"/></a:accent2>
      <a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>
      <a:accent4><a:srgbClr val="FFC000"/></a:accent4>
      <a:accent5><a:srgbClr val="4472C4"/></a:accent5>
      <a:accent6><a:srgbClr val="70AD47"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink>
      <a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Office">
      <a:majorFont>
        <a:latin typeface="Calibri Light"/>
        <a:ea typeface=""/>
        <a:cs typeface=""/>
        <a:font script="Hans" typeface="DengXian"/>
      </a:majorFont>
      <a:minorFont>
        <a:latin typeface="Calibri"/>
        <a:ea typeface=""/>
        <a:cs typeface=""/>
        <a:font script="Hans" typeface="DengXian"/>
      </a:minorFont>
    </a:fontScheme>
  </a:themeElements>
</a:theme>
""".encode("utf-8")


class TestStylesParser:
    def test_parse_doc_defaults_and_heading(self):
        table, rpr, ppr = StylesParser().parse(STYLES_XML)
        assert rpr.font_size == 11.0
        assert rpr.font_ascii == "Calibri"
        assert abs(ppr.space_after - 8.0) < 0.1  # 160 twips
        assert "Heading1" in table.styles
        h1 = table.get("Heading1")
        assert h1 is not None
        assert h1.based_on == "Normal"
        assert "bold" in h1.run_set
        assert h1.run_props.font_size == 16.0


class TestThemeParser:
    def test_parse_colors_and_fonts(self):
        colors, fonts = ThemeParser().parse(THEME_XML)
        assert colors["accent1"] == (0x5B, 0x9B, 0xD5)
        assert colors["dk1"] == (0, 0, 0)
        assert fonts["major_latin"] == "Calibri Light"
        assert fonts["minor_latin"] == "Calibri"
        assert fonts["minor_ea"] == "DengXian"


class TestThemeResolver:
    def test_tint_and_shade(self):
        tr = ThemeResolver({"accent1": (100, 100, 100)})
        tinted = tr.resolve_color(theme_color="accent1", tint="80")
        # factor 128/255 ≈ 0.5 → midway to white
        assert tinted[0] > 100
        shaded = tr.resolve_color(theme_color="accent1", shade="80")
        assert shaded[0] < 100

    def test_theme_fonts(self):
        tr = ThemeResolver(
            theme_fonts={"major_latin": "Cambria", "minor_latin": "Calibri", "minor_ea": "SimSun"}
        )
        props = RunProps(font_ascii="+mn-lt", font_east_asia="+mn-ea")
        props = tr.apply_fonts(props)
        assert props.font_ascii == "Calibri"
        assert props.font_east_asia == "SimSun"


class TestStyleResolver:
    def test_three_level_inheritance(self):
        table, default_rpr, default_ppr = StylesParser().parse(STYLES_XML)
        resolver = StyleResolver(table, default_rpr=default_rpr, default_ppr=default_ppr)

        props = resolver.resolve_run("", "LeafC", RunProps(), set())
        # BaseA: color red, size 10; MidB: italic + size 14; LeafC: bold
        assert props.color == (255, 0, 0)
        assert props.font_size == 14.0
        assert props.italic is True
        assert props.bold is True

    def test_direct_overrides_style(self):
        table, default_rpr, default_ppr = StylesParser().parse(STYLES_XML)
        resolver = StyleResolver(table, default_rpr=default_rpr, default_ppr=default_ppr)

        direct = RunProps(font_size=48.0, bold=False)
        props = resolver.resolve_run("", "Heading1", direct, {"font_size", "bold"})
        assert props.font_size == 48.0
        assert props.bold is False
        assert props.color == (0x2F, 0x54, 0x96)  # from Heading1

    def test_heading_para_spacing(self):
        table, default_rpr, default_ppr = StylesParser().parse(STYLES_XML)
        resolver = StyleResolver(table, default_rpr=default_rpr, default_ppr=default_ppr)
        props = resolver.resolve_para("Heading1", ParaProps(), set())
        assert abs(props.space_before - 24.0) < 0.1  # 480 twips
        assert props.outline_level == 0

    def test_character_style_emphasis(self):
        table, default_rpr, default_ppr = StylesParser().parse(STYLES_XML)
        resolver = StyleResolver(table, default_rpr=default_rpr, default_ppr=default_ppr)
        props = resolver.resolve_run("Emphasis", "Normal", RunProps(), set())
        assert props.italic is True
        assert props.font_size == 11.0  # from docDefaults
