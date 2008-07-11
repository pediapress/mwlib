#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import os
import zlib
import re

from mwlib import cdb, dumpparser

def normname(name):
    name = name.strip().replace("_", " ")
    name = name[:1].upper()+name[1:]
    return name

class ZCdbWriter(cdb.CdbMake):
    def __init__(self, indexpath, datapath=None):
        if not datapath:
            datapath = indexpath + 'data.bin'
            indexpath = indexpath + 'idx.cdb'

        cdb.CdbMake.__init__(self, open(indexpath, 'wb'))
        self.data = open(datapath, 'wb')

    def add(self, key, val):
        key = key.encode("utf-8")
        val = zlib.compress(val.encode('utf-8')) # NOTE: encode wasn't in original
        pos = self.data.tell()
        self.data.write(val)
        cdb.CdbMake.add(self, key, "%s %s" % (pos, len(val)))

    def finish(self):
        cdb.CdbMake.finish(self)
        self.data.close()


class ZCdbReader(cdb.Cdb):
    def __init__(self, indexpath, datapath=None):
        if not datapath:
            datapath = indexpath + 'data.bin'
            indexpath = indexpath + 'idx.cdb'

        cdb.Cdb.__init__(self, open(indexpath, 'rb'))
        self.datapath = datapath

    def __getitem__(self, key):
        key = key.encode("utf-8")
        data = cdb.Cdb.__getitem__(self, key) # may raise KeyError 
        return self._readz(data)

    def _readz(self, data):
        pos, len = map(int, data.split())
        
        f=open(self.datapath, "rb")
        f.seek(pos)
        d=f.read(len)
        f.close()
        return zlib.decompress(d).decode('utf-8')

    def iterkeys(self):
        return (k.decode('utf-8') for k in cdb.Cdb.iterkeys(self))

    def iteritems(self):
        return ((k.decode('utf-8'), self._readz(v))
            for k,v in cdb.Cdb.iteritems(self))

    def itervalues(self):
        return (self._readz(v) for v in cdb.Cdb.itervalues(self))


class BuildWiki(object):
    def __init__(self, dumpfile, outputdir, prefix='wiki'):
        if type(dumpfile) in (type(''), type(u'')):
            self.dumpParser = dumpparser.DumpParser(dumpfile)
        else:
            self.dumpParser = dumpfile
        self.output_path = os.path.join(outputdir, prefix)
        self.outputdir = outputdir
        
    def __call__(self):
        if not os.path.exists(self.outputdir):
            os.makedirs(self.outputdir)
        
        self.writer = ZCdbWriter(self.output_path)

        count = 0
        for page in self.dumpParser:
            if page.namespace == dumpparser.NS_MAIN:
                self.handleArticle(page.title, page.text, page.timestamp)
            elif page.namespace == dumpparser.NS_TEMPLATE:
                self.handleTemplate(page.title, page.text, page.timestamp)
            else:
                self.handleOther(page.title, page.text, page.timestamp)

            count += 1
            if count % 5000 == 0:
                self._write(" %s\n" % count)
            elif count % 100 == 0:
                self._write(".")
            
        self.writer.finish()

    def _write(self, msg):
        sys.stdout.write(msg)
        sys.stdout.flush()

    def handleArticle(self, title, text, timestamp):
        self.writer.add(u":"+title, text)

    def handleTemplate(self, title, text, timestamp):
        self.writer.add(u"T:"+title, text)

    def handleOther(self, title, text, timestamp):
        self.writer.add(title, text)
    


class WikiDB(object):
    redirect_rex = re.compile(r'^#Redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)

    def __init__(self, dir, prefix='wiki'):
        self.dir = dir
        self.reader = ZCdbReader(os.path.join(self.dir, prefix))

    def getRawArticle(self, title, raw=None, revision=None):
        title = normname(title)
        print repr(title)
        try:
            res = self.reader[":"+title]
        except KeyError:
            return None

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
        try:
            res = self.reader["T:"+title]
        except KeyError:
            return ''

        mo = self.redirect_rex.search(res)
        if mo:
            redirect = mo.group('redirect')
            redirect = normname(redirect.split("|", 1)[0].split("#", 1)[0])
            if followRedirects:
                return self.getTemplate(redirect, followRedirects=False)
            else:
                sys.stderr.write('Chained redirect not followed: %r -> %r' % (title, redirect))
        return res


    def articles(self):
        return (k[1:]
                for k in self.reader.iterkeys()
                if k[0] == ':')

    def article_texts(self):
        return ((k[1:], v)
                for k in self.reader.iteritems()
                if k[0] == ':')
        
