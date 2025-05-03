# Copyright (c) 2007-2023 PediaPress GmbH
# See README.rst for additional licensing information.

import sys

import pytest

from mwlib import parser
from mwlib.parser import advtree
from mwlib.parser.dummydb import DummyDB
from mwlib.parser.refine.uparser import parse_string
from mwlib.rendering import styleutils


def get_tree_from_markup(raw):
    tree = parse_string(title="Test", raw=raw, wikidb=DummyDB())
    advtree.build_advanced_tree(tree)
    return tree


def show(tree):
    parser.show(sys.stdout, tree)


def test_get_text_align():
    raw = """
{|
|-
! center
! style="text-align:right;"|right
|- style="text-align:left;"
! left
! style="text-align:right;"|right
|}
    """
    tree = get_tree_from_markup(raw)
    for cell in tree.get_child_nodes_by_class(advtree.Cell):
        txt = cell.get_all_display_text().strip()
        align = styleutils.get_text_alignment(cell)
        assert txt == align, "alignment not correctly parsed"


def test_get_text_align2():
    raw = """
left

<div style="text-align:right;">
right

<div style="text-align:left;">
left

{| class="prettytable"
|-
| left
| style="text-align:right;" | right
|}

{| class="prettytable" style="text-align:right;"
|-
| right
| style="text-align:center;" | center
|}
</div>
</div>"""

    tree = get_tree_from_markup(raw)
    for cell in tree.get_child_nodes_by_class(advtree.Cell):
        txt = cell.get_all_display_text().strip()
        align = styleutils.get_text_alignment(cell)

        if txt != align:
            show(cell)

        assert txt == align, f"alignment not correctly parsed. expected:|{txt}|, got |{align}|"


@pytest.mark.parametrize(
    "rgb_triple, darkness_limit, expected_output",
    [
        ((0.0, 0.0, 0.0), 0.0, (0.0, 0.0, 0.0)),
        ((0.0, 0.0, 0.0), 1.0, (1.0, 1.0, 1.0)),
        ((1.0, 1.0, 1.0), 0.0, (1.0, 1.0, 1.0)),
        ((1.0, 0.0, 0.0), 0.0, (0.3, 0.3, 0.3)),
        ((0.0, 1.0, 0.0), 0.0, (0.59, 0.59, 0.59)),
        ((0.0, 0.0, 1.0), 0.0, (0.11, 0.11, 0.11)),
        ((0.1, 0.5, 0.8), 0.0, (0.413, 0.413, 0.413)),
    ],
)
def test_greyscale_conversion(rgb_triple, darkness_limit, expected_output):
    result = styleutils._rgb_to_greyscale(rgb_triple, darkness_limit)  # pylint: disable=W0212
    for result, expected in zip([*result], [*expected_output], strict=False):
        assert result == pytest.approx(expected, 0.00001)
