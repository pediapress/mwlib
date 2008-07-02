"""provide mechanism to support tag extensions, i.e. custom tags
"""

class ExtensionRegistry(object):
    def __init__(self):
        self.name2ext = {}

    def registerExtension(self, k):
        name = k.name
        assert name not in self.name2ext, 'tag extension for %r already registered' % (name, )
        self.name2ext[name] = k()
        
    def names(self):
        return self.name2ext.keys()

    def __getitem__(self, n):
        return self.name2ext[n]

    def __contains__(self, n):
        return n in self.name2ext
        
default_registry = ExtensionRegistry()
register = default_registry.registerExtension

def _parse(txt):
    """parse text....and try to return a 'better' (some inner) node"""
    
    from mwlib import scanner, parser
    
    tokens = scanner.tokenize(txt)
    res=parser.Parser(tokens, "unknown").parse()

    # res is an parser.Article. 
    if len(res.children)!=1:
        res.__class__ = parser.Node
        return res

    res = res.children[0]
    if res.__class__==parser.Paragraph:
        res.__class__ = parser.Node
        
    if len(res.children)!=1:
        return res
    return res.children[0]

class TagExtension(object):
    name=None
    def __call__(self, source, attributes):
        return None
    def parse(self, txt):
        return _parse(txt)


# ---
# --- what follows are some implementations of TagExtensions
# ---
    
class Rot13Extension(TagExtension):
    name = 'rot13'
    def __call__(self, source, attributes):
        return self.parse("rot13(%s) is %s" % (source, source.encode('rot13')))
    
register(Rot13Extension)
