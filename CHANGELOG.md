# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-07-31

### Added

- Legacy VML flowchart rendering for rectangles, diamonds, text boxes, connector
  lines, arrowheads, fills, borders, insets, and overlay positioning
- Cross-page flow for long paragraphs with widow/orphan control
- Row-boundary table splitting so tables can use the remaining page area

### Changed

- Paragraph-relative floating objects now exclude text in later overlapping
  paragraphs, improving tight and square text wrapping
- CJK automatic line boxes and document-grid interval selection now use
  typographic font metrics, including WPS-compatible unsnapped line spacing
- CJK justification can absorb small overflow and hang closing punctuation at
  the right edge instead of creating visibly underfilled lines

### Fixed

- Break-only paragraphs now retain their paragraph-mark height and trailing
  spacing, preserving Word's blank intermediate page when a manual page break
  overflows
- Long paragraphs split by line instead of moving as one atomic block
- CJK wrapping keeps the final character that still fits on the current line
- Exact font family files now take priority over filename-derived aliases in
  the same discovery tier. On macOS, `Times New Roman` no longer resolves to
  `Times.ttc`, restoring the expected pagination and footnote continuation
  points
- Package metadata and `docx2img.__version__` now report the same version

## [0.1.1] - 2026-07-30

### Fixed

- Header text no longer wraps onto a second line; text width is now measured
  with exact fontTools glyph advances instead of estimates, fixing both CJK
  over-wide and under-wide lines
- Body content no longer overlaps the header separator rule; the body area now
  starts below the header
- Justified CJK paragraphs now distribute slack across inter-glyph gaps the
  way Word does, removing uneven holes in justified text
- TOC dot leaders are packed tightly and right-aligned flush at the tab stop,
  so dot columns line up vertically across entries
- `PAGE` fields inside footer text boxes now render the correct page number
- East-Asian line breaking now matches Word behaviour:
  - no punctuation width compression when `w:noPunctuationKerning` is set
  - closing punctuation hangs past the wrap edge (`w:overflowPunct`)
  - auto-spacing (`w:autoSpaceDE/DN`) applies only at genuine
    ideograph/kana/hangul ↔ Latin boundaries, not around full-width symbols
  - kinsoku line compression slightly shrinks CJK glyph gaps to absorb a small
    overflow instead of orphaning a lone character onto a near-empty line
- Trailing whitespace at paragraph end no longer produces stray whitespace-only
  final lines
- Image-only lines are snapped to the document grid (`w:snapToGrid`) and the
  inline picture is vertically centred in the enlarged line box, fixing
  vertical drift of all content below an inline image

### Changed

- `tests/output/` is no longer tracked in git (it was already listed in
  `.gitignore`); the two affected test fixtures were regenerated to match the
  current fixture generator

## [0.1.0] - 2026-07-28

Initial release.

- Pure-Python DOCX → image converter with no LibreOffice/Word dependency;
  Python API plus a `docx2img` command-line tool
- OOXML parsing: document body, styles, headers/footers, footnotes/endnotes,
  simple and complex fields, content controls (SDT), alternate content, and
  custom XML
- Layout engine: East-Asian line breaking, justification, tab stops and
  leaders, nested/merged tables, floating images and text boxes, multi-column
  sections, and document-grid line snapping
- Rendering: styled text, tables, images, and equations with font
  fallback/metrics via fontTools and Pillow
- Published on PyPI as `docx2img`

[0.1.2]: https://github.com/HuiTurn/docx2img/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/HuiTurn/docx2img/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/HuiTurn/docx2img/releases/tag/v0.1.0
