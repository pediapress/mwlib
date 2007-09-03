#! /usr/bin/env python

"""simple wsgi app for serving mediawiki content
"""

import os
import mimetypes
import StringIO
from mwlib import uparser, htmlwriter

class Files(object):
    def __init__(self, basedir):
        self.basedir = basedir
    
    def __call__(self, env, start_response):
        pi = env['PATH_INFO']
        print "PATHINFO:", pi
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
        self.resources = Files(os.path.expanduser("~/resources")) # FIXME
        self.image_files = Files(os.path.expanduser("~/images")) # FIXME

    def show(self, env, start_response):
        article = unicode(env['PATH_INFO'], 'utf-8').strip('/')
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

        return self.show(env, start_response)


        start_response('404 Not found', [('Content-Type', 'text/plain')])
        return ["404 Not found"]
        

def main():
    iface, port = '0.0.0.0', 8080

    from wsgiref.simple_server import make_server
    print "serving on %s:%s" % (iface, port)
    http = make_server(iface, port, Serve(None))
    http.serve_forever()

if __name__ == '__main__':
    main()
