#! /usr/bin/env python

from mwlib import metabook

c = metabook.collection()
c.append_article(title="Mainz", wikiident="de")
c.append_article(title="Mainz", wikiident="en")
c.wikis.append(metabook.WikiConf(ident="de", baseurl="http://de.wikipedia.org/w/"))
c.wikis.append(metabook.WikiConf(ident="en", baseurl="http://en.wikipedia.org/w/"))

print c.dumps()
