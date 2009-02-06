
from mwlib.refine import core
from mwlib.parser import nodes as N
from mwlib.utoken import token as T
from mwlib import namespace


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
        if node.type==T.t_complex_table and node.children:
            node.children = [x for x in node.children if x.type in (T.t_complex_table_row, T.t_complex_caption)]
        elif node.type==T.t_complex_table_row and node.children:
            node.children = [x for x in node.children if x.type==T.t_complex_table_cell]

        node.__class__ = tok2class.get(node.type, N.Text)
        if node.tagname=='br':
            node.__class__=N.TagNode
            
        if node.__class__==N.Text:
            node.caption=node.text
        if node.children is None:
            node.children = []
        else:
            node.children = list(node.children) # advtree can't handle the blist
        if node.vlist is None:
            node.vlist = {}
        if node.type==T.t_complex_tag:
            node.caption = node.tagname
            if node.tagname=='p':
                node.__class__=N.Paragraph
            elif node.tagname=='ref':
                node.__class__=N.Ref
                
        if node.__class__==N.Link:
            if node.ns==namespace.NS_IMAGE:
                node.__class__ = N.ImageLink
            elif node.ns==namespace.NS_MAIN:
                node.__class__ = N.ArticleLink
            elif node.ns==namespace.NS_CATEGORY:
                node.__class__ = N.CategoryLink
            elif node.ns is not None:
                node.__class__ = N.NamespaceLink
                
            
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
