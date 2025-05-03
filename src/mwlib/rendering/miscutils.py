# Copyright (c) 2007-2023 PediaPress GmbH
# See README.rst for additional licensing information.
from mwlib.parser import URL, advtree
from mwlib.utils.mwlib_exceptions import InvalidArticleStructureError

ARTICLE_ERROR = "{} needs to be called with Article node"


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
        URL: "caption",
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
    node: advtree.Node, infobox: advtree.Node,
    txt_list: list[tuple[int, bool]] = None
) -> int:
    if not txt_list:
        txt_list = []
    txt_list.append((text_in_node(node), node == infobox))
    for child in node:
        text_before_infobox(child, infobox, txt_list)
    sum_txt = 0
    for len_txt, is_infobox in txt_list:
        sum_txt += len_txt
        if is_infobox:
            return sum_txt
    return sum_txt


def get_error_msg(msg: str) -> str:
    return ARTICLE_ERROR.format(msg)


def article_starts_with_infobox(
    article_node: advtree.Article, max_text_until_infobox: int = 0
) -> bool:
    if article_node.__class__ != advtree.Article:
        error_message = get_error_msg("article_starts_with_infobox")
        raise InvalidArticleStructureError(ARTICLE_ERROR.format(error_message))
    infobox = None
    for table in article_node.get_child_nodes_by_class(advtree.Table):
        if has_infobox_attrs(table):
            infobox = table
    if not infobox:
        return False
    text_before = text_before_infobox(article_node, infobox, [])
    return text_before <= max_text_until_infobox


def article_starts_with_table(
    article_node: advtree.Article, max_text_until_infobox: int = 0
) -> bool:
    if article_node.__class__ != advtree.Article:
        error_message = get_error_msg("article_starts_with_table")
        raise InvalidArticleStructureError(error_message)

    tables = article_node.get_child_nodes_by_class(advtree.Table)
    if not tables:
        return False
    text_before = text_before_infobox(article_node, tables[0], [])
    return text_before <= max_text_until_infobox
