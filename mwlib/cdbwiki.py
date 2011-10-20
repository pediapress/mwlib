#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


import sys
import os
import zlib

try:
    import simplejson as json
except ImportError:
    import json

from mwlib import cdb, dumpparser, siteinfo, nshandling

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

        try:
            count = 0
            for page in self.dumpParser:
                title =  page.title
                text =  page.text
                self.writer.add(title,  text)
                count += 1
                if count % 5000 == 0:
                    self._write(" %s\n" % count)
                elif count % 100 == 0:
                    self._write(".")
        finally:
            self.writer.finish()

    def _write(self, msg):
        sys.stdout.write(msg)
        sys.stdout.flush()

class page(object):
    def __init__(self,  **kw):
        self.__dict__.update(**kw)



class WikiDB(object):
    max_redirects = 5
    def __init__(self, dir, prefix='wiki', lang="en"):
        self.redirects = {}
        self.dir = os.path.abspath(dir)
        self.reader = ZCdbReader(os.path.join(self.dir, prefix))
        
        # FIXME: guess language from xml namespace information???
        self.siteinfo = siteinfo.get_siteinfo(lang)
        if self.siteinfo is None:
            raise RuntimeError("could not get siteinfo for language %r" % (lang,))
        self.nshandler =  nshandling.nshandler(self.siteinfo)
        self.nfo =  dict(base_url="http://%s.wikipedia.org/w/" % (lang, ), # FIXME
                         script_extension = ".php", 
                         ) # FIXME
        self.redirect_matcher = self.nshandler.redirect_matcher
        
    def get_siteinfo(self):
        return self.siteinfo
    
    def normalize_and_get_page(self, name, defaultns):
        fqname = self.nshandler.get_fqname(name, defaultns=defaultns)
        return self.get_page(fqname)

    def get_page(self,  name,  revision=None):
        count = 0
        names =  []
        while count < self.max_redirects:       
            try:
                rawtext = self.reader[name]
            except KeyError:
                return None
            names.append(name)
            r =  self.redirect_matcher(rawtext)
            if r is None:
                break
            # print "Redirect:",  (name,  r)
            name =  r
            count += 1
        if r is not None:
            return None
        return page(rawtext=rawtext, names=names)
    
    def get_data(self, name):
        return self._loadjson(name+".json")
    
    def _loadjson(self, path, default=None):
        path = self._pathjoin(path)
        if os.path.exists(path):
            return json.load(open(path, "rb"))
        return default
    
    def _pathjoin(self, *p):
        return os.path.join(self.dir, *p)



    def articles(self):
        for title in self.reader.iterkeys():
            nsnum = self.nshandler.splitname(title)[0]
            if nsnum==0:
                yield title
                
    def article_texts(self):
        for title, txt in self.reader.iteritems():
            nsnum = self.nshandler.splitname(title)[0]
            if nsnum==0:
                yield title,  txt
