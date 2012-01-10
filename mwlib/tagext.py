#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


"""
provide mechanism to support tag extensions, i.e. custom tags

List of Tag Extensions:
http://www.mediawiki.org/wiki/Category:Tag_extensions

Examples for Sites and their supported tags:
http://wikitravel.org/en/Special:Version
http://www.mediawiki.org/wiki/Special:Version
http://en.wikipedia.org/wiki/Special:Version
http://wiki.services.openoffice.org/wiki/Special:Version 
http://www.wikia.com/wiki/Special:Version
http://en.wikibooks.org/wiki/Special:Version


List of tags used by Wikia:
http://code.pediapress.com/wiki/wiki/ParserExtensionTags
"""

class ExtensionRegistry(object):
    def __init__(self):
        self.name2ext = {}

    def registerExtension(self, k):
        name = k.name
        assert name not in self.name2ext, 'tag extension for %r already registered' % (name, )
        self.name2ext[name] = k()
        return k
        
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
    from mwlib.refine.compat import parse_txt
    from mwlib import parser
    
    res = parse_txt(txt)
    

    # res is an parser.Article. 
    if len(res.children)!=1:
        res.__class__ = parser.Node
        return res

    res = res.children[0]
    
    if res.__class__==parser.Paragraph:
        res.__class__ = parser.Node

    return res

    # if len(res.children)!=1:
    #     return res
    # return res.children[0]

class TagExtension(object):
    name=None
    def __call__(self, source, attributes):
        return None
    def parse(self, txt):
        return _parse(txt)

class IgnoreTagBase(TagExtension):
    def __call__(self, source, attributes):
        return # simply skip for now


# ---
# --- what follows are some implementations of TagExtensions
# ---

# list of tags than can not easily be re implemented in PDFs 
tags_to_ignore = """chem chess choose dpl dynamicpagelist feyn forum
go googlemapkml graph greek ling plot ppch
randomimage schem staff teng tipa verbatim
aoaudio aovideo bloglist cgamer ggtube googlemap
gtrailer gvideo nicovideo tangler video videogallery
wegame youtube imagelink badge comments createform
fan featuredimage gallerypopulate linkfilter listpages
loggedin loggedout newusers pagequality pollembed randomfeatureduser
randomgameunit randomimagebycategory randomuserswithavatars
rss siteactivity userpoll videogallerypopulate vote
welcomeuser xsound pageby uml graphviz categorytree summary""".split()

for name in tags_to_ignore:
    def _f(name):
        class I(IgnoreTagBase):
            name = name
        register(I)
    _f(name)

class Rot13Extension(TagExtension):
    """
    example extension
    """
    name = 'rot13' # must equal the tag-name
    def __call__(self, source, attributes):
        """
        @source : unparse wikimarkup from the elements text
        @attributes: XML style attributes of this tag

        this functions builds wikimarkup and returns a parse tree for this
        """
        return self.parse("rot13(%s) is %s" % (source, source.encode('rot13')))
register(Rot13Extension)


class TimelineExtension(TagExtension):
    name = "timeline"
    def __call__(self, source, attributes):
        from mwlib.parser import Timeline
        return Timeline(source)
register(TimelineExtension)


class MathExtension(TagExtension):
    name = "math"
    def __call__(self, source, attributes):
        from mwlib.parser import Math
        return Math(source)
register(MathExtension)

class IDLExtension(TagExtension):
    # http://wiki.services.openoffice.org/wiki/Special:Version
    name = "idl"
    def __call__(self, source, attributes):
        return self.parse('<source lang="idl">%s</source>' % source)        
register(IDLExtension)

class RDFExtension(TagExtension):
    # http://www.mediawiki.org/wiki/Extension:RDF
    # uses turtle notation :(
    name = "rdf"
    def __call__(self, source, attributes):
        #return self.parse("<!--\n%s\n -->" % source)
        return # simply skip for now, since comments are not parsed correctly

register(RDFExtension)

class HieroExtension(TagExtension):
    name = "hiero"
    def __call__(self, source, attributes):
        from mwlib import parser
        tn = parser.TagNode("hiero")
        tn.children.append(parser.Text(source))
        return tn   
register(HieroExtension)

class LabledSectionTransclusionExtensionHotFix(IgnoreTagBase):
    #http://www.mediawiki.org/wiki/Extension:Labeled_Section_Transclusion
    name = "section"
register(LabledSectionTransclusionExtensionHotFix)

# --- wiki travel extensions ----

class ListingExtension(TagExtension):
    " http://wikitravel.org/en/Wikitravel:Listings "
    name = "listing"
    attrs = [(u"name",u"'''%s'''"),
             ("alt",u"(''%s'')"),
             ("address",u", %s"),
             ("directions",u" (''%s'')"),
             ("phone", u", Phone:%s"),
             ("fax", u", Fax:%s"),
             ("url", u" [%s]"),
             ("hours", u", %s"),
             ("price", u", %s"),
             ("lat", u", Latitude:%s"),
             ("long", u", Longitude: %s"),
             ("tags", u", Tags: %s")]
    def __call__(self, source, attributes):
        t = u"".join(v%attributes[k] for k,v in self.attrs if attributes.get(k,None))
        if source:
            t += u", %s" % source
        return self.parse(t)

register(ListingExtension)

class SeeExtension(ListingExtension):
    name = "see"
register(SeeExtension)

class BuyExtension(ListingExtension):
    name = "buy"
register(BuyExtension)

class DoExtension(ListingExtension):
    name = "do"
register(DoExtension)

class EatExtension(ListingExtension):
    name = "eat"
register(EatExtension)

class DrinkExtension(ListingExtension):
    name = "drink"
register(DrinkExtension)

class SleepExtension(ListingExtension):
    name = "sleep"
register(SleepExtension)


#print default_registry.name2ext
