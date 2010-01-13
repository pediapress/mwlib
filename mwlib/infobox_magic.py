from xml.sax.saxutils import quoteattr
from mwlib import expander
from mwlib.templ import parser

def mark_infobox(self, name, raw):
    
    res = parser.parse(raw, replace_tags=self.replace_tags)
    if not name.lower().startswith("infobox"):
        return res
    print "marking infobox %r" % name
    return (u"<div templatename=%s>\n" % quoteattr(name), res, u"</div>")

def install():
    expander.Expander._parse_raw_template = mark_infobox
