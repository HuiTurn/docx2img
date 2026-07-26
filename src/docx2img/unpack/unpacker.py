"""DOCX ZIP unpacker"""

import zipfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class DocxPackage:
    """Represents an unpacked DOCX package."""
    document_xml: bytes = b""
    styles_xml: Optional[bytes] = None
    numbering_xml: Optional[bytes] = None
    theme_xml: Optional[bytes] = None
    media: Dict[str, bytes] = field(default_factory=dict)
    headers: Dict[str, bytes] = field(default_factory=dict)  # rId or filename → bytes
    footers: Dict[str, bytes] = field(default_factory=dict)
    footnotes_xml: Optional[bytes] = None
    endnotes_xml: Optional[bytes] = None
    rels: Dict[str, str] = field(default_factory=dict)
    document_rels: Dict[str, str] = field(default_factory=dict)


class Unpacker:
    """Extract DOCX contents from ZIP archive"""

    def __init__(self, docx_path: Path):
        self.docx_path = docx_path

    def unpack(self) -> DocxPackage:
        package = DocxPackage()

        with zipfile.ZipFile(self.docx_path, 'r') as zf:
            package.document_xml = zf.read('word/document.xml')

            for name, attr in (
                ('word/styles.xml', 'styles_xml'),
                ('word/numbering.xml', 'numbering_xml'),
                ('word/theme/theme1.xml', 'theme_xml'),
                ('word/footnotes.xml', 'footnotes_xml'),
                ('word/endnotes.xml', 'endnotes_xml'),
            ):
                try:
                    setattr(package, attr, zf.read(name))
                except KeyError:
                    pass

            try:
                package.document_rels = self._parse_rels(zf.read('word/_rels/document.xml.rels'))
            except KeyError:
                pass

            try:
                package.rels = self._parse_rels(zf.read('_rels/.rels'))
            except KeyError:
                pass

            for name in zf.namelist():
                if name.startswith('word/media/'):
                    rel = name[len('word/'):]
                    data = zf.read(name)
                    package.media[rel] = data
                    package.media[name.split('/')[-1]] = data

            # Map headers/footers by rId via document relationships
            for rid, target in package.document_rels.items():
                t = target.replace('\\', '/').lstrip('/')
                if t.startswith('word/'):
                    zip_path = t
                else:
                    zip_path = 'word/' + t
                try:
                    data = zf.read(zip_path)
                except KeyError:
                    continue
                lower = t.lower()
                if 'header' in lower:
                    package.headers[rid] = data
                    package.headers[t.split('/')[-1]] = data
                elif 'footer' in lower:
                    package.footers[rid] = data
                    package.footers[t.split('/')[-1]] = data

        return package

    def _parse_rels(self, rels_xml: bytes) -> Dict[str, str]:
        import xml.etree.ElementTree as ET

        rels = {}
        ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
        try:
            root = ET.fromstring(rels_xml)
            for rel in root.findall('r:Relationship', ns):
                rId = rel.get('Id')
                target = rel.get('Target')
                if rId and target:
                    rels[rId] = target
        except ET.ParseError:
            pass
        return rels
