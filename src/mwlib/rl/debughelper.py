#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from reportlab.platypus.flowables import KeepTogether
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.tables import Table

from .customflowables import Figure, FiguresAndParagraphs, SmartKeepTogether


def showParseTree(out, node, indent=0):
    print("    " * indent, repr(node), file=out)
    for x in node.children:
        showParseTree(out, x, indent + 1)


def dumpText(obj):
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


def dumpFiguresAndParagraphs(fp):
    print("=== FiguresAndParagraphs ===")
    print("  ::", end=" ")
    for f in fp.fs:
        print(f.imgPath[f.imgPath.rfind("/"):], end=" ")
    print()
    print("num paras:", len(fp.ps))
    for p in fp.ps:
        dumpText(p)
    print("===/FIG PAR")


def dumpKeepTogether(kt):
    print("=== KeepTogether ===")
    for f in kt._content:
        if isinstance(f, FiguresAndParagraphs):
            dumpFiguresAndParagraphs(f)
        else:
            dumpText(f)
    print("===/KEEP")


def dumpSmartKeepTogether(kt):
    print("=== SmartKeepTogether ===")
    for f in kt._content:
        if isinstance(f, FiguresAndParagraphs):
            dumpFiguresAndParagraphs(f)
        else:
            dumpText(f)
    print("===/SmartKeep")


def dumpTable(table):
    print("=== Table ===")
    for row in table._cellvalues:
        for cell in row:
            for item in cell:
                dumpText(item)
                print("-" * 20, "</item>")
            print("-" * 30, "</cell>")
        print("-" * 40, "</row>")
    print("===/TABLE")


def dumpTableData(tabledata):
    print("=== Table ===")
    for row in tabledata:
        for cell in row:
            print(cell.__class__.__name__)
            if cell.__class__ == dict:
                cell = cell["content"]
            for item in cell:
                dumpText(item)
                print("-" * 20, "</item>")
            print("-" * 30, "</cell>")
        print("-" * 40, "</row>")
    print("===/TABLE")


def dumpElements(elements):
    for e in elements:
        if isinstance(e, FiguresAndParagraphs):
            dumpFiguresAndParagraphs(e)
        elif isinstance(e, KeepTogether):
            dumpKeepTogether(e)
        elif isinstance(e, SmartKeepTogether):
            dumpSmartKeepTogether(e)
        elif isinstance(e, Table):
            dumpTable(e)
        else:
            dumpText(e)


def _dt(self, data):
    # helper for the col/rowspan code
    for (i, row) in enumerate(data):
        print("--- ROW ", i)
        for (j, cell) in enumerate(row):
            colspan = cell.get("colspan", 0)
            rowspan = cell.get("rowspan", 0)
            inserted = cell.get("inserted", "")
            print("- Cell ", j, "rs", rowspan, "cs", colspan, inserted)
