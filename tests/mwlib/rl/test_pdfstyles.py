#!/usr/bin/env py.test

# Copyright (c) PediaPress GmbH
# See README.txt for additional licensing information.

import pytest
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
import mwlib.writers.rl.pdfstyles as pdfstyles

from mwlib.writers.rl.pdfstyles import (
    BIG_FONT_SIZE,
    BIG_LEADING,
    FONT_SIZE,
    LEADING,
    LIST_LEFT_INDENT,
    MONO_FONT,
    PARA_LEFT_INDENT,
    SANS_FONT,
    SERIF_FONT,
    SMALL_FONT_SIZE,
    SMALL_LEADING,
    TEXT_ALIGN,
    BaseHeadingStyle,
    BaseStyle,
    heading_style,
    text_style,
)


def test_text_style_default_parameters():
    """Test that text_style returns a style with default parameters."""
    style = text_style()
    assert style.name == "text_style_p_indent_0_table_0_size_normal"
    assert style.fontName == SERIF_FONT
    assert style.alignment == TA_JUSTIFY
    assert style.flowable is True


def test_text_style_modes():
    """Test that text_style handles different modes correctly."""
    # Test each mode and verify key attributes
    modes = [
        "p", "blockquote", "center", "footer", "figure", "preformatted", 
        "list", "license", "licenselist", "box", "references", "articlefoot",
        "attribution", "img_attribution", "booktitle", "booksubtitle",
        "toc_group", "toc_chapter", "toc_article"
    ]

    for mode in modes:
        style = text_style(mode=mode)
        assert style.name == f"text_style_{mode}_indent_0_table_0_size_normal"

        # Test specific attributes for each mode
        if mode == "blockquote":
            assert style.rightIndent == PARA_LEFT_INDENT

        if mode in ["footer", "figure", "center"]:
            assert style.alignment == TA_CENTER

        if mode in ["references", "articlefoot", "source", "preformatted", "list", "attribution", "img_attribution"]:
            assert style.alignment == TA_LEFT

        if mode in ["attribution", "img_attribution"]:
            assert style.fontSize == 6
            assert style.leading == 8

        if mode in ["box", "source", "preformatted"]:
            assert style.backColor == "#eeeeee"
            assert style.borderPadding == 3

        if mode in ["source", "preformatted"]:
            assert style.fontName == MONO_FONT
            assert style.flowable is False

        if mode in ["list", "references"]:
            assert style.spaceBefore == 0

        if mode == "booktitle":
            assert style.fontSize == 36
            assert style.leading == 40
            assert style.fontName == SANS_FONT

        if mode == "booksubtitle":
            assert style.fontSize == 24
            assert style.leading == 30
            assert style.fontName == SANS_FONT

        if mode == "license" or mode == "licenselist":
            assert style.fontSize == 5
            assert style.leading == 1

        if mode == "toc_group":
            assert style.fontSize == 18
            assert style.leading == 22

        if mode == "toc_chapter":
            assert style.fontSize == 14
            assert style.leading == 18

        if mode == "toc_article":
            assert style.fontSize == 10
            assert style.leading == 12
            assert style.leftIndent == PARA_LEFT_INDENT


def test_text_style_indent_levels():
    """Test that text_style handles different indent levels correctly."""
    for indent_lvl in range(5):
        style = text_style(indent_lvl=indent_lvl)
        assert style.leftIndent == indent_lvl * PARA_LEFT_INDENT

        # Test list mode with indent levels
        list_style = text_style(mode="list", indent_lvl=indent_lvl)
        assert list_style.bulletIndent == LIST_LEFT_INDENT * max(0, indent_lvl - 1)
        assert list_style.leftIndent == LIST_LEFT_INDENT * indent_lvl


def test_text_style_in_table():
    """Test that text_style handles in_table parameter correctly."""
    # Test outside table
    style = text_style(in_table=0)
    assert style.fontSize != SMALL_FONT_SIZE

    # Test inside table
    table_style = text_style(in_table=1)
    assert table_style.fontSize == SMALL_FONT_SIZE
    assert table_style.bulletFontSize == SMALL_FONT_SIZE
    assert table_style.leading == SMALL_LEADING

    table_style = text_style(in_table=1, relsize="big")
    assert table_style.fontSize == SMALL_FONT_SIZE + 1


def test_text_style_relsize():
    """Test that text_style handles relsize parameter correctly."""
    # Test normal size
    style = text_style(relsize="normal")
    normal_size = style.fontSize

    # Test small size
    small_style = text_style(relsize="small")
    assert small_style.fontSize <= normal_size

    # Test big size
    big_style = text_style(relsize="big")
    assert big_style.fontSize >= normal_size

    # Test small size in preformatted mode
    preformatted_small = text_style(mode="preformatted", relsize="small")
    assert preformatted_small.fontSize == SMALL_FONT_SIZE - 1


def test_text_style_text_align():
    """Test that text_style handles text_align parameter correctly."""
    # Test default alignment (justified)
    style = text_style()
    assert style.alignment == TA_JUSTIFY

    # Test right alignment
    right_style = text_style(text_align="right")
    assert right_style.alignment == TA_RIGHT

    # Test center alignment
    center_style = text_style(text_align="center")
    assert center_style.alignment == TA_CENTER

    style = text_style(text_align="left")
    assert style.alignment == TA_LEFT


def test_base_style():
    """Test that BaseStyle initializes with correct default values."""
    style = BaseStyle(name="test_base_style")

    # Test default values
    assert style.name == "test_base_style"
    assert style.fontName == SERIF_FONT
    assert style.fontSize == FONT_SIZE
    assert style.leading == LEADING
    assert style.autoLeading == "max"
    assert style.leftIndent == 0
    assert style.rightIndent == 0
    assert style.firstLineIndent == 0
    assert style.alignment == TEXT_ALIGN
    assert style.spaceBefore == 3
    assert style.spaceAfter == 0
    assert style.bulletFontName == SERIF_FONT
    assert style.bulletFontSize == FONT_SIZE
    assert style.bulletIndent == 0
    assert style.textColor == colors.black
    assert style.backColor is None
    assert style.wordWrap is None
    assert style.textTransform is None
    assert style.strikeWidth == 1
    assert style.underlineWidth == 1


def test_base_heading_style():
    """Test that BaseHeadingStyle initializes with correct default values."""
    style = BaseHeadingStyle(name="test_base_heading_style")

    # Test default values
    assert style.name == "test_base_heading_style"
    assert style.fontName == SERIF_FONT
    assert style.fontSize == BIG_FONT_SIZE
    assert style.leading == LEADING
    assert style.autoLeading == "max"
    assert style.leftIndent == 0
    assert style.rightIndent == 0
    assert style.firstLineIndent == 0
    assert style.alignment == TA_LEFT
    assert style.spaceBefore == 12
    assert style.spaceAfter == 6
    assert style.bulletFontName == SERIF_FONT
    assert style.bulletFontSize == BIG_FONT_SIZE
    assert style.bulletIndent == 0
    assert style.textColor == colors.black
    assert style.backcolor is None
    assert style.wordWrap is None
    assert style.textTransform is None


def test_heading_style_default_parameters():
    """Test that heading_style returns a style with default parameters."""
    style = heading_style()

    assert style.name == "heading_style_chapter_1"
    assert style.fontName == SERIF_FONT
    assert style.prevent_post_pagebreak is True


def test_heading_style_modes():
    """Test that heading_style handles different modes correctly."""
    # Test each mode and verify key attributes
    modes = ["chapter", "article", "section", "tablecaption", "license"]

    for mode in modes:
        style = heading_style(mode=mode)
        assert style.name == f"heading_style_{mode}_1"

        # Test specific attributes for each mode
        if mode == "chapter":
            assert style.fontSize == 26
            assert style.leading == 30
            assert style.alignment == TA_CENTER

        elif mode == "article":
            assert style.fontSize == 22
            assert style.leading == 26
            assert style.spaceBefore == 20
            assert style.spaceAfter == 2

        elif mode == "section":
            assert style.fontSize == 18
            assert style.spaceBefore <= 20

        elif mode == "tablecaption":
            assert style.fontSize == 12
            assert style.leading == 16
            assert style.alignment == TA_CENTER
            assert style.flowable is False
            assert style.spaceAfter == 0

        elif mode == "license":
            assert style.fontSize == 7
            assert style.leading == 5
            assert style.spaceAfter == 0
            assert style.spaceBefore == 2


def test_heading_style_levels():
    """Test that heading_style handles different levels correctly."""
    # Test section headings with different levels
    for lvl in range(1, 6):
        style = heading_style(mode="section", lvl=lvl)
        assert style.name == f"heading_style_section_{lvl}"

        # Section font size decreases with level
        assert style.fontSize == 18 - (lvl - 1) * 2

        # Flowable should be True for levels > 1
        if lvl > 1:
            assert hasattr(style, 'flowable') and style.flowable is True


def test_heading_style_text_align():
    """Test that heading_style handles text_align parameter correctly."""
    # Test default alignment
    style = heading_style(mode="section")
    assert style.alignment == TA_LEFT

    # Test right alignment
    right_style = heading_style(mode="section", text_align="right")
    assert right_style.alignment == TA_RIGHT

    # Test center alignment
    center_style = heading_style(mode="section", text_align="center")
    assert center_style.alignment == TA_CENTER

    # Test left alignment
    left_style = heading_style(mode="section", text_align="left")
    assert left_style.alignment == TA_LEFT

    # Test justify alignment
    justify_style = heading_style(mode="section", text_align="justify")
    assert justify_style.alignment == TA_JUSTIFY


def test_rtl_text_style():
    """Test that text_style handles RTL (Right-to-Left) text correctly."""
    # Save original WORD_WRAP value
    original_word_wrap = pdfstyles.WORD_WRAP

    try:
        # Set WORD_WRAP to RTL
        pdfstyles.WORD_WRAP = "RTL"

        # Test normal paragraph with RTL
        style = text_style(mode="p")
        assert style.wordWrap == "RTL"
        assert style.alignment == TA_RIGHT  # Left alignment becomes right in RTL

        # Test that right indent and left indent are swapped
        style = text_style(mode="blockquote")
        assert style.leftIndent == pdfstyles.PARA_RIGHT_INDENT  # Right indent becomes left in RTL

        # Test that right alignment becomes left in RTL
        style = text_style(text_align="right")
        assert style.alignment == TA_LEFT  # Right alignment becomes left in RTL

        # Test that preformatted mode is not affected by RTL
        style = text_style(mode="preformatted")
        assert style.wordWrap is None  # preformatted should not have wordWrap set
    finally:
        # Restore original WORD_WRAP value
        pdfstyles.WORD_WRAP = original_word_wrap


def test_rtl_heading_style():
    """Test that heading_style handles RTL (Right-to-Left) text correctly."""
    # Save original WORD_WRAP value
    original_word_wrap = pdfstyles.WORD_WRAP

    try:
        # Set WORD_WRAP to RTL
        pdfstyles.WORD_WRAP = "RTL"

        # Test default heading with RTL
        style = heading_style()
        assert style.wordWrap == "RTL"
        assert style.alignment == TA_RIGHT  # Default alignment becomes right in RTL

        # Test that explicit text alignment overrides RTL default
        style = heading_style(text_align="center")
        assert style.alignment == TA_CENTER
    finally:
        # Restore original WORD_WRAP value
        pdfstyles.WORD_WRAP = original_word_wrap


def test_translation_function():
    """Test that the _ function works correctly for translation."""
    # Import the _ function directly
    from mwlib.writers.rl.pdfstyles import _

    # Test that _ returns the input text (since no translation is set up)
    assert _("test") == "test"
    assert _("Hello World") == "Hello World"


def test_custom_config_import():
    """Test the custom config import mechanism."""
    # This is a bit tricky to test directly since it depends on an external file.
    # We'll just verify that the code doesn't raise exceptions when the import fails.
    import mwlib.writers.rl.pdfstyles as pdfstyles

    # The module should have loaded successfully even without customconfig.py
    assert hasattr(pdfstyles, 'PRINT_WIDTH')
    assert hasattr(pdfstyles, 'PRINT_HEIGHT')
