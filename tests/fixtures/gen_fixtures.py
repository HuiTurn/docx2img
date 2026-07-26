"""Generate minimal OOXML .docx fixtures for testing (stdlib only)."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import List, Optional
from xml.sax.saxutils import escape


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Default Extension="jpg" ContentType="image/jpeg"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/theme/theme1.xml"
    ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/docProps/core.xml"
    ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml"
    ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
    Target="docProps/core.xml"/>
  <Relationship Id="rId3"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
    Target="docProps/app.xml"/>
</Relationships>
"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    Target="styles.xml"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
    Target="theme/theme1.xml"/>
  <Relationship Id="rId3"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"
    Target="settings.xml"/>
</Relationships>
"""

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

MINIMAL_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Calibri" w:eastAsia="SimSun" w:hAnsi="Calibri"/>
      <w:sz w:val="22"/>
    </w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr>
      <w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
    </w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="360" w:after="200"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="2F5496"/>
      <w:sz w:val="32"/>
    </w:rPr>
  </w:style>
  <w:style w:type="character" w:styleId="Emphasis">
    <w:name w:val="Emphasis"/>
    <w:rPr><w:i/></w:rPr>
  </w:style>
</w:styles>
"""

MINIMAL_THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office">
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
        <a:latin typeface="Calibri Light"/><a:ea typeface="SimSun"/><a:cs typeface="Times New Roman"/>
      </a:majorFont>
      <a:minorFont>
        <a:latin typeface="Calibri"/><a:ea typeface="SimSun"/><a:cs typeface="Times New Roman"/>
      </a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"><a:tint val="50000"/></a:schemeClr></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"><a:shade val="50000"/></a:schemeClr></a:solidFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="9525" cap="flat" cmpd="sng" algn="ctr">
          <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
          <a:prstDash val="solid"/>
        </a:ln>
        <a:ln w="12700" cap="flat" cmpd="sng" algn="ctr">
          <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
          <a:prstDash val="solid"/>
        </a:ln>
        <a:ln w="19050" cap="flat" cmpd="sng" algn="ctr">
          <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
          <a:prstDash val="solid"/>
        </a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
      </a:effectStyleLst>
      <a:bgFillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"><a:tint val="50000"/></a:schemeClr></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"><a:shade val="50000"/></a:schemeClr></a:solidFill>
      </a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>
"""

MINIMAL_SETTINGS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:zoom w:percent="100"/>
  <w:defaultTabStop w:val="720"/>
  <w:compat/>
</w:settings>
"""

MINIMAL_CORE_PROPS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties
  xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:dcmitype="http://purl.org/dc/dcmitype/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>docx2img fixture</dc:title>
  <dc:creator>docx2img</dc:creator>
  <cp:lastModifiedBy>docx2img</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2024-01-01T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2024-01-01T00:00:00Z</dcterms:modified>
</cp:coreProperties>
"""

MINIMAL_APP_PROPS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
  xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>docx2img</Application>
  <Pages>1</Pages>
  <Words>0</Words>
</Properties>
"""



def _run(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    strike: bool = False,
    size_half_pt: Optional[int] = 24,
    color: Optional[str] = None,
    highlight: Optional[str] = None,
    vert_align: Optional[str] = None,
    font_ascii: Optional[str] = "Times New Roman",
    font_east_asia: Optional[str] = "SimSun",
    bare: bool = False,
) -> str:
    if bare:
        space_attr = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
        return f"<w:r><w:t{space_attr}>{escape(text)}</w:t></w:r>"

    rpr_parts = []
    if font_ascii or font_east_asia:
        ascii_f = font_ascii or "Times New Roman"
        ea_f = font_east_asia or "SimSun"
        rpr_parts.append(
            f'<w:rFonts w:ascii="{escape(ascii_f)}" w:hAnsi="{escape(ascii_f)}" '
            f'w:eastAsia="{escape(ea_f)}"/>'
        )
    if size_half_pt is not None:
        rpr_parts.append(f'<w:sz w:val="{size_half_pt}"/>')
        rpr_parts.append(f'<w:szCs w:val="{size_half_pt}"/>')
    if bold:
        rpr_parts.append("<w:b/>")
    if italic:
        rpr_parts.append("<w:i/>")
    if underline:
        rpr_parts.append('<w:u w:val="single"/>')
    if strike:
        rpr_parts.append("<w:strike/>")
    if color:
        rpr_parts.append(f'<w:color w:val="{color}"/>')
    if highlight:
        rpr_parts.append(f'<w:highlight w:val="{highlight}"/>')
    if vert_align:
        rpr_parts.append(f'<w:vertAlign w:val="{vert_align}"/>')

    space_attr = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") or "  " in text else ""
    rpr_xml = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>" if rpr_parts else ""
    return f"<w:r>{rpr_xml}<w:t{space_attr}>{escape(text)}</w:t></w:r>"


def _br(break_type: str = "page") -> str:
    return f'<w:r><w:br w:type="{break_type}"/></w:r>'


def _para(
    runs_xml: str,
    *,
    align: Optional[str] = None,
    space_before: Optional[int] = None,
    space_after: Optional[int] = None,
    line: Optional[int] = None,
    line_rule: str = "auto",
    first_line: Optional[int] = None,
    page_break_before: bool = False,
    tabs_xml: Optional[str] = None,
) -> str:
    ppr = []
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    spacing_attrs = []
    if space_before is not None:
        spacing_attrs.append(f'w:before="{space_before}"')
    if space_after is not None:
        spacing_attrs.append(f'w:after="{space_after}"')
    if line is not None:
        spacing_attrs.append(f'w:line="{line}"')
        spacing_attrs.append(f'w:lineRule="{line_rule}"')
    if spacing_attrs:
        ppr.append(f'<w:spacing {" ".join(spacing_attrs)}/>')
    if first_line is not None:
        ppr.append(f'<w:ind w:firstLine="{first_line}"/>')
    if page_break_before:
        ppr.append("<w:pageBreakBefore/>")
    if tabs_xml:
        ppr.append(tabs_xml)
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>" if ppr else ""
    return f"<w:p>{ppr_xml}{runs_xml}</w:p>"


def _sect_pr(
    *,
    w: int = 11906,
    h: int = 16838,
    orient: str = "portrait",
    top: int = 1440,
    bottom: int = 1440,
    left: int = 1800,
    right: int = 1800,
) -> str:
    orient_attr = f' w:orient="{orient}"' if orient == "landscape" else ""
    return (
        f"<w:sectPr>"
        f'<w:pgSz w:w="{w}" w:h="{h}"{orient_attr}/>'
        f'<w:pgMar w:top="{top}" w:right="{right}" w:bottom="{bottom}" w:left="{left}" '
        f'w:header="720" w:footer="720" w:gutter="0"/>'
        f"</w:sectPr>"
    )


def _document(body_inner: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{NS_W}">'
        f"<w:body>{body_inner}</w:body>"
        "</w:document>"
    )


def write_docx(
    path: Path,
    document_xml: str,
    styles_xml: str = MINIMAL_STYLES,
    theme_xml: str = MINIMAL_THEME,
    media: Optional[dict] = None,
    extra_rels: Optional[list] = None,
    headers: Optional[dict] = None,
    footers: Optional[dict] = None,
    footnotes_xml: Optional[str] = None,
    endnotes_xml: Optional[str] = None,
    numbering_xml: Optional[str] = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rels = DOC_RELS
    extras = list(extra_rels or [])
    if numbering_xml:
        extras.append(
            '<Relationship Id="rIdNum" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" '
            'Target="numbering.xml"/>'
        )
    if extras:
        rels = DOC_RELS.replace("</Relationships>", "".join(extras) + "</Relationships>")

    ct = CONTENT_TYPES
    if numbering_xml:
        ct = ct.replace(
            "</Types>",
            '<Override PartName="/word/numbering.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
            "</Types>",
        )
    if footnotes_xml:
        extras.append(
            '<Relationship Id="rIdFootnotes" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" '
            'Target="footnotes.xml"/>'
        )
        rels = DOC_RELS.replace(
            "</Relationships>", "".join(extras) + "</Relationships>"
        )
        ct = ct.replace(
            "</Types>",
            '<Override PartName="/word/footnotes.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.footnotes+xml"/>'
            "</Types>",
        )
    if endnotes_xml:
        extras.append(
            '<Relationship Id="rIdEndnotes" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes" '
            'Target="endnotes.xml"/>'
        )
        rels = DOC_RELS.replace(
            "</Relationships>", "".join(extras) + "</Relationships>"
        )
        ct = ct.replace(
            "</Types>",
            '<Override PartName="/word/endnotes.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.endnotes+xml"/>'
            "</Types>",
        )
    if headers:
        for name in headers:
            ct = ct.replace(
                "</Types>",
                f'<Override PartName="/word/{name}" '
                f'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
                f"</Types>",
            )
    if footers:
        for name in footers:
            ct = ct.replace(
                "</Types>",
                f'<Override PartName="/word/{name}" '
                f'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                f"</Types>",
            )

    members = {
        "[Content_Types].xml": ct,
        "_rels/.rels": ROOT_RELS,
        "docProps/core.xml": MINIMAL_CORE_PROPS,
        "docProps/app.xml": MINIMAL_APP_PROPS,
        "word/_rels/document.xml.rels": rels,
        "word/document.xml": document_xml,
        "word/styles.xml": styles_xml,
        "word/settings.xml": MINIMAL_SETTINGS,
        "word/theme/theme1.xml": theme_xml,
    }
    if numbering_xml:
        members["word/numbering.xml"] = numbering_xml
    if footnotes_xml:
        members["word/footnotes.xml"] = footnotes_xml
    if endnotes_xml:
        members["word/endnotes.xml"] = endnotes_xml
    for name, data in (media or {}).items():
        members[f"word/media/{name}"] = data
    for name, data in (headers or {}).items():
        members[f"word/{name}"] = data
    for name, data in (footers or {}).items():
        members[f"word/{name}"] = data

    # Tests call fixture factories repeatedly.  Avoid rewriting a semantically
    # identical ZIP, since ZipFile timestamps would otherwise dirty every
    # tracked binary fixture on each test run.
    if path.exists():
        try:
            with zipfile.ZipFile(path) as current:
                if set(current.namelist()) == set(members) and all(
                    current.read(name) == (
                        data.encode("utf-8") if isinstance(data, str) else data
                    )
                    for name, data in members.items()
                ):
                    return path
        except (OSError, zipfile.BadZipFile):
            pass

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def make_basic_text(path: Path) -> Path:
    """English text with styles, alignment, indent, page break."""
    paras: List[str] = [
        _para(
            _run("Hello World - Basic Text", bold=True, size_half_pt=36, color="1F4E79"),
            align="center",
            space_after=200,
        ),
        _para(
            _run(
                "This is an English paragraph that should wrap correctly when the line "
                "becomes too long for the page width. Word wrapping must not split "
                "inside words like Supercalifragilisticexpialidocious."
            ),
            align="left",
            space_after=120,
            line=360,  # 1.5x
        ),
        _para(
            _run(
                "This is a test paragraph that should wrap correctly between words "
                "when the available width is exceeded. Mixed content with different "
                "font sizes and styles should also render without issues."
            ),
            first_line=480,  # 2 chars ≈ 24pt = 480 twips at 12pt
            space_after=120,
        ),
        _para(
            _run("Bold ", bold=True)
            + _run("Italic ", italic=True)
            + _run("Underline ", underline=True)
            + _run("Strike ", strike=True)
            + _run("Red", color="FF0000")
            + _run(" ")
            + _run("Highlight", highlight="yellow")
            + _run(" ")
            + _run("H", size_half_pt=24)
            + _run("2", size_half_pt=16, vert_align="subscript")
            + _run("O", size_half_pt=24)
            + _run(" and x")
            + _run("2", size_half_pt=16, vert_align="superscript"),
            space_after=200,
        ),
        _para(_run("Centered line"), align="center"),
        _para(_run("Right-aligned line"), align="right", space_after=200),
        _para(
            _run("Page break follows (Ctrl+Enter simulation)."),
            space_after=120,
        ),
        _para(_run("") + _br("page")),
        _para(
            _run("This is page 2 after a hard page break.", bold=True, color="006600"),
            space_before=200,
        ),
        _sect_pr(),
    ]
    return write_docx(path, _document("".join(paras)))


def make_page_break(path: Path) -> Path:
    """Break-only paragraph that overflows a full page → blank middle page.

    Short page (300pt tall) filled by eight default-spaced paragraphs, then a
    paragraph whose only content is a manual page break, then a tail paragraph.
    Word 16.0 (ExportAsFixedFormat) renders this as three pages where the
    middle page is blank: the break paragraph's mark line overflows page one,
    lands alone on page two, and the break itself pushes the tail to page
    three. Used as the ``page_break`` office golden case to quantify manual
    page-break pagination against Word.
    """
    sect = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="6000"/>'  # 595.3pt × 300pt
        '<w:pgMar w:top="920" w:right="1800" w:bottom="920" w:left="1800" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    paras = "".join(
        _para(_run(f"Filler {i}", size_half_pt=28), space_after=120)
        for i in range(8)
    )
    paras += _para(_run("", size_half_pt=28) + _br("page"))
    paras += _para(_run("After the page break.", size_half_pt=28))
    return write_docx(path, _document(paras + sect))


def make_long_wrap(path: Path) -> Path:
    """Long paragraph to exercise word-level wrapping."""
    text = "The quick brown fox jumps over the lazy dog. " * 40 + "Pack my box with five dozen liquor jugs. " * 10
    paras = [
        _para(_run(text, size_half_pt=22), line=276),  # ~1.15
        _sect_pr(),
    ]
    return write_docx(path, _document("".join(paras)))


def make_landscape(path: Path) -> Path:
    """Landscape A4 page."""
    # Landscape A4: w=16838, h=11906
    paras = [
        _para(_run("Landscape page test", bold=True, size_half_pt=32), align="center"),
        _sect_pr(w=16838, h=11906, orient="landscape"),
    ]
    return write_docx(path, _document("".join(paras)))


def make_styled(path: Path) -> Path:
    """Document using Heading1 / Emphasis styles."""
    h1 = (
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
        + _run("Styled Heading", bare=True)
        + "</w:p>"
    )
    body = (
        '<w:p>'
        + _run("Normal text with ", bare=True)
        + '<w:r><w:rPr><w:rStyle w:val="Emphasis"/></w:rPr>'
        '<w:t>emphasized</w:t></w:r>'
        + _run(" words.", bare=True)
        + "</w:p>"
    )
    return write_docx(path, _document(h1 + body + _sect_pr()))


def _ins(runs_xml: str) -> str:
    return f'<w:ins w:id="1" w:author="test">{runs_xml}</w:ins>'


def _del(runs_xml: str) -> str:
    return f'<w:del w:id="2" w:author="test">{runs_xml}</w:del>'


def make_tracked_changes(path: Path) -> Path:
    """Paragraph with w:ins and w:del; ins text is kept, del text is dropped."""
    para = (
        '<w:p>'
        + _run("Before ", bare=True)
        + _ins(_run("inserted", bare=True))
        + _run(" and ", bare=True)
        + _del(_run("deleted", bare=True))
        + _run("after.", bare=True)
        + '</w:p>'
    )
    return write_docx(path, _document(para + _sect_pr()))


def _tbl_borders() -> str:
    def b(side):
        return f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    return (
        "<w:tblBorders>"
        + "".join(b(s) for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
        + "</w:tblBorders>"
    )


def _tc(text: str, *, span: int = 1, vmerge: Optional[str] = None,
        width: int = 2000, fill: Optional[str] = None, bold: bool = False) -> str:
    pr = [f'<w:tcW w:w="{width * span}" w:type="dxa"/>']
    if span > 1:
        pr.append(f'<w:gridSpan w:val="{span}"/>')
    if vmerge:
        if vmerge == "restart":
            pr.append('<w:vMerge w:val="restart"/>')
        else:
            pr.append("<w:vMerge/>")
    if fill:
        pr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>')
    return (
        f"<w:tc><w:tcPr>{''.join(pr)}</w:tcPr>"
        + _para(_run(text, bold=bold, bare=(not bold and not text)))
        + "</w:tc>"
    )


def _tbl(rows_xml: str, col_widths: List[int]) -> str:
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in col_widths)
    return (
        "<w:tbl>"
        f"<w:tblPr><w:tblW w:w=\"{sum(col_widths)}\" w:type=\"dxa\"/>{_tbl_borders()}</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        f"{rows_xml}"
        "</w:tbl>"
    )


def make_basic_table(path: Path) -> Path:
    """3x3 basic table with header shading."""
    cols = [2000, 2000, 2000]
    r0 = "<w:tr>" + _tc("A", fill="2F5496", bold=True) + _tc("B", fill="2F5496", bold=True) + _tc("C", fill="2F5496", bold=True) + "</w:tr>"
    # Fix header cells - bold True with text needs size
    r0 = (
        "<w:tr>"
        + _tc("Name", fill="D6DCE4", bold=True)
        + _tc("Qty", fill="D6DCE4", bold=True)
        + _tc("Price", fill="D6DCE4", bold=True)
        + "</w:tr>"
    )
    r1 = "<w:tr>" + _tc("Apple") + _tc("10") + _tc("3.5") + "</w:tr>"
    r2 = "<w:tr>" + _tc("Banana") + _tc("5") + _tc("2.0") + "</w:tr>"
    body = _para(_run("Basic Table", bold=True, size_half_pt=28)) + _tbl(r0 + r1 + r2, cols) + _sect_pr()
    return write_docx(path, _document(body))


def make_merged_table(path: Path) -> Path:
    """Table with gridSpan and vMerge."""
    cols = [1800, 1800, 1800, 1800]
    # Row0: span 2 + span 2
    r0 = (
        "<w:tr>"
        + _tc("Header Left", span=2, fill="5B9BD5", bold=True, width=1800)
        + _tc("Header Right", span=2, fill="5B9BD5", bold=True, width=1800)
        + "</w:tr>"
    )
    # Row1: vMerge restart + 3 cells
    r1 = (
        "<w:tr>"
        + _tc("Merged", vmerge="restart", fill="E2EFDA", width=1800)
        + _tc("R1C2")
        + _tc("R1C3")
        + _tc("R1C4")
        + "</w:tr>"
    )
    # Row2: vMerge continue
    r2 = (
        "<w:tr>"
        + _tc("", vmerge="continue", width=1800)
        + _tc("R2C2")
        + _tc("R2C3")
        + _tc("R2C4")
        + "</w:tr>"
    )
    body = (
        _para(_run("Merged Table", bold=True, size_half_pt=28))
        + _tbl(r0 + r1 + r2, cols)
        + _sect_pr()
    )
    return write_docx(path, _document(body))


def make_nested_table(path: Path) -> Path:
    """Outer table with a nested table in one cell."""
    cols = [3000, 3000]
    inner = _tbl(
        "<w:tr>" + _tc("in1") + _tc("in2") + "</w:tr>",
        [1400, 1400],
    )
    outer_cell = (
        f'<w:tc><w:tcPr><w:tcW w:w="3000" w:type="dxa"/></w:tcPr>'
        f'{_para(_run("outer"))}{inner}{_para(_run(""))}</w:tc>'
    )
    r0 = "<w:tr>" + outer_cell + _tc("right") + "</w:tr>"
    body = _para(_run("Nested Table", bold=True)) + _tbl(r0, cols) + _sect_pr()
    return write_docx(path, _document(body))


def _make_png_bytes(color=(30, 144, 255), size=(80, 60)) -> bytes:
    from io import BytesIO
    from PIL import Image as PILImage
    img = PILImage.new("RGB", size, color)
    # Draw a simple pattern
    for x in range(0, size[0], 10):
        for y in range(size[1]):
            img.putpixel((x, y), (255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _inline_drawing(rid: str = "rId10", cx: int = 914400, cy: int = 685800) -> str:
    """Inline drawing XML referencing media via rId. Default ~1\" x 0.75\"."""
    return f"""<w:r><w:drawing>
      <wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                 xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
                 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
        <wp:extent cx="{cx}" cy="{cy}"/>
        <a:graphic>
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic>
              <pic:blipFill>
                <a:blip r:embed="{rid}"/>
              </pic:blipFill>
              <pic:spPr>
                <a:xfrm><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
              </pic:spPr>
            </pic:pic>
          </a:graphicData>
        </a:graphic>
      </wp:inline>
    </w:drawing></w:r>"""


def make_inline_image(path: Path) -> Path:
    """Paragraph with text + inline PNG."""
    png = _make_png_bytes()
    drawing = _inline_drawing("rId10", cx=1143000, cy=857250)  # 1.25" x 0.9375"
    body = (
        _para(_run("Before image ", bare=True) + drawing + _run(" after image.", bare=True))
        + _para(_run("Next line under the image paragraph."))
        + _sect_pr()
    )
    rel = (
        '<Relationship Id="rId10" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        'Target="media/image1.png"/>'
    )
    return write_docx(
        path,
        _document(body),
        media={"image1.png": png},
        extra_rels=[rel],
    )


def make_two_sections(path: Path) -> Path:
    """Two sections: portrait then landscape."""
    sect1 = (
        '<w:p>'
        + _run("Section 1 portrait", bold=True)
        + '<w:pPr>'
        + _sect_pr()  # wrong - sectPr shouldn't be wrapped like this
    )
    # Proper: paragraph with text + pPr containing sectPr
    p1 = (
        "<w:p><w:pPr>"
        + _sect_pr().replace("<w:sectPr>", "<w:sectPr>").replace("</w:sectPr>", "</w:sectPr>")
        + "</w:pPr>"
        + _run("End of section 1 (portrait A4).", bold=True)
        + "</w:p>"
    )
    # Fix: sectPr inside pPr
    p1 = (
        '<w:p><w:pPr>'
        f'<w:sectPr>'
        f'<w:pgSz w:w="11906" w:h="16838"/>'
        f'<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        f'w:header="720" w:footer="720" w:gutter="0"/>'
        f'<w:type w:val="nextPage"/>'
        f'</w:sectPr>'
        f'</w:pPr>'
        + _run("Section 1 content — portrait.", bold=True)
        + "</w:p>"
    )
    body = (
        _para(_run("Intro in section 1."))
        + p1
        + _para(_run("Section 2 content — landscape.", bold=True, color="C00000"))
        + _sect_pr(w=16838, h=11906, orient="landscape")
    )
    return write_docx(path, _document(body))


def make_two_columns(path: Path) -> Path:
    """Single section with 2 equal columns on a short page so content fills col1→col2."""
    long = ("Column flow text. " * 20)
    cols_sect = (
        '<w:sectPr>'
        '<w:pgSz w:w="11906" w:h="5000"/>'  # short page → force column overflow
        '<w:pgMar w:top="360" w:right="360" w:bottom="360" w:left="360" '
        'w:header="360" w:footer="360" w:gutter="0"/>'
        '<w:cols w:num="2" w:space="200" w:equalWidth="1" w:sep="1"/>'
        '</w:sectPr>'
    )
    body = (
        _para(_run("Two Columns", bold=True, size_half_pt=28), align="center")
        + "".join(_para(_run(long)) for _ in range(6))
        + cols_sect
    )
    return write_docx(path, _document(body))


def make_header_footer(path: Path) -> Path:
    """Multi-page doc with header text and footer PAGE field."""
    header_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="{NS_W}">
  <w:p>{_run("Company Header", bold=True, color="2F5496")}</w:p>
</w:hdr>"""
    footer_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{NS_W}">
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    {_run("Page ", bare=True)}
    <w:fldSimple w:instr=" PAGE ">
      <w:r><w:t>1</w:t></w:r>
    </w:fldSimple>
    {_run(" of ", bare=True)}
    <w:fldSimple w:instr=" NUMPAGES ">
      <w:r><w:t>1</w:t></w:r>
    </w:fldSimple>
  </w:p>
</w:ftr>"""

    sect = (
        '<w:sectPr>'
        '<w:headerReference w:type="default" r:id="rId20" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        '<w:footerReference w:type="default" r:id="rId21" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        '</w:sectPr>'
    )
    body = (
        _para(_run("Page one body text."))
        + _para(_run("") + _br("page"))
        + _para(_run("Page two body text."))
        + sect
    )
    rels = [
        '<Relationship Id="rId20" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" '
        'Target="header1.xml"/>',
        '<Relationship Id="rId21" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" '
        'Target="footer1.xml"/>',
    ]
    return write_docx(
        path,
        _document(body),
        extra_rels=rels,
        headers={"header1.xml": header_xml},
        footers={"footer1.xml": footer_xml},
    )


def make_date_field(path: Path) -> Path:
    """One-page footer DATE field with an intentionally stale cached result."""
    footer_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{NS_W}">
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    {_run("Reference date: ", bare=True)}
    <w:fldSimple w:instr=' DATE \\@ "yyyy-MM-dd" '>
      <w:r><w:t>2000-01-01</w:t></w:r>
    </w:fldSimple>
  </w:p>
</w:ftr>"""
    sect = (
        '<w:sectPr>'
        '<w:footerReference w:type="default" r:id="rId21" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        '</w:sectPr>'
    )
    rels = [
        '<Relationship Id="rId21" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" '
        'Target="footer1.xml"/>',
    ]
    body = _para(_run("Deterministic DATE field.", bare=True)) + sect
    return write_docx(
        path,
        _document(body),
        extra_rels=rels,
        footers={"footer1.xml": footer_xml},
    )


def make_hyperlink_field(path: Path) -> Path:
    """One-page footer with a cached w:fldSimple HYPERLINK result."""
    footer_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{NS_W}">
  <w:p>
    <w:pPr><w:jc w:val="center"/></w:pPr>
    {_run("Link: ", bare=True)}
    <w:fldSimple w:instr=' HYPERLINK "https://example.com" '>
      <w:r>
        <w:rPr>
          <w:color w:val="0563C1"/>
          <w:u w:val="single"/>
          <w:sz w:val="22"/>
        </w:rPr>
        <w:t>Cached destination</w:t>
      </w:r>
    </w:fldSimple>
  </w:p>
</w:ftr>"""
    sect = (
        '<w:sectPr>'
        '<w:footerReference w:type="default" r:id="rId21" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        '</w:sectPr>'
    )
    rels = [
        '<Relationship Id="rId21" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" '
        'Target="footer1.xml"/>',
    ]
    body = _para(_run("Cached HYPERLINK field.", bare=True)) + sect
    return write_docx(
        path,
        _document(body),
        extra_rels=rels,
        footers={"footer1.xml": footer_xml},
    )


def make_lists(path: Path) -> Path:
    """Bullet + numbered lists."""
    numbering = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{NS_W}">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="•"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:abstractNum w:abstractNumId="1">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="decimal"/>
      <w:lvlText w:val="%1."/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
    </w:lvl>
    <w:lvl w:ilvl="1">
      <w:start w:val="1"/>
      <w:numFmt w:val="lowerLetter"/>
      <w:lvlText w:val="%2)"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="1440" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
  <w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>"""

    def num_para(text: str, num_id: int, ilvl: int = 0) -> str:
        return (
            f'<w:p><w:pPr><w:numPr>'
            f'<w:ilvl w:val="{ilvl}"/><w:numId w:val="{num_id}"/>'
            f'</w:numPr></w:pPr>{_run(text, bare=True)}</w:p>'
        )

    body = (
        _para(_run("Lists", bold=True, size_half_pt=28))
        + num_para("Bullet one", 1)
        + num_para("Bullet two", 1)
        + num_para("Numbered one", 2)
        + num_para("Numbered two", 2)
        + num_para("Nested letter", 2, 1)
        + num_para("Numbered three", 2)
        + _sect_pr()
    )
    return write_docx(path, _document(body), numbering_xml=numbering)


def _tab_run() -> str:
    return "<w:r><w:tab/></w:r>"


def _anchor_drawing(
    rid: str = "rId10",
    cx: int = 1143000,
    cy: int = 857250,
    pos_x_emu: int = 0,
    pos_y_emu: int = 0,
    wrap: str = "square",
) -> str:
    """Floating anchor drawing. wrap: square | topAndBottom | behind | inFrontOf."""
    if wrap == "topAndBottom":
        wrap_xml = "<wp:wrapTopAndBottom/>"
        behind = "0"
    elif wrap == "behind":
        wrap_xml = "<wp:wrapNone/>"
        behind = "1"
    elif wrap == "inFrontOf":
        wrap_xml = "<wp:wrapNone/>"
        behind = "0"
    else:
        wrap_xml = '<wp:wrapSquare wrapText="bothSides"/>'
        behind = "0"
    return f"""<w:r><w:drawing>
      <wp:anchor xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                 xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
                 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                 distT="0" distB="0" distL="0" distR="0"
                 simplePos="0" relativeHeight="0" behindDoc="{behind}"
                 locked="0" layoutInCell="1" allowOverlap="1">
        <wp:simplePos x="0" y="0"/>
        <wp:positionH relativeFrom="column">
          <wp:posOffset>{pos_x_emu}</wp:posOffset>
        </wp:positionH>
        <wp:positionV relativeFrom="paragraph">
          <wp:posOffset>{pos_y_emu}</wp:posOffset>
        </wp:positionV>
        <wp:extent cx="{cx}" cy="{cy}"/>
        {wrap_xml}
        <a:graphic>
          <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
            <pic:pic>
              <pic:blipFill>
                <a:blip r:embed="{rid}"/>
              </pic:blipFill>
              <pic:spPr>
                <a:xfrm><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
              </pic:spPr>
            </pic:pic>
          </a:graphicData>
        </a:graphic>
      </wp:anchor>
    </w:drawing></w:r>"""


def make_justify_tabs(path: Path) -> Path:
    """Justify paragraph + tab stops with dot leader."""
    long = (
        "The quick brown fox jumps over the lazy dog. "
        "Pack my box with five dozen liquor jugs. "
        "How vexingly quick daft zebras jump again and again."
    )
    tabs = (
        '<w:tabs>'
        '<w:tab w:val="left" w:pos="4320" w:leader="dot"/>'
        '<w:tab w:val="right" w:pos="8640" w:leader="underscore"/>'
        '</w:tabs>'
    )
    body = (
        _para(_run(long), align="both")
        + _para(
            _run("Chapter 1", bare=True) + _tab_run() + _run("3", bare=True),
            tabs_xml=tabs,
        )
        + _para(
            _run("Appendix", bare=True) + _tab_run() + _run("99", bare=True),
            tabs_xml=tabs,
        )
        + _sect_pr()
    )
    return write_docx(path, _document(body))


def make_float_image(path: Path) -> Path:
    """Paragraph with floating square-wrap image on the right + wrapping text."""
    png = _make_png_bytes(color=(0, 160, 0))
    # ~1.25" wide, placed ~3.5" from column left
    drawing = _anchor_drawing(
        "rId10",
        cx=1143000,
        cy=857250,
        pos_x_emu=3200400,
        pos_y_emu=0,
        wrap="square",
    )
    long = (
        "Floating wrap text flows beside the green image box. "
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789. "
        "Repeat the sentence so multiple lines hug the float exclusion zone. "
        "More wrapping content to force several lines around the picture area."
    )
    body = (
        _para(drawing + _run(long, bare=True))
        + _para(_run("After the float paragraph."))
        + _sect_pr()
    )
    rel = (
        '<Relationship Id="rId10" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        'Target="media/image1.png"/>'
    )
    return write_docx(
        path,
        _document(body),
        media={"image1.png": png},
        extra_rels=[rel],
    )


def make_textbox(path: Path) -> Path:
    """Simple text box via w:txbxContent inside an anchor."""
    # 2" x 1"
    cx, cy = 1828800, 914400
    drawing = f"""<w:r><w:drawing>
      <wp:anchor xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                 distT="0" distB="0" distL="0" distR="0"
                 simplePos="0" relativeHeight="0" behindDoc="0"
                 locked="0" layoutInCell="1" allowOverlap="1">
        <wp:simplePos x="0" y="0"/>
        <wp:positionH relativeFrom="column"><wp:posOffset>914400</wp:posOffset></wp:positionH>
        <wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>
        <wp:extent cx="{cx}" cy="{cy}"/>
        <wp:wrapNone/>
        <w:txbxContent xmlns:w="{NS_W}">
          <w:p>{_run("Box text", bold=True, color="C00000")}</w:p>
        </w:txbxContent>
      </wp:anchor>
    </w:drawing></w:r>"""
    body = (
        _para(_run("Before textbox. ", bare=True) + drawing + _run(" After.", bare=True))
        + _sect_pr()
    )
    return write_docx(path, _document(body))


NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def make_shape_fill(path: Path) -> Path:
    """Filled + outlined DrawingML text box and autoshape.

    Two ``wps:wsp`` shapes inside a WordprocessingShape graphicData: an
    autoshape (yellow fill, red outline) and a text box (blue fill, no
    outline). Word renders the coloured backgrounds and outlines; this is the
    ``shape_fill`` office golden case quantifying standalone-shape fill/border
    fidelity (the standalone parse path previously dropped both).
    """

    def _shape(text, fill, border, pos_x, pos_y, cx=1828800, cy=914400):
        c_nv_sp_pr = '<wps:cNvSpPr txBox="1"/>'
        if fill:
            fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
        else:
            fill_xml = "<a:noFill/>"
        border_xml = ""
        if border:
            border_xml = (
                f'<a:ln w="25400">'
                f'<a:solidFill><a:srgbClr val="{border}"/></a:solidFill>'
                f"</a:ln>"
            )
        sp_pr = (
            "<wps:spPr>"
            f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f"{fill_xml}{border_xml}"
            "</wps:spPr>"
        )
        style_xml = (
            "<wps:style>"
            '<a:lnRef idx="2"><a:schemeClr val="accent1">'
            '<a:shade val="15000"/></a:schemeClr></a:lnRef>'
            '<a:fillRef idx="1"><a:schemeClr val="accent1"/></a:fillRef>'
            '<a:effectRef idx="0"><a:schemeClr val="accent1"/></a:effectRef>'
            '<a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef>'
            "</wps:style>"
        )
        body = (
            "<wps:txbx><w:txbxContent>"
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            f'{_run(text, bold=True, color="000000")}</w:p>'
            "</w:txbxContent></wps:txbx>"
            '<wps:bodyPr rot="0" vert="horz" lIns="91440" tIns="45720" '
            'rIns="91440" bIns="45720" anchor="ctr"/>'
        )
        return (
            "<w:r><w:drawing>"
            '  <wp:anchor xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
            '             xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
            '             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
            '             xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
            f'            xmlns:w="{NS_W}"'
            '            distT="0" distB="0" distL="0" distR="0" simplePos="0"'
            '            relativeHeight="0" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">'
            '    <wp:simplePos x="0" y="0"/>'
            f'    <wp:positionH relativeFrom="column"><wp:posOffset>{pos_x}</wp:posOffset></wp:positionH>'
            f'    <wp:positionV relativeFrom="paragraph"><wp:posOffset>{pos_y}</wp:posOffset></wp:positionV>'
            f'    <wp:extent cx="{cx}" cy="{cy}"/>'
            '    <wp:effectExtent l="0" t="0" r="0" b="0"/>'
            "    <wp:wrapNone/>"
            '    <wp:docPr id="1" name="Shape"/>'
            "    <wp:cNvGraphicFramePr/>"
            '    <a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
            f"      <wps:wsp><wps:cNvPr id=\"1\" name=\"Shape\"/>{c_nv_sp_pr}"
            f"{sp_pr}{style_xml}{body}</wps:wsp>"
            "    </a:graphicData></a:graphic>"
            "  </wp:anchor>"
            "</w:drawing></w:r>"
        )

    shape_a = _shape("Shape A", "FFCC00", "FF0000", 0, 300000)
    shape_b = _shape("Box B", "4472C4", None, 2400000, 300000)
    body = (
        _para(_run("Before shapes.", bare=True))
        + _para(shape_a + shape_b)
        + _para(_run("After shapes.", bare=True))
        + _sect_pr()
    )
    return write_docx(path, _document(body))


def make_drawingml_text(path: Path) -> Path:
    """DrawingML ``a:txBody`` text inside a standards-based locked canvas.

    ``lc:lockedCanvas`` is a valid ``a:graphicData`` payload and may contain
    ``a:sp/a:txSp/a:txBody`` shape text.  This deliberately avoids
    ``wps:txbx/w:txbxContent`` so the office golden isolates the native
    DrawingML text-body parser path.
    """
    cx, cy = 2743200, 914400  # 3" × 1"
    drawing = (
        "<w:r><w:drawing>"
        '  <wp:anchor xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
        '             xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        '             xmlns:lc="http://schemas.openxmlformats.org/drawingml/2006/lockedCanvas"'
        '             distT="0" distB="0" distL="0" distR="0" simplePos="0"'
        '             relativeHeight="251658240" behindDoc="0" locked="0"'
        '             layoutInCell="1" allowOverlap="1">'
        '    <wp:simplePos x="0" y="0"/>'
        '    <wp:positionH relativeFrom="column"><wp:posOffset>457200</wp:posOffset></wp:positionH>'
        '    <wp:positionV relativeFrom="paragraph"><wp:posOffset>228600</wp:posOffset></wp:positionV>'
        f'    <wp:extent cx="{cx}" cy="{cy}"/>'
        '    <wp:effectExtent l="0" t="0" r="0" b="0"/>'
        "    <wp:wrapNone/>"
        '    <wp:docPr id="41" name="DrawingML text body"/>'
        "    <wp:cNvGraphicFramePr/>"
        '    <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/lockedCanvas">'
        "      <lc:lockedCanvas>"
        "        <a:nvGrpSpPr>"
        '          <a:cNvPr id="1" name="Locked canvas"/>'
        "          <a:cNvGrpSpPr/>"
        "        </a:nvGrpSpPr>"
        "        <a:grpSpPr><a:xfrm>"
        '          <a:off x="0" y="0"/>'
        f'          <a:ext cx="{cx}" cy="{cy}"/>'
        '          <a:chOff x="0" y="0"/>'
        f'          <a:chExt cx="{cx}" cy="{cy}"/>'
        "        </a:xfrm></a:grpSpPr>"
        "        <a:sp>"
        "          <a:nvSpPr>"
        '            <a:cNvPr id="2" name="DrawingML text shape"/>'
        "            <a:cNvSpPr/>"
        "          </a:nvSpPr>"
        "          <a:spPr>"
        f'            <a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '            <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "            <a:noFill/><a:ln><a:noFill/></a:ln>"
        "          </a:spPr>"
        "          <a:txSp>"
        '          <a:txBody><a:bodyPr wrap="square" lIns="91440" tIns="45720"'
        '              rIns="91440" bIns="45720" anchor="ctr"/>'
        "            <a:lstStyle/>"
        '            <a:p><a:pPr algn="ctr"/>'
        '              <a:r><a:rPr lang="en-US" sz="1800" b="1">'
        '                <a:solidFill><a:srgbClr val="C00000"/></a:solidFill>'
        '                <a:latin typeface="Times New Roman"/>'
        "              </a:rPr><a:t>DrawingML txBody</a:t></a:r>"
        '              <a:endParaRPr lang="en-US" sz="1800"/>'
        "            </a:p>"
        "          </a:txBody>"
        "            <a:useSpRect/>"
        "          </a:txSp>"
        "        </a:sp>"
        "      </lc:lockedCanvas>"
        "    </a:graphicData></a:graphic>"
        "  </wp:anchor>"
        "</w:drawing></w:r>"
    )
    body = (
        _para(_run("Before DrawingML text.", bare=True))
        + _para(drawing)
        + _para(_run("After DrawingML text.", bare=True))
        + _sect_pr()
    )
    return write_docx(path, _document(body))


def make_math(path: Path) -> Path:
    """Inline OMML: fraction, superscript, radical, n-ary."""
    frac = (
        f'<m:oMath xmlns:m="{NS_M}">'
        f"<m:f><m:num><m:r><m:t>a</m:t></m:r></m:num>"
        f"<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f>"
        f"</m:oMath>"
    )
    sup = (
        f'<m:oMath xmlns:m="{NS_M}">'
        f"<m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e>"
        f"<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>"
        f"</m:oMath>"
    )
    rad = (
        f'<m:oMath xmlns:m="{NS_M}">'
        f"<m:rad><m:deg/><m:e><m:r><m:t>2</m:t></m:r></m:e></m:rad>"
        f"</m:oMath>"
    )
    nary = (
        f'<m:oMath xmlns:m="{NS_M}">'
        f'<m:nary><m:naryPr><m:chr m:val="∑"/></m:naryPr>'
        f"<m:sub><m:r><m:t>i</m:t></m:r></m:sub>"
        f"<m:sup><m:r><m:t>n</m:t></m:r></m:sup>"
        f"<m:e><m:r><m:t>i</m:t></m:r></m:e></m:nary>"
        f"</m:oMath>"
    )
    body = (
        _para(_run("Math: ", bare=True) + frac + _run(" and ", bare=True) + sup)
        + _para(rad + _run("  ", bare=True) + nary)
        + _sect_pr()
    )
    return write_docx(path, _document(body))


def make_math_bar(path: Path) -> Path:
    """Single native OMML bottom bar, isolated from paragraph-flow noise."""
    bottom = (
        f'<m:oMath xmlns:m="{NS_M}"><m:bar>'
        '<m:barPr><m:pos m:val="bot"/></m:barPr>'
        '<m:e><m:r><m:t>xy</m:t></m:r></m:e>'
        '</m:bar></m:oMath>'
    )
    body = _para(bottom, align="center") + _sect_pr()
    return write_docx(path, _document(body))


def make_math_accent(path: Path) -> Path:
    """Single native OMML accent, isolated from paragraph-flow noise."""
    accent = (
        f'<m:oMath xmlns:m="{NS_M}"><m:acc>'
        '<m:accPr><m:chr m:val="~"/></m:accPr>'
        '<m:e><m:r><m:t>xy</m:t></m:r></m:e>'
        '</m:acc></m:oMath>'
    )
    body = _para(accent, align="center") + _sect_pr()
    return write_docx(path, _document(body))


def make_math_border_box(path: Path) -> Path:
    """Single native OMML border box, isolated from paragraph-flow noise."""
    border = (
        f'<m:oMath xmlns:m="{NS_M}"><m:borderBox>'
        '<m:e><m:r><m:t>xy</m:t></m:r></m:e>'
        '</m:borderBox></m:oMath>'
    )
    body = _para(border, align="center") + _sect_pr()
    return write_docx(path, _document(body))


def make_math_limit(path: Path) -> Path:
    """Single native OMML lower limit, isolated from paragraph-flow noise."""
    limit = (
        f'<m:oMath xmlns:m="{NS_M}"><m:limLow>'
        '<m:e><m:r><m:t>lim</m:t></m:r></m:e>'
        '<m:lim><m:r><m:t>x=0</m:t></m:r></m:lim>'
        '</m:limLow></m:oMath>'
    )
    body = _para(limit, align="center") + _sect_pr()
    return write_docx(path, _document(body))


def make_math_eq_arr(path: Path) -> Path:
    """Single native two-row OMML equation array."""
    equations = (
        f'<m:oMath xmlns:m="{NS_M}"><m:eqArr>'
        '<m:e><m:r><m:t>a</m:t></m:r></m:e>'
        '<m:e><m:r><m:t>b</m:t></m:r></m:e>'
        '</m:eqArr></m:oMath>'
    )
    body = _para(equations, align="center") + _sect_pr()
    return write_docx(path, _document(body))


def make_footnote(path: Path) -> Path:
    """One body reference and one plain-text footnote definition."""
    body = (
        _para(
            _run("Body text", bare=True)
            + '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
            '<w:sz w:val="20"/></w:rPr>'
            '<w:footnoteReference w:id="1"/></w:r>'
        )
        + _sect_pr()
    )
    footnotes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{NS_W}">'
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r>'
        '<w:separator/></w:r></w:p></w:footnote>'
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r>'
        '<w:continuationSeparator/></w:r></w:p></w:footnote>'
        '<w:footnote w:id="1"><w:p>'
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr><w:footnoteRef/></w:r>'
        '<w:r><w:tab/></w:r>'
        '<w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        '<w:t>Footnote text.</w:t></w:r>'
        '</w:p></w:footnote>'
        '</w:footnotes>'
    )
    return write_docx(
        path,
        _document(body),
        footnotes_xml=footnotes,
    )


def make_footnote_reflow(path: Path) -> Path:
    """Near-full short page whose final paragraph owns a footnote.

    Without reserving space for the note, all eight body paragraphs fit on
    page one and the footnote overlaps the final paragraph. Word moves the
    reference paragraph to page two so the page-bottom note remains clear.
    """
    sect = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="6000"/>'
        '<w:pgMar w:top="920" w:right="1800" w:bottom="920" w:left="1800" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    body = "".join(
        _para(_run(f"Filler {i}", size_half_pt=28), space_after=120)
        for i in range(1, 8)
    )
    body += _para(
        _run("Reference paragraph", size_half_pt=28, bare=True)
        + '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr>'
        '<w:footnoteReference w:id="1"/></w:r>',
        space_after=120,
    )
    footnotes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{NS_W}">'
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r>'
        '<w:separator/></w:r></w:p></w:footnote>'
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r>'
        '<w:continuationSeparator/></w:r></w:p></w:footnote>'
        '<w:footnote w:id="1"><w:p>'
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr><w:footnoteRef/></w:r>'
        '<w:r><w:tab/></w:r>'
        '<w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        '<w:t>Reserved footnote.</w:t></w:r>'
        '</w:p></w:footnote>'
        '</w:footnotes>'
    )
    return write_docx(
        path,
        _document(body + sect),
        footnotes_xml=footnotes,
    )


def make_footnote_continuation(path: Path) -> Path:
    """One multi-paragraph footnote that must continue onto page two."""
    sect = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="6000"/>'
        '<w:pgMar w:top="920" w:right="1800" w:bottom="920" w:left="1800" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    body = _para(
        _run("Body reference", size_half_pt=28, bare=True)
        + '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr>'
        '<w:footnoteReference w:id="1"/></w:r>',
        space_after=120,
    )
    note_paragraphs = (
        '<w:p><w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr><w:footnoteRef/></w:r>'
        '<w:r><w:tab/></w:r><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        '<w:t>Continuation line 1</w:t></w:r></w:p>'
    )
    note_paragraphs += "".join(
        '<w:p><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        f'<w:t>Continuation line {i}</w:t></w:r></w:p>'
        for i in range(2, 19)
    )
    footnotes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{NS_W}">'
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r>'
        '<w:separator/></w:r></w:p></w:footnote>'
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r>'
        '<w:continuationSeparator/></w:r></w:p></w:footnote>'
        f'<w:footnote w:id="1">{note_paragraphs}</w:footnote>'
        '</w:footnotes>'
    )
    return write_docx(
        path,
        _document(body + sect),
        footnotes_xml=footnotes,
    )


def make_footnote_multiple_continuation(path: Path) -> Path:
    """Two same-page footnotes whose combined paragraphs need page two."""
    sect = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="6000"/>'
        '<w:pgMar w:top="920" w:right="1800" w:bottom="920" w:left="1800" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    reference = (
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr>'
    )
    body = _para(
        _run("Body references", size_half_pt=28, bare=True)
        + reference
        + '<w:footnoteReference w:id="1"/></w:r>'
        + _run(" and ", size_half_pt=28, bare=True)
        + reference
        + '<w:footnoteReference w:id="2"/></w:r>',
        space_after=120,
    )

    def note_xml(note_id: int, label: str, count: int) -> str:
        first = (
            '<w:p><w:r><w:rPr><w:vertAlign w:val="superscript"/>'
            '<w:sz w:val="20"/></w:rPr><w:footnoteRef/></w:r>'
            '<w:r><w:tab/></w:r><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
            f'<w:t>{label} line 1</w:t></w:r></w:p>'
        )
        rest = "".join(
            '<w:p><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
            f'<w:t>{label} line {i}</w:t></w:r></w:p>'
            for i in range(2, count + 1)
        )
        return f'<w:footnote w:id="{note_id}">{first}{rest}</w:footnote>'

    footnotes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{NS_W}">'
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r>'
        '<w:separator/></w:r></w:p></w:footnote>'
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r>'
        '<w:continuationSeparator/></w:r></w:p></w:footnote>'
        + note_xml(1, "First note", 5)
        + note_xml(2, "Second note", 13)
        + '</w:footnotes>'
    )
    return write_docx(
        path,
        _document(body + sect),
        footnotes_xml=footnotes,
    )


def make_footnote_line_continuation(path: Path) -> Path:
    """One footnote paragraph with explicit line breaks spanning two pages."""
    sect = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="6000"/>'
        '<w:pgMar w:top="920" w:right="1800" w:bottom="920" w:left="1800" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    body = _para(
        _run("Body reference", size_half_pt=28, bare=True)
        + '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr>'
        '<w:footnoteReference w:id="1"/></w:r>',
        space_after=120,
    )
    line_runs = (
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr><w:footnoteRef/></w:r>'
        '<w:r><w:tab/></w:r><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        '<w:t>Explicit line 1</w:t></w:r>'
    )
    line_runs += "".join(
        '<w:r><w:br/></w:r><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        f'<w:t>Explicit line {i}</w:t></w:r>'
        for i in range(2, 19)
    )
    footnotes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{NS_W}">'
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r>'
        '<w:separator/></w:r></w:p></w:footnote>'
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r>'
        '<w:continuationSeparator/></w:r></w:p></w:footnote>'
        f'<w:footnote w:id="1"><w:p>{line_runs}</w:p></w:footnote>'
        '</w:footnotes>'
    )
    return write_docx(
        path,
        _document(body + sect),
        footnotes_xml=footnotes,
    )


def make_footnote_wrap_continuation(path: Path) -> Path:
    """One automatically wrapped footnote paragraph spanning two pages."""
    sect = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="6000"/>'
        '<w:pgMar w:top="920" w:right="1800" w:bottom="920" w:left="1800" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    body = _para(
        _run("Body reference", size_half_pt=28, bare=True)
        + '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr>'
        '<w:footnoteReference w:id="1"/></w:r>',
        space_after=120,
    )
    tokens = " ".join(
        f"AutoWrap{i:02d}" + ("M" * 19) for i in range(1, 19)
    )
    footnotes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{NS_W}">'
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r>'
        '<w:separator/></w:r></w:p></w:footnote>'
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r>'
        '<w:continuationSeparator/></w:r></w:p></w:footnote>'
        '<w:footnote w:id="1"><w:p>'
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr><w:footnoteRef/></w:r>'
        '<w:r><w:tab/></w:r><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        f'<w:t>{tokens}</w:t></w:r>'
        '</w:p></w:footnote></w:footnotes>'
    )
    return write_docx(
        path,
        _document(body + sect),
        footnotes_xml=footnotes,
    )


def make_endnote(path: Path) -> Path:
    """One body reference and one plain-text endnote definition."""
    body = (
        _para(
            _run("Body text", bare=True)
            + '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
            '<w:sz w:val="20"/></w:rPr>'
            '<w:endnoteReference w:id="1"/></w:r>'
        )
        + _sect_pr()
    )
    endnotes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:endnotes xmlns:w="{NS_W}">'
        '<w:endnote w:type="separator" w:id="-1"><w:p><w:r>'
        '<w:separator/></w:r></w:p></w:endnote>'
        '<w:endnote w:type="continuationSeparator" w:id="0"><w:p><w:r>'
        '<w:continuationSeparator/></w:r></w:p></w:endnote>'
        '<w:endnote w:id="1"><w:p>'
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr><w:endnoteRef/></w:r>'
        '<w:r><w:tab/></w:r>'
        '<w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        '<w:t>Endnote text.</w:t></w:r>'
        '</w:p></w:endnote>'
        '</w:endnotes>'
    )
    return write_docx(
        path,
        _document(body),
        endnotes_xml=endnotes,
    )


def make_endnote_continuation(path: Path) -> Path:
    """One multi-paragraph endnote that must continue onto page two."""
    sect = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="6000"/>'
        '<w:pgMar w:top="920" w:right="1800" w:bottom="920" w:left="1800" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    body = _para(
        _run("Body reference", size_half_pt=28, bare=True)
        + '<w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr>'
        '<w:endnoteReference w:id="1"/></w:r>',
        space_after=120,
    )
    note_paragraphs = (
        '<w:p><w:r><w:rPr><w:vertAlign w:val="superscript"/>'
        '<w:sz w:val="20"/></w:rPr><w:endnoteRef/></w:r>'
        '<w:r><w:tab/></w:r><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        '<w:t>Endnote line 1</w:t></w:r></w:p>'
    )
    note_paragraphs += "".join(
        '<w:p><w:r><w:rPr><w:sz w:val="20"/></w:rPr>'
        f'<w:t>Endnote line {i}</w:t></w:r></w:p>'
        for i in range(2, 19)
    )
    endnotes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:endnotes xmlns:w="{NS_W}">'
        '<w:endnote w:type="separator" w:id="-1"><w:p><w:r>'
        '<w:separator/></w:r></w:p></w:endnote>'
        '<w:endnote w:type="continuationSeparator" w:id="0"><w:p><w:r>'
        '<w:continuationSeparator/></w:r></w:p></w:endnote>'
        f'<w:endnote w:id="1">{note_paragraphs}</w:endnote>'
        '</w:endnotes>'
    )
    return write_docx(
        path,
        _document(body + sect),
        endnotes_xml=endnotes,
    )


if __name__ == "__main__":
    out = Path(__file__).parent
    make_basic_text(out / "basic_text.docx")
    make_page_break(out / "page_break.docx")
    make_long_wrap(out / "long_wrap.docx")
    make_landscape(out / "landscape.docx")
    make_styled(out / "styled_text.docx")
    make_basic_table(out / "tables.docx")
    make_merged_table(out / "merged_table.docx")
    make_nested_table(out / "nested_table.docx")
    make_inline_image(out / "images.docx")
    make_two_sections(out / "two_sections.docx")
    make_two_columns(out / "two_columns.docx")
    make_header_footer(out / "headers_footers.docx")
    make_date_field(out / "date_field.docx")
    make_hyperlink_field(out / "hyperlink_field.docx")
    make_lists(out / "lists.docx")
    make_justify_tabs(out / "justify_tabs.docx")
    make_float_image(out / "float_image.docx")
    make_textbox(out / "textbox.docx")
    make_drawingml_text(out / "drawingml_text.docx")
    make_math(out / "math.docx")
    make_math_bar(out / "math_bar.docx")
    make_math_accent(out / "math_accent.docx")
    make_math_border_box(out / "math_border_box.docx")
    make_math_limit(out / "math_limit.docx")
    make_math_eq_arr(out / "math_eq_arr.docx")
    make_footnote(out / "footnote.docx")
    make_footnote_reflow(out / "footnote_reflow.docx")
    make_footnote_continuation(out / "footnote_continuation.docx")
    make_footnote_multiple_continuation(
        out / "footnote_multiple_continuation.docx"
    )
    make_footnote_line_continuation(
        out / "footnote_line_continuation.docx"
    )
    make_footnote_wrap_continuation(
        out / "footnote_wrap_continuation.docx"
    )
    make_endnote(out / "endnote.docx")
    make_endnote_continuation(out / "endnote_continuation.docx")
    print("Fixtures written to", out)
