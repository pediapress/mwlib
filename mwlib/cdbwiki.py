#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import os
import zlib
import re

from mwlib import cdb

try:
    from xml.etree import cElementTree
except ImportError:
    import cElementTree

ns = '{http://www.mediawiki.org/xml/export-0.3/}'

wikiindex = "wikiidx"
wikidata = "wikidata.bin"



def normname(name):
    name = name.strip().replace("_", " ")
    name = name[:1].upper()+name[1:]
    return name

class Tags:
    page = ns + 'page'

    # <title> inside <page>
    title = ns + 'title'

    # <revision> inside <page>
    revision = ns + 'revision'

    # <id> inside <revision>
    revid = ns + 'id'

    # <contributor><username> inside <revision>
    username = ns + 'contributor/' + ns + 'username'

    # <text> inside <revision>
    text = ns + 'text'

    # <timestamp> inside <revision>
    timestamp = ns + 'timestamp'

    # <revision><text> inside <page>
    revision_text = ns + 'revision/' + ns + 'text'

    siteinfo = ns + "siteinfo"

class DumpParser(object):
    category_ns = set(['category', 'kategorie'])
    image_ns = set(['image', 'bild'])
    template_ns = set(['template', 'vorlage'])
    wikipedia_ns = set(['wikipedia'])

    tags = Tags()


    def __init__(self, xmlfilename):
        self.xmlfilename = xmlfilename

    def _write(self, msg):
        sys.stdout.write(msg)
        sys.stdout.flush()

    def openInputStream(self):
        if self.xmlfilename.lower().endswith(".bz2"):
            f = os.popen("bunzip2 -c %s" % self.xmlfilename, "r")
        elif self.xmlfilename.lower().endswith(".7z"):
            f = os.popen("7z -so x %s" % self.xmlfilename, "r")
        else:
            f = open(self.xmlfilename, "r")        

        return f

    def __call__(self):
        f = self.openInputStream()    
        
        count = 0
        for event, elem in cElementTree.iterparse(f):
            if elem.tag != self.tags.page:
                continue
            self.handlePageElement(elem)
            elem.clear()
            count += 1
            
            if count % 5000 == 0:
                self._write(" %s\n" % count)            
            elif count % 100 == 0:
                self._write(".")

    
    def handlePageElement(self, page):
        title = page.find(self.tags.title).text
        revisions = page.findall(self.tags.revision)
        if not revisions:
            return
        revision = revisions[-1]
        
        texttag = revision.find(self.tags.text)
        timestamptag = revision.find(self.tags.timestamp)
        revision.clear()
        
        if texttag is not None:
            text = texttag.text
            texttag.clear()
        else:
            text = None
            
        if timestamptag is not None:
            timestamp = timestamptag.text
            timestamptag.clear()
        else:
            timestamp = None
        
        if not text:
            return

        if isinstance(title, str):
            title = unicode(title)
        if isinstance(text, str):
            text = unicode(text)

            
        if ':' in title:
            ns, rest = title.split(':', 1)
            ns = ns.lower()
            if ns not in self.template_ns:
                return
            self.handleTemplate(rest, text, timestamp)
        else:
            self.handleArticle(title, text, timestamp)

    def handleArticle(self, title, text, timestamp):
        print "ART:", repr(title), len(text), timestamp

    def handleTemplate(self, title, text, timestamp):
        print "TEMPL:", repr(title), len(text), timestamp

class BuildWiki(DumpParser):
    def __init__(self, xmlfilename, outputdir):
        DumpParser.__init__(self, xmlfilename)
        self.outputdir = outputdir
        
    def __call__(self):
        if not os.path.exists(self.outputdir):
            os.makedirs(self.outputdir)
        
        n = os.path.join(self.outputdir, wikiindex)
        out = open(os.path.join(self.outputdir, wikidata), "wb")
        self.out = out
        f = open(n+'.cdb', 'wb')
        c = cdb.CdbMake(f)
        self.cdb = c

        DumpParser.__call__(self)
        c.finish()
        f.close()


    def _writeobj(self, key, val):
        key = key.encode("utf-8")
        val = zlib.compress(val)
        pos = self.out.tell()
        self.out.write(val)
        self.cdb.add(key, "%s %s" % (pos, len(val)))

    def handleArticle(self, title, text, timestamp):
        self._writeobj(u":"+title, text.encode("utf-8"))

    def handleTemplate(self, title, text, timestamp):
        self._writeobj(u"T:"+title, text.encode("utf-8"))
    


class WikiDB(object):
    redirect_rex = re.compile(r'^#Redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)

    def __init__(self, dir):
        self.dir = dir
        self.obj2pos_path = os.path.join(self.dir, wikidata)
        self.cdb = cdb.Cdb(open(os.path.join(self.dir, wikiindex+'.cdb'), 'rb'))

    def _readobj(self, key):
        key = key.encode("utf-8")

        try:
            data = self.cdb[key]  
        except KeyError:
            return None

        pos, len = map(int, data.split())
        
        f=open(self.obj2pos_path, "rb")
        f.seek(pos)
        d=f.read(len)
        f.close()
        return zlib.decompress(d)

    def getRawArticle(self, title, raw=None, revision=None):
        title = normname(title)
        res = self._readobj(":"+title)
        if res is None:
            return  None

        res = unicode(res, 'utf-8')
        mo = self.redirect_rex.search(res)
        if mo:
            redirect = mo.group('redirect')
            redirect = normname(redirect.split("|", 1)[0].split("#", 1)[0])

            return self.getRawArticle(redirect)

        return res

    def getTemplate(self, title, followRedirects=False):
        if ":" in title:
            title = title.split(':', 1)[1]

        title = normname(title)
        res = unicode(self._readobj(u"T:"+title) or "", 'utf-8')
        if not res:
            return res

        mo = self.redirect_rex.search(res)
        if mo:
            redirect = mo.group('redirect')
            redirect = normname(redirect.split("|", 1)[0].split("#", 1)[0])
            return self.getTemplate(redirect)
        return res


    def articles(self):
        for k, v in self.cdb:
            if k[0]==':':
                k = unicode(k[1:], "utf-8")
                yield k
