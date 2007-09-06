#! /usr/bin/env python

"""simple wsgi app for serving mediawiki content
"""

import os
import mimetypes
import StringIO
from mwlib import uparser, htmlwriter, rendermath

class Pngmath(object):
    def __init__(self, basedir):
        self.basedir = basedir
        
    def __call__(self, env, start_response):
        pi = env['PATH_INFO']
        path = pi.split('/', 2)[-1]
        path = path.strip("/")
        path = path[:-len(".png")]
        
        pngfile = os.path.join(self.basedir, path+'.png')
        if not os.path.exists(pngfile):
            texfile = os.path.join(self.basedir, path+'.tex')
            if not os.path.exists(texfile):
                start_response('404 Not found', [('Content-Type', 'text/plain')])
                return ["404 not found"]
            
            r = rendermath.Renderer()
            r._render_file(path, 'png')
            
        
        d=open(pngfile, 'rb').read()


        start_response('200 Ok', [('Content-Type', 'image/png')])
        return [d]
        
class Files(object):
    def __init__(self, basedir):
        self.basedir = basedir
    
    def __call__(self, env, start_response):
        pi = env['PATH_INFO']
        path = pi.split('/', 2)[-1]
        path = path.strip("/")
        assert ".." not in path, "path must not contain '..'"

        mt, enc = mimetypes.guess_type(path)

        try:
            f=open(os.path.join(self.basedir, path), 'rb')
        except (IOError, OSError), err:
            print "ERROR:", err
            start_response('404 Not found', [('Content-Type', 'text/plain')])
            return ["404 not found"]
            
        send = start_response('200 OK', [('Content-type', mt or 'text/plain; charset=utf-8')])
        while 1:
            data=f.read(0x20000)
            if not data:
                break
            send(data)
        return []


class Serve(object):
    head = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="content-type" content="text/html; charset="utf-8"></meta>
<link rel="stylesheet" href="/resources/pedia.css" />
</head>
<body>
"""
    def __init__(self, db, images):
        self.db = db
        self.images = images
        from mwlib import resources
        self.resources = Files(os.path.dirname(resources.__file__)) # FIXME
        self.image_files = Files(os.path.expanduser("~/images")) # FIXME
        self.pngmath = Pngmath(os.path.expanduser("~/pngmath")) # FIXME
        self.timeline = Files(os.path.expanduser("~/timeline")) # FIXME

    def show(self, env, start_response):
        article = unicode(env['PATH_INFO'], 'utf-8').strip('/').replace("_", " ")
        article = article[:1].upper()+article[1:] # FIXME: we should redirect instead.
        
        raw=self.db.getRawArticle(article)
        if not raw:
            start_response('404 Not found', [('Content-Type', 'text/plain')])
            return ["Article %r not found" % (article,)]
        
        send = start_response('200 OK', [('Content-type', 'text/html; charset=utf-8')])
        send(self.head)

        out=StringIO.StringIO(u"")

        a=uparser.parseString(article, raw=raw, wikidb=self.db)
        w=htmlwriter.HTMLWriter(out, self.images)
        w.write(a)

        return [out.getvalue().encode('utf-8')]
        
    def __call__(self, env, start_response):
        path = env['PATH_INFO']


        if path.startswith("/resources/"):
            return self.resources(env, start_response)
        if path.startswith("/images"):
            return self.image_files(env, start_response)
        if path.startswith("/pngmath/"):
            return self.pngmath(env, start_response)
        if path.startswith("/timeline/"):
            return self.timeline(env, start_response)

        return self.show(env, start_response)


        start_response('404 Not found', [('Content-Type', 'text/plain')])
        return ["404 Not found"]
