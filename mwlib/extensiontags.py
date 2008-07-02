#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

"""
This module can defines special handling for parser extension tags

Examples for Sites and their supported tags:
http://wikitravel.org/en/Special:Version
http://www.mediawiki.org/wiki/Special:Version
http://en.wikipedia.org/wiki/Special:Version
http://wiki.services.openoffice.org/wiki/Special:Version 
http://www.wikia.com/wiki/Special:Version
http://en.wikibooks.org/wiki/Special:Version
"""




from mwlib import parser

# collect the  methods 
methods = []
def add(func): # used as decorator
    methods.append(func)
    return func


@add
def parseRDFTag(self):
    # http://wiki.services.openoffice.org/wiki/Special:Version
    n = self.parsePRETag()
    n.vlist["lang"] = "idl"
    n.caption = "code"
    return n

@add
def parseIDLTag(self):
    # http://wiki.services.openoffice.org/wiki/Special:Version
    n = self.parsePRETag()
    n.vlist["lang"] = "idl"
    n.caption = "code"
    return n

@add
def _parseLISTINGTag(self):
    # http://wikitravel.org/en/Wikitravel:Listings 
    attrs = ["name", "alt", "address", "directions", "phone", "email", "fax", "url", "hours", "price", "lat", "long", "tags"]
    r = self.parseTag()
    n = parser.Node() # group stuff
    r.children.insert(0, n)
    txt = ", ".join(unicode(r.vlist[a]) for a in attrs if r.vlist.get(a,None))
    n.children.append(parser.Text(txt))
    return r

@add
def parseLISTINGTag(self):
    return self._parseLISTINGTag()

@add
def parseSEETag(self):
    return self._parseLISTINGTag()

@add
def parseBUYTag(self):
    return self._parseLISTINGTag()

@add
def parseDOTag(self):
    return self._parseLISTINGTag()

@add
def parseEATTag(self):
    return self._parseLISTINGTag()

@add
def parseTRINKTag(self):
    return self._parseLISTINGTag()

@add
def parseSLEEPTag(self):
    return self._parseLISTINGTag()



def addExtensionTags(): # called from mwlib.parser.Parser
    for m in methods:
        setattr(parser.Parser, m.__name__ , m)


def test():
    from mwlib.uparser import simpleparse
    addExtensionTags()

    raw ="""
===Emergency===
* '''Emergency number:''' '''123'''
* '''Police number:''' '''122'''
* '''Fire HQ number:''' '''180'''
* <listing name="Central Ambulance" alt="" address="Kom El Dekka" directions="opposite Alexandria Station" phone="+20-3-4922257" url="" hours="" price="" lat="" long="" email="" fax=""></listing>
* <eat name="El Moassa Hospital" alt="" address="El Horreya Rd., El Hadara" directions="" phone="+20-3-4212885/6/7/8" url="" hours="" price="" lat="" long="" email="" fax=""></listing>
* <drink name="El Shatby Hospital" alt="" address="Dr. Hassan Sobhy St., El Shatby" directions="" phone="+20-3- 4871586" url="" hours="" price="" lat="" long="" email="" fax=""></listing>
* <do name="Medical Research Institute" alt="" address="El Horreya Rd." directions="beside Gamal Abdel Nasser Hospital" phone="+20-3-4215455 - 4212373" url="" hours="" price="" lat="" long="" email="" fax=""></listing>
* <sleep name="Bacos Ambulance" alt="" address="Mehatet El Souk St., Bacos" directions="" phone="+20-3- 5703454" url="" hours="" price="" lat="" long="" email="" fax=""></listing>
* <listing name="Poison Center Main University Hospital" alt="" address="" directions="" phone="+20-3-4862244" url="" hours="" price="" lat="" long="" email="" fax=""></listing>

<idl>
func 1 = 2
   true := 1Exp2
</idl>

<unknowntag>mama '''mia''' </unknowntag>

"""
    t = simpleparse(raw)
    from mwlib.rl.rltreecleaner import buildAdvancedTree
    #buildAdvancedTree(t)
    #import sys
    #parser.show(sys.stdout, t, 0)


if __name__ == '__main__':
    test()
