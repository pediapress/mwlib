#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import logging
import math

from reportlab.lib import colors

from mwlib.parser.nodes import Cell, Row, Table, Text
from mwlib.rendering import styleutils
from mwlib.writers.rl import pdfstyles

from ...parser import advtree
from .customflowables import Figure

log = logging.getLogger("rlwriter")


def scale_images(data):
    for row in data:
        for cell in row:
            for i, element in enumerate(cell):
                if isinstance(element, Figure):  # scale image to half size
                    cell[i] = Figure(
                        imgFile=element.img_path,
                        captionTxt=element.captionTxt,
                        captionStyle=element.cs,
                        imgWidth=element.imgWidth / 2.0,
                        imgHeight=element.imgHeight / 2.0,
                        margin=element.margin,
                        padding=element.padding,
                        align=element.align,
                    )


def get_remaining_space(avail_width, summedwidths, minwidths, recursion_depth, data, table, nesting_level):
    remaining_space = avail_width - sum(summedwidths)
    if remaining_space < 0:
        remaining_space = avail_width - sum(minwidths)
        if remaining_space < 0:
            if recursion_depth == 0:
                scale_images(data)
                return get_col_widths(
                    data, table=table,
                    recursion_depth=1, nesting_level=nesting_level
                )
            else:
                return None
        else:
            _widths = minwidths
    else:
        _widths = summedwidths
    return _widths, remaining_space


def calculate_table_cell_widths_and_breaks(table, avail_width, cell, i, j, minwidths, maxbreaks, summedwidths):
    cellwidth = 0
    try:
        colspan = getattr(table.children[i].children[j], "colspan", 1)
    except IndexError:  # caused by empty row b/c of rowspanning
        colspan = 1
    for element in cell:
        minw, minh = element.wrap(0, pdfstyles.PRINT_HEIGHT)
        _, maxh = element.wrap(avail_width, pdfstyles.PRINT_HEIGHT)
        minw += 6  # FIXME +6 is the cell padding we are using
        cellwidth += minw
        rows = (
            minh / maxh - 0.5 if maxh > 0 else 0
        )  # approx. #linebreaks - smooted out
        if colspan > 1:
            for offset in range(colspan):
                minwidths[j + offset] = max(
                    minw / colspan, minwidths[j + offset]
                )
                maxbreaks[j + offset] = max(
                    rows / colspan, maxbreaks[j + offset]
                )
        else:
            minwidths[j] = max(minw, minwidths[j])
            maxbreaks[j] = max(rows, maxbreaks[j])
    summedwidths[j] = max(cellwidth, summedwidths[j])


def get_col_widths(data, table=None, recursion_depth=0, nesting_level=1):
    """
    the widths for the individual columns are calculated.
    if the horizontal size exceeds the pagewidth
    the fontsize is reduced
    """

    if nesting_level > 1:
        scale_images(data)

    if not data:
        return None

    avail_width = pdfstyles.print_width - 12  # twice the total cell padding
    minwidths = [0 for x in range(len(data[0]))]
    summedwidths = [0 for x in range(len(data[0]))]
    maxbreaks = [0 for x in range(len(data[0]))]
    for i, row in enumerate(data):
        for j, cell in enumerate(row):
            calculate_table_cell_widths_and_breaks(
                table, avail_width, cell, i, j, minwidths, maxbreaks, summedwidths
            )

    parent_cells = table.get_parent_nodes_by_class(Cell)
    parent_tables = table.get_parent_nodes_by_class(Table)
    # nested tables in colspanned cell are expanded to full page width
    if (
        nesting_level == 2
        and parent_cells
        and parent_tables
        and parent_cells[0].colspan == parent_tables[0].num_cols
    ):
        avail_width -= 8
    elif nesting_level > 1:
        return minwidths
    _widths, remaining_space = get_remaining_space(
        avail_width, summedwidths, minwidths, recursion_depth, data, table, nesting_level
    )

    totalbreaks = sum(maxbreaks)
    if totalbreaks == 0:
        return minwidths
    else:
        widths = [
            _widths[col] + remaining_space * (breaks / totalbreaks)
            for (col, breaks) in enumerate(maxbreaks)
        ]
        return widths


def get_cell_node_types(cell):
    cell_node_types = []
    for item in cell.children:
        if not item.is_block_node:
            cell_node_types.append(Text)
        else:
            cell_node_types.append(item.__class__)
    return cell_node_types


def get_cell_text_len(cell):
    cell_text_len = 0
    for item in cell.children:
        cell_text_len += len(item.get_all_display_text())
    return cell_text_len


def get_row_node_info(row):
    row_node_info = []
    for cell in row:
        if cell.children:
            cell_node_types = get_cell_node_types(cell)
            cell_text_len = get_cell_text_len(cell)
            row_node_info.append((cell_node_types, cell_text_len))
    return row_node_info


def get_content_type(table):
    node_info = []
    for row in table.children:
        row_node_info = get_row_node_info(row)
        if row_node_info:
            node_info.append(row_node_info)
    return node_info


def custom_calc_widths(table, avail_width):
    from mwlib.rendering.styleutils import scale_length

    first_row = None
    for child in table.children:
        if isinstance(child, Row):
            first_row = child
            break
    if not first_row:
        return None
    col_widths = []
    for cell in first_row.children:
        width = scale_length(
            getattr(cell, "vlist", {}).get("style", {}).get("width", "")
        )
        col_widths.append(width)
    if any(not isinstance(w, float) for w in col_widths):
        return None
    sum_col_widths = sum(col_widths)
    total_needed_width = min(avail_width, sum_col_widths)
    col_widths = [w * total_needed_width / sum_col_widths for w in col_widths]
    return col_widths


def optimize_widths(min_widths, max_widths, avail_width,
                    stretch=False, table=None):
    if pdfstyles.TABLE_WIDTH_FROM_MARKUP:
        col_widths = custom_calc_widths(table, avail_width)
        if col_widths is not None:
            return col_widths
    remaining_space = avail_width - sum(min_widths)

    if stretch and sum(max_widths) < avail_width:
        total_current = sum(max_widths)
        if total_current == 0:
            return max_widths
        remaining = avail_width - total_current
        return [w + w / total_current * remaining for w in max_widths]
    else:
        total_delta = sum(
            [max_widths[i] - min_widths[i] for i in range(len(min_widths))]
        )

    # prevent remaining_space to get negative. -5 compensates for table margins
    remaining_space = max(-5, remaining_space)
    if total_delta < 0.1 or sum(max_widths) < avail_width:
        max_widths = [w + 0.01 for w in max_widths]
        return max_widths
    col_widths = []
    for i in range(len(min_widths)):
        col_widths.append(
            min_widths[i]
            + remaining_space * (max_widths[i] - min_widths[i]) / total_delta
        )
    return col_widths


def get_empty_cell(color, colspan=1, rowspan=1):
    empty_cell = advtree.Cell()
    empty_cell.color = color
    empty_cell.attributes["colspan"] = max(1, colspan)
    empty_cell.attributes["rowspan"] = max(1, rowspan)
    return empty_cell


def _add_styles_to_cell(styles, col_idx, row_idx, span_range, iteration, cell):
    styles.append(
        (
            "SPAN",
            (col_idx, row_idx + span_range * iteration),
            (
                col_idx + cell.colspan - 1,
                row_idx + (iteration + 1) * span_range - 1,
            ),
        )
    )
    styles.append(
        (
            "LINEBELOW",
            (col_idx,
             row_idx + (iteration + 1) * span_range - 1),
            (
                col_idx + cell.colspan - 1,
                row_idx + (iteration + 1) * span_range - 1,
            ),
            0.25,
            colors.white,
        )
    )


def add_styles_to_row(cell, row_idx, col_idx, styles, _approx_cols):
    # allow splitting of cells if rowspan exceeds this value
    # max_row_span = 15 for 4 cols, and 6 for
    # 10 cols - empiric value
    max_row_span = 50 / _approx_cols
    if cell.rowspan <= max_row_span:
        styles.append(
            (
                "SPAN",
                (col_idx, row_idx),
                (
                    col_idx + cell.colspan - 1,
                    row_idx + cell.rowspan - 1,
                ),
            )
        )
    else:
        num_splits = int(math.ceil(cell.rowspan / max_row_span))
        span_range = int(math.floor(cell.rowspan / num_splits))
        for split_index in range(num_splits - 1):
            _add_styles_to_cell(
                styles, col_idx, row_idx, span_range, split_index, cell
            )
        styles.append(
            (
                "SPAN",
                (col_idx, row_idx + span_range * (num_splits - 1)),
                (
                    col_idx + cell.colspan - 1,
                    row_idx + cell.rowspan - 1,
                ),
            )
        )


def check_spans_in_row(row, row_idx, col_idx, cell, table, styles, _approx_cols):
    col_idx = 0
    for cell in row.children:
        if cell.rowspan > 1:
            emptycell = get_empty_cell(None, cell.colspan, cell.rowspan - 1)
            last_col_idx = len(table.children[row_idx + 1].children) - 1
            if col_idx > last_col_idx:
                emptycell.move_to(table.children[row_idx + 1].children[last_col_idx])
            else:
                emptycell.move_to(
                    table.children[row_idx + 1].children[col_idx], prefix=True
                )
            if not getattr(cell, "rowspanned", False):
                add_styles_to_row(cell, row_idx, col_idx, styles, _approx_cols)
            emptycell.rowspanned = True
            if cell.colspan > 1:
                emptycell.colspanned = True
        elif cell.colspan > 1:
            styles.append(
                ("SPAN", (col_idx, row_idx),
                 (col_idx + cell.colspan - 1, row_idx))
            )
        col_idx += 1


def check_spans(table):
    if getattr(table, "checked_spans", False):
        return
    styles = []
    num_rows = len(table.children)
    _approx_cols = 1
    for row_idx, row in enumerate(table.children):
        col_idx = 0
        _approx_cols = max(_approx_cols, len(row.children))
        for cell in row.children:
            if cell.colspan > 1:
                emptycell = get_empty_cell(None, cell.colspan - 1, cell.rowspan)
                emptycell.move_to(cell)  # move behind orignal cell
                emptycell.colspanned = True
            if row_idx + cell.rowspan > num_rows:  # fix broken rowspans
                cell.attributes["rowspan"] = num_rows - row_idx
            col_idx += 1

    for row_idx, row in enumerate(table.children):
        check_spans_in_row(row, row_idx, col_idx, cell, table, styles, _approx_cols)

    num_cols = max(len(row.children) for row in table.children)
    for row in table.children:
        while len(row.children) < num_cols:
            row.append_child(get_empty_cell(None, colspan=1, rowspan=1))

    table.checked_spans = True
    table.span_styles = styles


def get_styles(table):
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
            ("LEFTPADDING", (0, 0), (-1, -1), pdfstyles.CELL_PADDING),
            ("RIGHTPADDING", (0, 0), (-1, -1), pdfstyles.CELL_PADDING),
        ]
    )
    for row_idx, row in enumerate(table):
        for col_idx, cell in enumerate(row):
            if getattr(cell, "compact", False):
                styles.append(("TOPPADDING", (col_idx, row_idx),
                               (col_idx, row_idx), 2))
                styles.append(
                    ("BOTTOMPADDING", (col_idx, row_idx),
                     (col_idx, row_idx), 0)
                )
    return styles


def valign_styles(table):
    styles = []
    for row_idx, row in enumerate(table):
        for col_idx, cell in enumerate(row):
            valign = styleutils.get_vertical_alignment(cell)
            if valign in ["middle", "bottom"]:
                styles.append(
                    ("VALIGN", (col_idx, row_idx),
                     (col_idx, row_idx), valign.upper())
                )
    return styles


def border_styles(table):
    styles = []

    if styleutils.table_border(table):
        styles.append(("BOX", (0, 0), (-1, -1), 0.25, colors.black))
        for idx, row in enumerate(table):
            if not getattr(row, "suppress_bottom_border", False):
                styles.append(("LINEBELOW",
                               (0, idx), (-1, idx), 0.25, colors.black))
        for col in range(table.num_cols):
            styles.append(("LINEAFTER", (col, 0), (col, -1),
                           0.25, colors.black))
    return styles


def background_styles(table):
    styles = []
    table_bg = styleutils.rgb_bg_color_from_node(table, follow=False)
    if table_bg:
        styles.append(
            (
                "BACKGROUND",
                (0, 0),
                (-1, -1),
                colors.Color(table_bg[0], table_bg[1], table_bg[2]),
            )
        )
    for row_idx, row in enumerate(table.children):
        rgb = styleutils.rgb_bg_color_from_node(row, follow=False)
        if rgb:
            styles.append(
                (
                    "BACKGROUND",
                    (0, row_idx),
                    (-1, row_idx),
                    colors.Color(rgb[0], rgb[1], rgb[2]),
                )
            )
        for col_idx, cell in enumerate(row.children):
            if cell.__class__ != Cell:
                continue
            rgb = styleutils.rgb_bg_color_from_node(cell, follow=False)
            if rgb:
                styles.append(
                    (
                        "BACKGROUND",
                        (col_idx, row_idx),
                        (col_idx + cell.colspan - 1,
                         row_idx + cell.rowspan - 1),
                        colors.Color(rgb[0], rgb[1], rgb[2]),
                    )
                )
    return styles


def flip_dir(table, rtl=False):
    if not rtl or getattr(table, "flipped", False):
        return
    for row in table.children:
        row.children.reverse()
    table.flipped = True
