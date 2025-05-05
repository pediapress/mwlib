#! /usr/bin/env py.test

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
import codecs

from mwlib import parser
from mwlib.parser import Math, Timeline

rot13_encode = codecs.getencoder("rot-13")


class ExtensionRegistry:
    def __init__(self):
        self.name2ext = {}

    def register_extension(self, ext):
        ext_name = ext.name
        if ext_name in self.name2ext:
            raise ValueError(f"tag extension for {ext_name!r} already registered")
        self.name2ext[ext_name] = ext()
        return ext

    def names(self):
        return list(self.name2ext.keys())

    def __getitem__(self, index):
        return self.name2ext[index]

    def __contains__(self, item):
        return item in self.name2ext


default_registry = ExtensionRegistry()
register = default_registry.register_extension


def _parse(txt):
    """parse text....and try to return a 'better' (some inner) node"""
    from mwlib.parser.refine.compat import parse_txt

    res = parse_txt(txt)

    if len(res.children) != 1:
        res.__class__ = parser.Node
        return res

    res = res.children[0]

    if res.__class__ == parser.Paragraph:
        res.__class__ = parser.Node

    return res


class TagExtension:
    name = None

    def __call__(self, source, attributes):
        return None

    def parse(self, txt):
        return _parse(txt)


class IgnoreTagBase(TagExtension):
    def __call__(self, source, attributes):
        return  # simply skip for now


# ---
# --- what follows are some implementations of TagExtensions
# ---

# list of tags than can not easily be re implemented in PDFs
tags_to_ignore = ["phonos", "audio", "chem", "chess", "choose", "dpl", "dynamicpagelist", "feyn", "forum", "go", "googlemapkml", "graph", "greek", "ling", "plot", "ppch", "randomimage", "schem", "staff", "teng", "tipa", "verbatim", "aoaudio", "aovideo", "bloglist", "cgamer", "ggtube", "googlemap", "gtrailer", "gvideo", "nicovideo", "tangler", "video", "videogallery", "wegame", "youtube", "imagelink", "badge", "comments", "createform", "fan", "featuredimage", "gallerypopulate", "linkfilter", "listpages", "loggedin", "loggedout", "newusers", "pagequality", "pollembed", "randomfeatureduser", "randomgameunit", "randomimagebycategory", "randomuserswithavatars", "rss", "siteactivity", "templatestyles", "userpoll", "videogallerypopulate", "vote", "welcomeuser", "xsound", "pageby", "uml", "graphviz", "categorytree", "summary", "slippymap"]

for name in tags_to_ignore:

    def _f():
        class Ignore(IgnoreTagBase):
            name = name

        register(Ignore)

    _f()


class Rot13Extension(TagExtension):
    """
    example extension
    """

    name = "rot13"  # must equal the tag-name

    def __call__(self, source, attributes):
        """
        @source : unparse wikimarkup from the elements text
        @attributes: XML style attributes of this tag

        this functions builds wikimarkup and returns a parse tree for this
        """
        return self.parse(f"rot13({source}) is {rot13_encode(source)[0]}")


register(Rot13Extension)


class TimelineExtension(TagExtension):
    name = "timeline"

    def __call__(self, source, attributes):
        return Timeline(source)


register(TimelineExtension)


class MathExtension(TagExtension):
    name = "math"

    def __call__(self, source, attributes):
        return Math(source)


register(MathExtension)


class IDLExtension(TagExtension):
    # http://wiki.services.openoffice.org/wiki/Special:Version
    name = "idl"

    def __call__(self, source, attributes):
        return self.parse('<source lang="idl">%s</source>' % source)


register(IDLExtension)


class Syntaxhighlight(TagExtension):
    """http://www.mediawiki.org/wiki/Syntaxhighlight"""

    name = "syntaxhighlight"

    def __call__(self, source, attributes):
        return self.parse(
            "<source{}>{}</source>".format(
                "".join(f" {k}={v}" for k, v in attributes.items()), source
            )
        )


register(Syntaxhighlight)


class RDFExtension(TagExtension):
    # http://www.mediawiki.org/wiki/Extension:RDF
    # uses turtle notation :(
    name = "rdf"

    def __call__(self, source, attributes):
        return  # simply skip for now, since comments are not parsed correctly


register(RDFExtension)


class TimeExtension(TagExtension):
    name = "time"

    def __call__(self, source, attributes):
        return self.parse(source)


register(TimeExtension)


class HieroExtension(TagExtension):
    name = "hiero"

    def __call__(self, source, attributes):
        from mwlib import parser

        tag_node = parser.TagNode("hiero")
        tag_node.children.append(parser.Text(source))
        return tag_node


register(HieroExtension)


class LabledSectionTransclusionExtensionHotFix(IgnoreTagBase):
    # http://www.mediawiki.org/wiki/Extension:Labeled_Section_Transclusion
    name = "section"


register(LabledSectionTransclusionExtensionHotFix)

# --- wiki travel extensions ----


class ListingExtension(TagExtension):
    "http://wikitravel.org/en/Wikitravel:Listings"
    name = "listing"
    attrs = [
        ("name", "'''%s'''"),
        ("alt", "(''%s'')"),
        ("address", ", %s"),
        ("directions", " (''%s'')"),
        ("phone", ", ☎ %s"),
        ("fax", ", fax: %s"),
        ("email", ", e-mail: %s"),
        ("url", ", %s"),
        ("hours", ", %s"),
        ("price", ", %s"),
        ("tags", ", Tags: %s"),
    ]

    def __call__(self, source, attributes):
        tag = "".join(
            v % attributes[k] for k, v in self.attrs if attributes.get(k, None)
        )
        if source:
            tag += ", %s" % source
        return self.parse(tag)


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
