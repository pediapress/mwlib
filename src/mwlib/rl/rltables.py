#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import math
from builtins import range

from mwlib.parser.nodes import Text, ItemList, Table, Row, Cell
from mwlib import advtree
from mwlib import log
from mwlib.writer import styleutils
from mwlib.rl import pdfstyles
from reportlab.lib import colors

from .customflowables import Figure

# import debughelper

log = log.Log("rlwriter")


def scaleImages(data):
    for row in data:
        for cell in row:
            for (i, e) in enumerate(cell):
                if isinstance(e, Figure):  # scale image to half size
                    cell[i] = Figure(
                        imgFile=e.imgPath,
                        captionTxt=e.captionTxt,
                        captionStyle=e.cs,
                        imgWidth=e.imgWidth / 2.0,
                        imgHeight=e.imgHeight / 2.0,
                        margin=e.margin,
                        padding=e.padding,
                        align=e.align,
                    )


def getColWidths(data, table=None, recursionDepth=0, nestingLevel=1):
    """
    the widths for the individual columns are calculated. if the horizontal size exceeds the pagewidth
    the fontsize is reduced
    """

    if nestingLevel > 1:
        scaleImages(data)

    if not data:
        return None

    availWidth = pdfstyles.print_width - 12  # twice the total cell padding
    minwidths = [0 for x in range(len(data[0]))]
    summedwidths = [0 for x in range(len(data[0]))]
    maxbreaks = [0 for x in range(len(data[0]))]
    for (i, row) in enumerate(data):
        for (j, cell) in enumerate(row):
            cellwidth = 0
            try:
                colspan = getattr(table.children[i].children[j], "colspan", 1)
            except IndexError:  # caused by empty row b/c of rowspanning
                colspan = 1
            for e in cell:
                minw, minh = e.wrap(0, pdfstyles.print_height)
                maxw, maxh = e.wrap(availWidth, pdfstyles.print_height)
                minw += 6  # FIXME +6 is the cell padding we are using
                cellwidth += minw
                if maxh > 0:
                    rows = minh / maxh - 0.5  # approx. #linebreaks - smooted out -
                else:
                    rows = 0
                if colspan > 1:
                    for offset in range(colspan):
                        minwidths[j + offset] = max(minw / colspan, minwidths[j + offset])
                        maxbreaks[j + offset] = max(rows / colspan, maxbreaks[j + offset])
                else:
                    minwidths[j] = max(minw, minwidths[j])
                    maxbreaks[j] = max(rows, maxbreaks[j])
            summedwidths[j] = max(cellwidth, summedwidths[j])

    parent_cells = table.get_parent_nodes_by_class(Cell)
    parent_tables = table.get_parent_nodes_by_class(Table)
    # nested tables in colspanned cell are expanded to full page width
    if (
        nestingLevel == 2
        and parent_cells
        and parent_tables
        and parent_cells[0].colspan == parent_tables[0].numcols
    ):
        availWidth -= 8
    elif nestingLevel > 1:
        return minwidths

    remainingSpace = availWidth - sum(summedwidths)
    if remainingSpace < 0:
        remainingSpace = availWidth - sum(minwidths)
        if remainingSpace < 0:
            if recursionDepth == 0:
                scaleImages(data)
                return getColWidths(data, table=table, recursionDepth=1, nestingLevel=nestingLevel)
            else:
                return None
        else:
            _widths = minwidths
    else:
        _widths = summedwidths

    totalbreaks = sum(maxbreaks)
    if totalbreaks == 0:
        return minwidths
    else:
        widths = [
            _widths[col] + remainingSpace * (breaks / totalbreaks)
            for (col, breaks) in enumerate(maxbreaks)
        ]
        return widths


def splitCellContent(data):
    # FIXME: this is a hotfix for tables which contain extremly large cells which cant be handeled by reportlab
    n_data = []
    splitCellCount = 14  # some arbitrary constant...: if more than 14 items are present in a cell, the cell is split into two cells in two rows
    for row in data:
        maxCellItems = 0
        for cell in row:
            maxCellItems = max(maxCellItems, len(cell))
        if maxCellItems > splitCellCount:
            for splitRun in range(int(math.ceil(maxCellItems / splitCellCount))):
                n_row = []
                for cell in row:
                    if len(cell) > splitRun * splitCellCount:
                        n_row.append(
                            cell[splitRun * splitCellCount : (splitRun + 1) * splitCellCount]
                        )
                    else:
                        n_row.append("")
                n_data.append(n_row)
        else:
            n_data.append(row)
    return n_data


def getContentType(t):
    nodeInfo = []
    for row in t.children:
        rowNodeInfo = []
        for cell in row:
            cellNodeTypes = []
            cellTextLen = 0
            for item in cell.children:
                if (
                    not item.is_block_node
                ):  # any inline node is treated as a regular TextNode for simplicity
                    cellNodeTypes.append(Text)
                else:
                    cellNodeTypes.append(item.__class__)
                cellTextLen += len(item.get_all_display_text())
            if cell.children:
                rowNodeInfo.append((cellNodeTypes, cellTextLen))
        if rowNodeInfo:
            nodeInfo.append(rowNodeInfo)
    return nodeInfo


def reformatTable(t, maxCols):
    nodeInfo = getContentType(t)
    numCols = maxCols
    numRows = len(t.rows)

    onlyTables = len(t.children) > 0  # if table is empty onlyTables and onlyLists are False
    onlyLists = len(t.children) > 0
    if not nodeInfo:
        onlyTables = False
        onlyLists = False
    for row in nodeInfo:
        for cell in row:
            cellNodeTypes, cellTextLen = cell
            if not all(nodetype == Table for nodetype in cellNodeTypes):
                onlyTables = False
            if not all(nodetype == ItemList for nodetype in cellNodeTypes):
                onlyLists = False

    if onlyTables and numCols > 1:
        log.info("got table only table - removing container")
        t = removeContainerTable(t)
    if onlyLists and numCols > 2:
        log.info("got list only table - reducing columns to 2")
        t = reduceCols(t, colnum=2)
    if onlyLists:
        log.info("got list only table - splitting list items")
        t = splitListItems(t)
        pass
    return t


def splitListItems(t):
    nt = t.copy()
    nt.children = []
    for r in t.children:
        nr = Row()
        cols = []
        maxItems = 0
        for cell in r:
            items = []
            for c in cell.children:
                if c.__class__ == ItemList:
                    items.extend(c.children)
            cols.append(items)
            maxItems = max(maxItems, len(items))
        for i in range(maxItems):
            for (j, col) in enumerate(cols):
                try:
                    item = cols[j][i]
                    il = ItemList()
                    il.append_child(item)
                    nc = Cell()
                    nc.append_child(il)
                    nr.append_child(nc)
                except IndexError:
                    nr.append_child(Cell())
            nt.append_child(nr)
            nr = Row()
    return nt


def reduceCols(t, colnum=2):
    nt = t.copy()
    nt.children = []
    for r in t.children:
        nr = Row()
        for c in r:
            nc = c.copy()
            if len(nr.children) == colnum:
                nt.append_child(nr)
                nr = Row()
            nr.append_child(nc)
        if len(nr.children) > 0:
            while len(nr.children) < colnum:
                nr.append_child(Cell())
            nt.append_child(nr)
    return nt


def removeContainerTable(containertable):
    newtables = []
    for row in containertable:
        for cell in row:
            for item in cell:
                if item.__class__ == Table:
                    newtables.append(item)
                else:
                    log.info("unmatched node:", item.__class__)
    return newtables


#############################################


def customCalcWidths(table, avail_width):
    from mwlib.writer.styleutils import scale_length

    first_row = None
    for c in table.children:
        if isinstance(c, Row):
            first_row = c
            break
    if not first_row:
        return None
    col_widths = []
    for cell in first_row.children:
        width = scale_length(getattr(cell, "vlist", {}).get("style", {}).get("width", ""))
        col_widths.append(width)
    if any(not isinstance(w, float) for w in col_widths):
        return None
    sum_col_widths = sum(col_widths)
    total_needed_width = min(avail_width, sum_col_widths)
    col_widths = [w * total_needed_width / sum_col_widths for w in col_widths]
    return col_widths


def optimizeWidths(min_widths, max_widths, avail_width, stretch=False, table=None):
    if pdfstyles.table_widths_from_markup:
        col_widths = customCalcWidths(table, avail_width)
        if col_widths != None:
            return col_widths
    remaining_space = avail_width - sum(min_widths)

    if stretch and sum(max_widths) < avail_width:
        total_current = sum(max_widths)
        if total_current == 0:
            return max_widths
        remaining = avail_width - total_current
        return [w + w / total_current * remaining for w in max_widths]
    else:
        total_delta = sum([max_widths[i] - min_widths[i] for i in range(len(min_widths))])

    # prevent remaining_space to get negative. -5 compensates for table margins
    remaining_space = max(-5, remaining_space)
    if total_delta < 0.1 or sum(max_widths) < avail_width:
        max_widths = [w + 0.01 for w in max_widths]
        return max_widths
    col_widths = []
    for i in range(len(min_widths)):
        col_widths.append(
            min_widths[i] + remaining_space * (max_widths[i] - min_widths[i]) / total_delta
        )
    return col_widths


def getEmptyCell(color, colspan=1, rowspan=1):
    emptyCell = advtree.Cell()
    # emptyCell.append_child(emptyNode)
    emptyCell.color = color
    emptyCell.attributes["colspan"] = max(1, colspan)
    emptyCell.attributes["rowspan"] = max(1, rowspan)
    return emptyCell


def checkSpans(t):
    if getattr(t, "checked_spans", False):
        return
    styles = []
    num_rows = len(t.children)
    _approx_cols = 1
    for row_idx, row in enumerate(t.children):
        col_idx = 0
        _approx_cols = max(_approx_cols, len(row.children))
        for cell in row.children:
            if cell.colspan > 1:
                emptycell = getEmptyCell(None, cell.colspan - 1, cell.rowspan)
                emptycell.move_to(cell)  # move behind orignal cell
                emptycell.colspanned = True
            if row_idx + cell.rowspan > num_rows:  # fix broken rowspans
                cell.attributes["rowspan"] = num_rows - row_idx
            col_idx += 1

    for row_idx, row in enumerate(t.children):
        col_idx = 0
        for cell in row.children:
            if cell.rowspan > 1:
                emptycell = getEmptyCell(None, cell.colspan, cell.rowspan - 1)
                last_col_idx = len(t.children[row_idx + 1].children) - 1
                if col_idx > last_col_idx:
                    emptycell.moveto(t.children[row_idx + 1].children[last_col_idx])
                else:
                    emptycell.moveto(t.children[row_idx + 1].children[col_idx], prefix=True)
                if not getattr(cell, "rowspanned", False):
                    # allow splitting of cells if rowspan exceeds this value
                    # max_row_span = 15 for 4 cols, and 6 for 10 cols - empiric value
                    max_row_span = 50 / _approx_cols
                    if cell.rowspan <= max_row_span:
                        styles.append(
                            (
                                "SPAN",
                                (col_idx, row_idx),
                                (col_idx + cell.colspan - 1, row_idx + cell.rowspan - 1),
                            )
                        )
                    else:
                        num_splits = int(math.ceil(cell.rowspan / max_row_span))
                        span_range = int(math.floor(cell.rowspan / num_splits))
                        for n in range(num_splits - 1):
                            styles.append(
                                (
                                    "SPAN",
                                    (col_idx, row_idx + span_range * n),
                                    (
                                        col_idx + cell.colspan - 1,
                                        row_idx + (n + 1) * span_range - 1,
                                    ),
                                )
                            )
                            styles.append(
                                (
                                    "LINEBELOW",
                                    (col_idx, row_idx + (n + 1) * span_range - 1),
                                    (
                                        col_idx + cell.colspan - 1,
                                        row_idx + (n + 1) * span_range - 1,
                                    ),
                                    0.25,
                                    colors.white,
                                )
                            )
                        styles.append(
                            (
                                "SPAN",
                                (col_idx, row_idx + span_range * (num_splits - 1)),
                                (col_idx + cell.colspan - 1, row_idx + cell.rowspan - 1),
                            )
                        )

                emptycell.rowspanned = True
                if cell.colspan > 1:
                    emptycell.colspanned = True
            elif cell.colspan > 1:
                styles.append(("SPAN", (col_idx, row_idx), (col_idx + cell.colspan - 1, row_idx)))
            col_idx += 1

    numcols = max(len(row.children) for row in t.children)
    for row in t.children:
        while len(row.children) < numcols:
            row.append_child(getEmptyCell(None, colspan=1, rowspan=1))

    t.checked_spans = True
    t.span_styles = styles


def getStyles(table):
    styles = []
    styles.extend(base_styles(table))
    styles.extend(border_styles(table))
    styles.extend(background_styles(table))
    styles.extend(valign_styles(table))
    styles.extend(table.span_styles)
    return styles


def base_styles(table):
    styles = []
    styles.append(("VALIGN", (0, 0), (-1, -1), "TOP"))
    styles.extend(
        [
            ("LEFTPADDING", (0, 0), (-1, -1), pdfstyles.cell_padding),
            ("RIGHTPADDING", (0, 0), (-1, -1), pdfstyles.cell_padding),
        ]
    )
    for row_idx, row in enumerate(table):
        for col_idx, cell in enumerate(row):
            if getattr(cell, "compact", False):
                styles.append(("TOPPADDING", (col_idx, row_idx), (col_idx, row_idx), 2))
                styles.append(("BOTTOMPADDING", (col_idx, row_idx), (col_idx, row_idx), 0))
    return styles


def valign_styles(table):
    styles = []
    for row_idx, row in enumerate(table):
        for col_idx, cell in enumerate(row):
            valign = styleutils.get_vertical_alignment(cell)
            if valign in ["middle", "bottom"]:
                styles.append(("VALIGN", (col_idx, row_idx), (col_idx, row_idx), valign.upper()))
    return styles


def border_styles(table):
    styles = []

    if styleutils.table_border(table):
        styles.append(("BOX", (0, 0), (-1, -1), 0.25, colors.black))
        for idx, row in enumerate(table):
            if not getattr(row, "suppress_bottom_border", False):
                styles.append(("LINEBELOW", (0, idx), (-1, idx), 0.25, colors.black))
        for col in range(table.numcols):
            styles.append(("LINEAFTER", (col, 0), (col, -1), 0.25, colors.black))
    return styles


def background_styles(table):
    styles = []
    table_bg = styleutils.rgb_bg_color_from_node(table, follow=False)
    if table_bg:
        styles.append(
            ("BACKGROUND", (0, 0), (-1, -1), colors.Color(table_bg[0], table_bg[1], table_bg[2]))
        )
    for (row_idx, row) in enumerate(table.children):
        rgb = styleutils.rgb_bg_color_from_node(row, follow=False)
        if rgb:
            styles.append(
                ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.Color(rgb[0], rgb[1], rgb[2]))
            )
        for (col_idx, cell) in enumerate(row.children):
            if cell.__class__ != Cell:
                continue
            rgb = styleutils.rgb_bg_color_from_node(cell, follow=False)
            if rgb:
                styles.append(
                    (
                        "BACKGROUND",
                        (col_idx, row_idx),
                        (col_idx + cell.colspan - 1, row_idx + cell.rowspan - 1),
                        colors.Color(rgb[0], rgb[1], rgb[2]),
                    )
                )
    return styles


def flip_dir(t, rtl=False):
    if not rtl or getattr(t, "flipped", False):
        return
    for row in t.children:
        row.children.reverse()
    t.flipped = True
