"""Tests for scripts/generate_lo_golden.py helpers."""

import zipfile
from pathlib import Path

import pytest

from scripts.generate_lo_golden import strip_tracked_changes

REPO = Path(__file__).resolve().parent.parent.parent
TRACKED = (
    REPO
    / "testdata"
    / "regression"
    / "sample-files-complex"
    / "sample-files.com-tracked-changes.docx"
)

pytestmark = pytest.mark.skipif(
    not TRACKED.exists(),
    reason="optional external visual-regression corpus is not available",
)


def test_strip_tracked_changes_removes_revision_markup(tmp_path):
    """The cleaned DOCX must drop w:ins/w:del/comment ranges."""
    cleaned = strip_tracked_changes(TRACKED, tmp_path)
    assert cleaned.exists()
    with zipfile.ZipFile(cleaned) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    assert "w:ins" not in doc
    assert "w:del" not in doc
    assert "w:commentRangeStart" not in doc
    assert "w:commentRangeEnd" not in doc
    assert "w:commentReference" not in doc


def test_strip_tracked_changes_preserves_final_text(tmp_path):
    """Insertions should be kept and deletions removed in the cleaned text."""
    cleaned = strip_tracked_changes(TRACKED, tmp_path)
    with zipfile.ZipFile(cleaned) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    # The title is unchanged.
    assert "Project Proposal: Website Redesign" in doc
    # Deleted phrase from the document is gone; inserted phrase is kept.
    assert "make the website better" not in doc
    assert "improve user experience, increase conversion rates" in doc
