
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib.refine import core
from mwlib.parser import nodes as N
from mwlib.utoken import token as T
from mwlib import nshandling


tok2class = {
    T.t_complex_table : N.Table,
    T.t_complex_caption: N.Caption,
    T.t_complex_table_row: N.Row,
    T.t_complex_table_cell: N.Cell,
    T.t_complex_link: N.Link,
    T.t_complex_section: N.Section,
    T.t_complex_article: N.Article,
    T.t_complex_tag: N.TagNode,
    T.t_complex_named_url: N.NamedURL,
    T.t_complex_style: N.Style,
    T.t_complex_node: N.Node,
    T.t_complex_line: N.Node,
    T.t_http_url: N.URL,
    T.t_complex_preformatted: N.PreFormatted,
    }


        

def _change_classes(node):
    if isinstance(node, T):
        if node.type==T.t_complex_table and node.children:

            node.children = [x for x in node.children if x.type in (T.t_complex_table_row, T.t_complex_caption) or x.tagname == "caption"]
        elif node.type==T.t_complex_table_row and node.children:
            node.children = [x for x in node.children if x.type==T.t_complex_table_cell]

        if node.type==T.t_http_url:
            node.caption = node.text
            node.children=[]

        if node.type==T.t_complex_compat:
            node.__class__ = node.compatnode.__class__
            node.__dict__ = node.compatnode.__dict__
            return
        
        if node.type==T.t_magicword:
            node.caption = u""
            node.children = []
            node.__class__=N.Text
            return

        if node.type==T.t_html_tag_end:
            node.caption = u""
            node.children = []
            node.__class__=N.Text
            return
            
        klass = tok2class.get(node.type, N.Text)
        
            
        if klass==N.Text:
            node.caption=node.text or u""
            assert not node.children, "%r has children" % (node,)
            
        node.__class__=klass
        
        if node.type==T.t_hrule or (node.type in (T.t_html_tag, T.t_html_tag_end) and node.rawtagname=='hr'):
            node.__class__=N.TagNode
            node.caption = "hr"
            
        if node.rawtagname=='br':
            node.__class__=N.TagNode
            node.caption="br"

        if node.type==T.t_complex_style:
            node.__class__=N.Style
            
        if node.__class__==N.Text:
            node.caption=node.text or u""
            assert not node.children, "%r has children" % (node,)
            
            
        if node.children is None:
            node.children = []
            
        if node.vlist is None:
            node.vlist = {}
        if node.type==T.t_complex_tag:
            node.caption = node.tagname
            if node.tagname=='p':
                node.__class__=N.Paragraph
            elif node.tagname=='caption':
                node.__class__=N.Caption
            elif node.tagname=='ref':
                pass
                #node.__class__=N.Ref
            elif node.tagname=='ul':
                node.__class__=N.ItemList
            elif node.tagname=='ol':
                node.__class__=N.ItemList
                node.numbered=True
            elif node.tagname=='li':
                node.__class__=N.Item
            elif node.tagname=="timeline":
                node.__class__=N.Timeline
                node.caption = node.timeline
            elif node.tagname=="imagemap":
                if node.imagemap.imagelink:
                    _change_classes(node.imagemap.imagelink)
            elif node.tagname=="math":
                node.__class__=N.Math
                node.caption = node.math
            elif node.tagname=='b':
                node.__class__=N.Style
                node.caption = "'''"
            elif node.tagname=='pre':
                node.__class__=N.PreFormatted
            elif node.tagname=='blockquote':
                node.__class__=N.Style
                node.caption = "-"
            elif node.tagname=="strong":
                node.__class__=N.Style
                node.caption = "'''"
            elif node.tagname=="cite":
                node.__class__=N.Style
                node.caption="cite"
            elif node.tagname=="big":
                node.__class__=N.Style
                node.caption="big"
            elif node.tagname=="small":
                node.__class__=N.Style
                node.caption="small"
            elif node.tagname=="s":
                node.__class__=N.Style
                node.caption="s"                
            elif node.tagname=="var":
                node.__class__=N.Style
                node.caption="var"
            elif node.tagname=="i":
                node.__class__=N.Style
                node.caption="''"
            elif node.tagname=="em":
                node.__class__=N.Style
                node.caption="''"
            elif node.tagname=="sup":
                node.__class__=N.Style
                node.caption="sup"
            elif node.tagname=="sub":
                node.__class__=N.Style
                node.caption="sub"
            elif node.tagname=="u":
                node.__class__=N.Style
                node.caption=="u"
                
        if node.__class__==N.Link:
            ns = node.ns
            
            if node.colon:
                ns = nshandling.NS_SPECIAL
                
            if ns==nshandling.NS_IMAGE:
                node.__class__ = N.ImageLink
            elif ns==nshandling.NS_MAIN:
                node.__class__ = N.ArticleLink
            elif ns==nshandling.NS_CATEGORY:
                node.__class__ = N.CategoryLink
            elif ns is not None:
                node.__class__ = N.NamespaceLink
            elif node.langlink:
                node.__class__ = N.LangLink
                node.namespace = node.target.split(":", 1)[0]
            elif node.interwiki:
                node.__class__ = N.InterwikiLink
                node.namespace = node.interwiki

            ns, partial, full = node.nshandler.splitname(node.target)
            if node.namespace is None:
                node.namespace = node.ns
            
                
            
        node = node.children
        
    if node:
        for x in node:
            _change_classes(x)

    
    
def parse_txt(raw, **kwargs):
    sub = core.parse_txt(raw, **kwargs)
    article = T(type=T.t_complex_article, start=0, len=0, children=sub)
    _change_classes(article)
    return article
