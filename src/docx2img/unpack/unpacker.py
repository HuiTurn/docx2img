"""DOCX ZIP unpacker"""

import zipfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class DocxPackage:
    """Represents an unpacked DOCX package
    
    Attributes:
        root_path: Base path inside ZIP (usually empty or 'word/')
        document_xml: Main document XML bytes
        styles_xml: Styles XML bytes (optional)
        numbering_xml: Numbering XML bytes (optional)
        theme_xml: Theme XML bytes (optional)
        media: Dictionary of media files {rId: bytes}
        headers: Dictionary of header files {rId: bytes}
        footers: Dictionary of footer files {rId: bytes}
        rels: Relationships dictionary
    """
    document_xml: bytes = b""
    styles_xml: Optional[bytes] = None
    numbering_xml: Optional[bytes] = None
    theme_xml: Optional[bytes] = None
    media: Dict[str, bytes] = field(default_factory=dict)
    headers: Dict[str, bytes] = field(default_factory=dict)
    footers: Dict[str, bytes] = field(default_factory=dict)
    rels: Dict[str, str] = field(default_factory=dict)  # rId -> target path
    document_rels: Dict[str, str] = field(default_factory=dict)  # rId -> target for document.xml.rels


class Unpacker:
    """Extract DOCX contents from ZIP archive"""
    
    def __init__(self, docx_path: Path):
        self.docx_path = docx_path
    
    def unpack(self) -> DocxPackage:
        """Unpack DOCX and return DocxPackage"""
        package = DocxPackage()
        
        with zipfile.ZipFile(self.docx_path, 'r') as zf:
            # Read main document
            package.document_xml = zf.read('word/document.xml')
            
            # Read optional components
            try:
                package.styles_xml = zf.read('word/styles.xml')
            except KeyError:
                pass
            
            try:
                package.numbering_xml = zf.read('word/numbering.xml')
            except KeyError:
                pass
            
            try:
                package.theme_xml = zf.read('word/theme/theme1.xml')
            except KeyError:
                pass
            
            # Read relationships
            try:
                doc_rels_xml = zf.read('word/_rels/document.xml.rels')
                package.document_rels = self._parse_rels(doc_rels_xml)
            except KeyError:
                pass
            
            try:
                root_rels_xml = zf.read('_rels/.rels')
                package.rels = self._parse_rels(root_rels_xml)
            except KeyError:
                pass
            
            # Extract media files
            for name in zf.namelist():
                if name.startswith('word/media/'):
                    rId = self._extract_rid_from_path(name)
                    if rId:
                        package.media[rId] = zf.read(name)
                
                # Extract headers
                elif name.startswith('word/header'):
                    rId = self._extract_rid_from_path(name)
                    if rId:
                        package.headers[rId] = zf.read(name)
                
                # Extract footers
                elif name.startswith('word/footer'):
                    rId = self._extract_rid_from_path(name)
                    if rId:
                        package.footers[rId] = zf.read(name)
        
        return package
    
    def _parse_rels(self, rels_xml: bytes) -> Dict[str, str]:
        """Parse .rels XML file"""
        import xml.etree.ElementTree as ET
        
        rels = {}
        # Handle OOXML namespace
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
    
    def _extract_rid_from_path(self, path: str) -> Optional[str]:
        """Extract rId from a path like 'word/media/image1.png' -> 'rId1'
        
        This is a heuristic - actual mapping comes from .rels files
        """
        # For media files, we'll use the filename to create a key
        if '/media/' in path:
            filename = path.split('/')[-1]
            # image1.png -> rId1 (heuristic, will be refined in parser)
            return f"media_{filename}"
        return None
