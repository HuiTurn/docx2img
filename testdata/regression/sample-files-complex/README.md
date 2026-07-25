# Complex DOCX regression corpus

Downloaded from [Sample-Files.com DOCX samples](https://sample-files.com/documents/docx/) on 2026-07-25 for local visual-regression testing.  Confirm the source's licence and redistribution terms before committing these documents to a public repository.

| File | Coverage | SHA-256 |
|---|---|---|
| `sample-files.com-image-document.docx` | Embedded images and text wrapping | `8c2a8c4725e77bbfb4ddc7925674dc221611a39b876dbd7ea2efc829e70b8530` |
| `sample-files.com-table-document.docx` | Multiple complex tables | `f11873de3cb3f1f2424806b21aab6e6c95e5a54bf05875a62fd7ac0420d33189` |
| `sample-files.com-template.docx` | Content controls and form fields | `1c675c67c6664e250b4b21a59a7b73f090d6d4e4626f151c55adbada9d79c6b1` |
| `sample-files.com-lists.docx` | Bulleted, numbered, and nested lists | `fa458becb212f0970211ead57726a1b457d706be07f2b635f40ca419a794ff0f` |
| `sample-files.com-tracked-changes.docx` | Revisions and comments | `56d880c6099dbf982d8a4ad1da71e482440171cb8a456a804bfa3c0010001076` |
| `sample-files.com-multi-column.docx` | Two-column layout and section breaks | `a4b4a8a7e6ecdc31f90cab6e2fb53fb50c72b94232593747dbc1d023bdbc4d6c` |
| `sample-files.com-large-document.docx` | 50-page, multi-section document with styles and TOC | `94d1e6bc3fcef399e69d49543fcabbf62ee9dad4873c1c0958a5d46cdf6654ea` |

Re-verify downloads with:

```bash
shasum -a 256 testdata/regression/sample-files-complex/*.docx
```
