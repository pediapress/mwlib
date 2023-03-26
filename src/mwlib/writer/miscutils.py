# Copyright (c) 2007-2023 PediaPress GmbH
# See README.rst for additional licensing information.
from mwlib import advtree


def has_infobox_attrs(node: advtree.Node) -> bool:
    infobox_class_ids = ["infobox", "taxobox"]
    if node.has_class_id(infobox_class_ids):
        return True
    if node.attributes.get("summary", "").lower() in infobox_class_ids:
        return True
    return False


def text_in_node(node: advtree.Node) -> int:
    amap = {
        advtree.Text: "caption",
        advtree.Link: "target",
        advtree.URL: "caption",
        advtree.Math: "caption",
        advtree.ImageLink: "caption",
    }
    access = amap.get(node.__class__, "")
    if access:
        txt = getattr(node, access)
        if txt:
            return len(txt)
        else:
            return 0
    else:
        return 0


def text_before_infobox(
    node: advtree.Node, infobox: advtree.Node, txt_list: list[tuple[int, bool]] = None
) -> int:
    if not txt_list:
        txt_list = []
    txt_list.append((text_in_node(node), node == infobox))
    for c in node:
        text_before_infobox(c, infobox, txt_list)
    sum_txt = 0
    for len_txt, is_infobox in txt_list:
        sum_txt += len_txt
        if is_infobox:
            return sum_txt
    return sum_txt


def article_starts_with_infobox(
    article_node: advtree.Article, max_text_until_infobox: int = 0
) -> bool:
    assert (
        article_node.__class__ == advtree.Article
    ), "article_starts_with_infobox needs to be called with Article node"
    infobox = None
    for table in article_node.get_child_nodes_by_class(advtree.Table):
        if has_infobox_attrs(table):
            infobox = table
    if not infobox:
        return False
    return text_before_infobox(article_node, infobox, []) <= max_text_until_infobox


def article_starts_with_table(
    article_node: advtree.Article, max_text_until_infobox: int = 0
) -> bool:
    assert (
        article_node.__class__ == advtree.Article
    ), "article_starts_with_table needs to be called with Article node"
    tables = article_node.get_child_nodes_by_class(advtree.Table)
    if not tables:
        return False
    return text_before_infobox(article_node, tables[0], []) <= max_text_until_infobox
