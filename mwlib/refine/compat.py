
from mwlib.refine import core
from mwlib.parser import nodes as N
from mwlib.utoken import token as T


tok2class = {
    T.t_complex_table : N.Table,
    T.t_complex_caption: N.Caption,
    T.t_complex_table_row: N.Row,
    T.t_complex_table_cell: N.Cell,
    T.t_complex_link: N.Link,
    T.t_complex_section: N.Section,
    T.t_complex_article: N.Article,
    T.t_complex_tag: N.TagNode,
    }


def _change_classes(node):
    if isinstance(node, T):
        node.__class__ = tok2class.get(node.type, N.Text)
        if node.__class__==N.Text:
            node.caption=node.text
        if node.children is None:
            node.children = []
        if node.type==T.t_complex_tag:
            node.caption = node.tagname
        
        node = node.children
        
    if node:
        for x in node:
            _change_classes(x)

def parse_txt(raw):
    sub = core.parse_txt(raw)
    article = T(type=T.t_complex_article, start=0, len=0, children=sub)
    core.show(article)
    _change_classes(article)
    article.show()
    return article
