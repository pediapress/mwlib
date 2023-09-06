#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.rst for additional licensing information.


import contextlib
import math

from six.moves import range

from .advtree import URL, Cell, ImageLink, Link, Math, NamedURL, Reference, Text


def getNodeHeight(node, params):
    lineHeight = params['lineHeight']
    charsPerLine = params['charsPerLine']
    paragraphMargin = params['paragraphMargin']
    imgHeight = params['imgHeight']

    height = 0
    nonFollowNodes = [Reference, NamedURL]
    amap = {Text: "caption", Link: "target", URL: "caption", Math: "caption", NamedURL: 'caption'}
    access = amap.get(node.__class__, "")
    if access:
        txt = '' if node.__class__ == Link and node.children else getattr(node, access)
        if txt:
            # 40 chars per line --> number of lines --> 20pt height per line
            addHeight = math.ceil(len(txt) / charsPerLine) * lineHeight
            if node.is_block_node:
                addHeight += paragraphMargin
            else:
                # for inline nodes we reduce the height guess. below that is compensated
                # for blocknode-heights w/o text
                addHeight = addHeight / 2
            height += addHeight
    elif node.__class__ == ImageLink:
        if node.isInline():  # image heights are just wild guesses. in case of normal image, we assume 5 lines of text in height
            height += 0  # lineHeight
        else:
            height += lineHeight * imgHeight
    elif node.is_block_node:  # compensation for e.g. listItems which contain text.
        height += 0.5 * lineHeight

    for n in node.children[:]:
        if n.__class__ not in nonFollowNodes:
            height += getNodeHeight(n, params)
    return height


def splitRow(row, params):
    maxCellHeight = params['maxCellHeight']
    newrows = []
    cols = [[] for i in range(len(row.children))]
    for (colindex, cell) in enumerate(row.children):
        cellHeight = 0
        items = []
        for item in cell.children:
            cellHeight += getNodeHeight(item, params)
            if not items or cellHeight < maxCellHeight:
                items.append(item)
            else:
                cols[colindex].append(items)
                items = [item]
                cellHeight = 0
        if items:
            cols[colindex].append(items)

    maxNewRows = max([len(col) for col in cols])

    for rowindex in range(maxNewRows):
        newrow = row.copy()
        newrow.children = []
        for colindex in range(len(cols)):
            try:
                cellchildren = cols[colindex][rowindex]
            except IndexError:
                cellchildren = []  # fixme maybe some better empty child
            cell = Cell()
            with contextlib.suppress(BaseException):
                cell.vlist = row.children[colindex].vlist

            for c in cellchildren:
                cell.appendChild(c)
            newrow.append_child(cell)
            newrow.suppress_bottom_border = True
        newrows.append(newrow)

    return newrows
