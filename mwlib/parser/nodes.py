
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib import utoken

class Node(utoken.token):
    """Base class for all nodes"""
    
    caption = ''

    def __init__(self, caption=''):
        self.children = []
        self.caption = caption

    def __iter__(self):
        for x in self.children:
            yield x

    def __repr__(self):
        try:
            return utoken.token.__repr__(self)
        except:
            return "%s %r: %s children" % (self.__class__.__name__, self.caption, len(self.children))

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and self.caption == other.caption
                and self.children == other.children)

    def __ne__(self, other):
        return not(self==other)

    def allchildren(self): # name is broken, returns self, which is not a child
        yield self 
        for c in self.children:
            for x in c.allchildren():
                yield x        

    def find(self, tp):
        """find instances of type tp in self.allchildren()"""
        return [x for x in self.allchildren() if isinstance(x, tp)]


    def filter(self, fun):
        for x in self.allchildren():
            if fun(x):
                yield x

    def _asText(self, out):
        out.write(self.caption)
        for x in self.children:
            x._asText(out)
        
    def asText(self, ):
        from StringIO import StringIO
        out = StringIO()
        self._asText(out)
        return out.getvalue()
                    
class Math(Node): pass
class Ref(Node): pass
class Item(Node): pass
class ItemList(Node):
    numbered = False

class Style(Node):
    """Describes text styles like italics, bold etc. The type of the style is
    contained in the caption attribute. The styled text is contained in
    children.
    
    The attribute caption can have the following values:
     * "''" for italic text
     * ''' for bold text
     * ":", "::", ... for indented text (number of ":"'s == indentation level)
     * ";" for a definition description term
    """

class Book(Node):
    pass

class Chapter(Node):
    pass
    
class Article(Node):
    url = None
    
class Paragraph(Node):
    pass

class Section(Node):
    """A section heading
    
    The level attribute contains the level of the section heading, i.e.::
    
       = test =    level=1
       == test ==  level=2
       etc.
    
    The first element in children contains the caption of the section as a Node
    instance with 0 or more children. Subsequent children are elements following
    the section heading.
    """

class Timeline(Node):
    """A <timeline> tag"""

class TagNode(Node):
    """Some tag i.e. <TAGNAME>...</TAGNAME>
    
    The caption attribute contains the tag name, e.g. 'br', 'pre', 'h1' etc.
    
    The children attribute contains the elements contained inside the opening and
    closing tag.
    
    Wikitext::
    
        Some text<br/>
        Some more text
    """

class PreFormatted(TagNode):
    """Preformatted text, encapsuled in <pre>...</pre>
    
    Wikitext::
    
       <pre>
         Some preformatted text
       </pre>
    """

class URL(Node):
    """A (external) URL, which can be a http, https, ftp or mailto URL
    
    The caption attribution contains the URL
    
    Wikitext::
    
       http://example.com/
       mailto:test@example.com
       ftp://example.com/
    """
    
class NamedURL(Node): 
    """A (potentially) named URL
    
    The caption attribute contains the URL. The children attribute contains the
    nodes making up the name of the URL (children can be empty if no name is
    specified).
    
    Wikitext::
    
       [http://example.com/ This is the name of the URL]
       [http://example.com/]
    """

class Table(Node):
    pass

class Row(Node):
    pass

class Cell(Node):
    pass

class Caption(Node):
    pass

class Link(Node):
    """Base class for all "wiki links", i.e. *not* URLs.
    
    All links are further specialized to some subclass of Link depending on the
    link prefix (usually the part before the ":").
    
    The target attribute contains the link target with the prefix stripped off.
    The full_target attribute contains the full link target (but with a potential
    leading ":" stripped off).
    The colon attribute is set to True if the original link target is prefixed
    with a ":".
    The url attribute can contain a valid HTTP URL. If the resolving didn't work
    this attribute is None.
    The children attribute can contain the nodes making up the name of the link.
    The namespace attribute is either set to one of the constants NS_... defined
    in mwlib.namespace (int) or to the prefix of the link (unicode).
    
    Wikitext::
    
      [[Some article|An article]]
      
    This Link would be specialized to an ArticleLink instance. The target attribute
    and the full_target attribute would both be u'Some article', the namespace
    attribute would be NS_MAIN (0) and the children attribute would contain a Text
    node with caption=u'An article'.
    
    Wikitext::
    
      [[Image:Bla.jpg]]
      
    This Link would be specialized to an ImageLink instance. The target attribute
    would be u'Bla.jpg', the full_target attribute would be u'Image:Bla.jpg' and
    the children attribute would be empty.
    """
    
    target = None
    colon = False
    url = None

    

    capitalizeTarget = False # Wiki-dependent setting, e.g. Wikipedia => True


# Link forms:

class ArticleLink(Link):
    """A link to an article
    
    Wikitext::
    
       [[An article]]
       [[An article|Some other text]]
    """

class SpecialLink(Link):
    """Base class for NamespaceLink and InterwikiLink
    
    A link with a prefix, which is *not* a CategoryLink or ImageLink.
    """

class NamespaceLink(SpecialLink):
    """A SpecialLink which has not been recognized as an InterwikiLink
    
    The namespace attribute contains the namespace prefix.
    """

class InterwikiLink(SpecialLink):
    """An 'interwiki' link, i.e. a link into another MediaWiki
    
    The namespace attribute is set to the interwiki prefix.
    
    Wikitext::
    
       [[wikibooks:Some article in wikibook]]
    """

# Non-links with same syntax:

class LangLink(Link):
    """A language link. This is essentially an interwiki link to a MediaWiki
    installation in a different language.
    
    The namesapce attribute is set to the language prefix.
    
    Wikitext::
    
      [[de:Ein Artikel]]
    """

class CategoryLink(Link):
    """A category link, i.e. a link that assigns the containing article
    to the given category.
    
    Wikitext::
    
      [[Category:Bla]]
    
    Note that links of the form [[:Category:Bla]] are *not* CategoryLinks,
    but SpecialLinks with namespace=NS_CATEGORY (14)!
    """

class ImageLink(Link):
    """An image link.
    
    The children attributes potentially contains the nodes making up the image
    caption.
    
    The following attributes are parsed from the wikitext and set accordingly
    (if present, otherwise None):
     * width: width in pixels (int)
     * height: height in pixles (int)
     * align: one of the strings 'left', 'right', 'center', 'none'
     * thumb: set to True if given
    """
    
    target = None
    width = None
    height = None
    align = ''
    thumb = False
    printargs = None
    alt = None
    link = None
    frame = None
    border = None
    upright = None
    
    def isInline(self):
        return not bool(self.align or self.thumb or self.frame)
            
class Text(Node):
    """Plain text
    
    The caption attribute contains the text (unicode),
    the children attribute is always the empty list.
    """
    
    def __repr__(self):
        return repr(self.caption)
    
    def __init__(self, txt):
        self.caption = txt
        self.children = []
    
class Control(Text):
    pass
