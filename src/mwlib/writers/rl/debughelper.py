#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from reportlab.platypus.flowables import KeepTogether
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.tables import Table

from mwlib.writers.rl.customflowables import Figure, FiguresAndParagraphs, SmartKeepTogether


def show_parse_tree(out, node, indent=0):
    print("    " * indent, repr(node), file=out)
    for child in node.children:
        show_parse_tree(out, child, indent + 1)


def dump_text(obj):
    if isinstance(obj, Paragraph):
        print(
            "P:  --",
            obj.__class__.__name__,
            obj.text,
            obj.style.name,
            "KEEP:",
            getattr(obj, "keepWithNext", False),
        )
    elif isinstance(obj, Figure):
        print("F:  --", obj.__class__.__name__, obj.c.text)
    elif isinstance(obj, str):
        print("S:  --", obj.__class__.__name__, obj)
    else:
        print("U:  --", obj.__class__.__name__)


def dump_figures_and_paragraphs(file_path):
    print("=== FiguresAndParagraphs ===")
    print("  ::", end=" ")
    for figure in file_path.figures:
        print(figure.img_path[figure.img_path.rfind("/"):], end=" ")
    print()
    print("num paras:", len(file_path.paragraphs))
    for paragraph in file_path.paragraphs:
        dump_text(paragraph)
    print("===/FIG PAR")


def dump_keep_together(keep_together):
    print("=== KeepTogether ===")
    for figure in keep_together._content:
        if isinstance(figure, FiguresAndParagraphs):
            dump_figures_and_paragraphs(figure)
        else:
            dump_text(figure)
    print("===/KEEP")


def dump_smart_keep_together(keep_together):
    print("=== SmartKeepTogether ===")
    for figure in keep_together._content:
        if isinstance(figure, FiguresAndParagraphs):
            dump_figures_and_paragraphs(figure)
        else:
            dump_text(figure)
    print("===/SmartKeep")


def dump_table(table):
    print("=== Table ===")
    for row in table._cellvalues:
        for cell in row:
            for item in cell:
                dump_text(item)
                print("-" * 20, "</item>")
            print("-" * 30, "</cell>")
        print("-" * 40, "</row>")
    print("===/TABLE")


def dump_table_data(tabledata):
    print("=== Table ===")
    for row in tabledata:
        for cell in row:
            print(cell.__class__.__name__)
            if isinstance(cell.__class__, dict):
                cell = cell["content"]
            for item in cell:
                dump_text(item)
                print("-" * 20, "</item>")
            print("-" * 30, "</cell>")
        print("-" * 40, "</row>")
    print("===/TABLE")


def dump_elements(elements):
    for element in elements:
        if isinstance(element, FiguresAndParagraphs):
            dump_figures_and_paragraphs(element)
        elif isinstance(element, KeepTogether):
            dump_keep_together(element)
        elif isinstance(element, SmartKeepTogether):
            dump_smart_keep_together(element)
        elif isinstance(element, Table):
            dump_table(element)
        else:
            dump_text(element)
