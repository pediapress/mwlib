#!/usr/bin/env py.test

# Copyright (c) PediaPress GmbH
# See README.txt for additional licensing information.

import pytest
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT

from mwlib.writers.rl.pdfstyles import (
    LIST_LEFT_INDENT,
    MONO_FONT,
    PARA_LEFT_INDENT,
    SANS_FONT,
    SERIF_FONT,
    SMALL_FONT_SIZE,
    SMALL_LEADING,
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
