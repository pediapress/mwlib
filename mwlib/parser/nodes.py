import os
import re    
from mwlib import namespace

if "MWREFINE" in os.environ:
    from mwlib.utoken import token as base
else:
    base = object
    
class Node(base):
    """Base class for all nodes"""
    
    caption = ''

    def __init__(self, caption=''):
        self.children = []
        self.caption = caption

    def hasContent(self):
        for x in self.children:
            if x.hasContent():
                return True
        return False
    
    def append(self, c, merge=False):
        if c is None:
            return

        if merge and type(c)==Text and self.children and type(self.children[-1])==Text:
            self.children[-1].caption += c.caption
        else:            
            self.children.append(c)

    def __iter__(self):
        for x in self.children:
            yield x

    def __repr__(self):
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
    def append(self, node, merge=False):
        if not isinstance(node, Item):
            c=Item()
            c.append(node)
            self.children.append(c)
        else:
            self.children.append(node)

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
    pass
    
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

class _VListNode(Node):
    def __init__(self, caption=''):
        Node.__init__(self, caption)
        self.vlist = {}

    def __repr__(self):
        return "%s %r %s: %s children" % (self.__class__.__name__, self.caption, self.vlist, len(self.children))
    
class Table(_VListNode):
    pass

class Row(_VListNode):
    pass

class Cell(_VListNode):
    pass

class Caption(_VListNode):
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
    def hasContent(self):
        if self.target:
            return True
        return False

    @classmethod
    def _buildSpecializeMap(cls, namespaces, interwikimap):
        """Return a dict mapping namespace prefixes to a tuple of form
        (link_class, namespace_value).
        """

        from mwlib.lang import languages
        
        res = {}
        
        def reg(name, num):
            name = name.lower()
            if num == namespace.NS_CATEGORY:
                res[name] = (CategoryLink, num)
            elif num == namespace.NS_FILE:
                res[name] = (ImageLink, num)
            else:
                res[name] = (NamespaceLink, num)
        
        for name, num in namespaces.iteritems():
            reg(name, num)
        
        for prefix, d in interwikimap.items():
            if 'language' in interwikimap[prefix] or prefix in languages:
                res[prefix] = (LangLink, prefix)
            else:
                res[prefix] = (InterwikiLink, d.get('renamed', prefix))
        
        return res
    
    @classmethod
    def _setSpecializeMap(cls, nsMap='default', interwikimap=None):
        if interwikimap is None:
            from mwlib.lang import languages
            interwikimap = {}
            for prefix, renamed in namespace.dummy_interwikimap.items():
                interwikimap[prefix] = {'renamed': renamed}
            for lang in languages:
                interwikimap[lang] = {'language': True}
        
        return cls._buildSpecializeMap(
            namespace.namespace_maps[nsMap], interwikimap,
            )
    
    def _specialize(self, specializeMap, imagemod):
        """
        Handles different forms of link, e.g.:
            - [[Foo]]
            - [[Foo|Bar]]
            - [[Category:Foo]]
            - [[:Category:Foo]]
        """

        if not self.children:
            return

        if type(self.children[0]) != Text:
            return
            
        # Handle [[Foo|Bar]]
        full_target = self.children[0].caption.strip()
        del self.children[0]
        if self.children and self.children[0] == Control("|"):
            del self.children[0]

        # Mark [[:Category:Foo]]. See below
        if full_target.startswith(':'):
            self.colon = True
            full_target = full_target[1:]
        self.full_target = full_target
        
        try:
            ns, title = full_target.split(':', 1)
        except ValueError:
            self.namespace = namespace.NS_MAIN
            self.target = full_target
            self.__class__ = ArticleLink
            return

        self.__class__, self.namespace = specializeMap.get(
            ns.lower(),
            (ArticleLink, namespace.NS_MAIN),
        )
        
        if self.colon and self.namespace != namespace.NS_MAIN:
            # [[:Category:Foo]] should not be a category link
            self.__class__ = NamespaceLink

        if self.namespace == namespace.NS_MAIN:
            # e.g. [[Blah: Foo]] is an ordinary article with a colon
            self.target = full_target
        else:
            self.target = title

        if self.__class__ == ImageLink:
            # Handle images. First ensure they are syntactically sound.

            try:
                prefix, suffix = title.rsplit('.', 1)
                if suffix.lower() in ['jpg', 'jpeg', 'gif', 'png', 'svg']:
                    self._readArgs(imagemod) # calls Image._readArgs()
                    return
            except ValueError:
                pass
            # We can't handle this as an image, so default:
            self.__class__ = NamespaceLink 
    

    capitalizeTarget = False # Wiki-dependent setting, e.g. Wikipedia => True

    _SPACE_RE = re.compile('[_\s]+')
    def _normalizeTarget(self):
        """
        Normalizes the format of the target with regards to whitespace and
        capitalization (depending on capitalizeTarget setting).
        """

        if not self.target:
            return

        # really we should have a urllib.unquote() first, but in practice this
        # format may be rare enough to ignore

        # [[__init__]] -> [[init]]
        self.target = self._SPACE_RE.sub(' ', self.target).strip()
        if self.capitalizeTarget:
            self.target = self.target[:1].upper() + self.target[1:]


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

    def _readArgs(self, imagemod):
        idx = 0
        last = []

        while idx<len(self.children):
            x = self.children[idx]
            if x == Control("|"):
                if idx:
                    last = self.children[:idx]
                    
                del self.children[:idx+1]
                idx = 0
                continue

            if not type(x)==Text:
                idx += 1
                continue

            mod_type, match = imagemod.parse(x.caption)

            if mod_type is None:
                idx += 1
                continue

# FIXME: disabled for now, since I don't know what these modifiers do, and what kind of parameters they expect
##             if mod_type == 'img_link':
##                 print "got link:", match
##                 self.link = match
            
##             if mod_type == 'img_alt':
##                 self.alt = match

            del self.children[idx]

            if mod_type == 'img_thumbnail':
                self.thumb = True

            if mod_type == 'img_left':
                self.align = 'left'
            if mod_type == 'img_right':
                self.align = 'right'
            if mod_type == 'img_center':
                self.align = 'center'
            if mod_type == 'img_none':
                self.align = 'none'

            if mod_type in ['img_framed', 'img_frameless']:
                self.frame = match

            if mod_type == 'img_border':
                self.border = True

                
            if mod_type == 'img_upright':
                try:
                    scale = float(match)
                except ValueError:
                    scale = 0.75
                self.upright = scale
                
            if mod_type == 'img_width':                
                # x200px or 100x200px or 200px
                width, height = (match.split('x')+['0'])[:2]
                try:
                    width = int(width)
                except ValueError:
                    width = 0

                try:
                    height = int(height)
                except ValueError:
                    height = 0

                self.width = width
                self.height = height
                
                
        if not self.children:
            self.children = last
        

##             if x.startswith('print='):
##                 self.printargs = x[len('print='):]

##             if x.startswith('alt='):
##                 self.alt = x[len('alt='):]

##             if x.startswith('link='):
##                 self.link = x[len('link='):]


defaultSpecializeMap = Link._setSpecializeMap('default') 
# initialise the Link class (not sure -- anyone will use that?)

            
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

    def hasContent(self):
        if self.caption.strip():
            return True
        return False
    
class Control(Text):
    pass
