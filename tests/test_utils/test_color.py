"""Tests for color utilities"""

import pytest
from src.docx2img.utils.color import parse_color


class TestParseColor:
    """Test cases for parse_color function"""

    def test_parse_red(self):
        """Test parsing red color"""
        assert parse_color("FF0000") == (255, 0, 0)

    def test_parse_green(self):
        """Test parsing green color"""
        assert parse_color("00FF00") == (0, 255, 0)

    def test_parse_blue(self):
        """Test parsing blue color"""
        assert parse_color("0000FF") == (0, 0, 255)

    def test_parse_black(self):
        """Test parsing black color"""
        assert parse_color("000000") == (0, 0, 0)

    def test_parse_white(self):
        """Test parsing white color"""
        assert parse_color("FFFFFF") == (255, 255, 255)

    def test_parse_with_hash_prefix(self):
        """Test parsing color with # prefix"""
        assert parse_color("#FF0000") == (255, 0, 0)
        assert parse_color("#00FF00") == (0, 255, 0)
        assert parse_color("#0000FF") == (0, 0, 255)

    def test_parse_mixed_color(self):
        """Test parsing mixed color"""
        assert parse_color("A1B2C3") == (161, 178, 195)

    def test_parse_invalid_length(self):
        """Test parsing invalid length returns default black"""
        assert parse_color("FF") == (0, 0, 0)
        assert parse_color("FFFF") == (0, 0, 0)
        assert parse_color("FFFFFFFF") == (0, 0, 0)

    def test_parse_invalid_chars(self):
        """Test parsing invalid characters returns default black"""
        assert parse_color("GGGGGG") == (0, 0, 0)
        assert parse_color("ZZZZZZ") == (0, 0, 0)
        assert parse_color("12345X") == (0, 0, 0)

    def test_parse_empty_string(self):
        """Test parsing empty string returns default black"""
        assert parse_color("") == (0, 0, 0)

    def test_parse_lowercase(self):
        """Test parsing lowercase hex values"""
        assert parse_color("ff0000") == (255, 0, 0)
        assert parse_color("00ff00") == (0, 255, 0)
        assert parse_color("0000ff") == (0, 0, 255)
        assert parse_color("a1b2c3") == (161, 178, 195)
