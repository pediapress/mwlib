#!/usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.rst for additional licensing information.

import urllib
import sys
import cgi
import subprocess
import BaseHTTPServer
import SimpleHTTPServer
import urllib2
from mwlib.utils import daemonize
try:
    import simplejson as json
except ImportError:
    import json

# init host and port fu**ed up style # FIXME
host, port = "localhost", 8000
if len(sys.argv) > 1:
    host = sys.argv[1]
if len(sys.argv) > 2:
    port = int(sys.argv[2])


mwzip_cmd = 'mw-zip' # (Path to) mw-zip executable.
default_baseurl = "en.wikipedia.org/w"
serviceurl = "http://pediapress.com/api/collections/"
thisservice = "http://%s:%d/"% (host, port)

class State(object):
    articles = []
    baseurl = default_baseurl
    bookmarklet ="javascript:location.href='%s?addarticle='+location.href" % thisservice


class MyHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    # all shared between all requests
    state = State()

    def renderpage(self):
        response = """<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
</head>
<body>
        <form action="">
        baseurl: <input type="text" name="baseurl" value="%s">
        <br/>
        <input type="submit" value="submit"/>
        <input type="submit" name="reset" value="reset"/>
        <input type="submit" name="order" value="order"/>
        <a href="%s">refresh if pages were added</a>
        <br/>
        Articles:        <br/>
        <textarea cols="80" rows="24" name="articles">%s</textarea>
        </form>
        <h5>usage</h5>
        drag and drop this bookmarklet to <a href="%s">add article</a>s from any supported mediawiki
        <br/>
        bookmark this page to get back to this page :)
        <br/>
        Note, only articles from one wiki allowed, baseurl should be set so, that api.php can be found
        <br/>
        Click order to send your collection to pediapress
        </body>
        </html>
        """ %(self.state.baseurl, 
              thisservice,
              ("\n".join(self.state.articles)),
              self.state.bookmarklet,
              )
        return response
    
    def do_GET(self):
        path, query = urllib.splitquery(self.path)
        path = [urllib.unquote_plus(x) for x in path.split("/")]
        query = cgi.parse_qs(query or "")
        print path, query
        app = path[1]
        args = path[2:]
        print args, query
        redir = False
        
        print self.state.articles

        if "articles" in query:
            self.state.articles = [x.strip() for x in query["articles"][0].split("\n") if x.strip()]
            redir = True

        if "baseurl" in query:
            self.state.baseurl = query["baseurl"][0].strip() 
            redir = True

        if "addarticle" in query:
            url = query["addarticle"][0]
            self.state.articles.append( url )
            self.send_response(301)
            self.send_header("Location", url)
            self.end_headers()
            return 

        if "order" in query and self.state.articles and self.state.baseurl:
            return self.do_zip_post()

        if "reset" in query:
            self.state.articles = []
            self.state.baseurl = default_baseurl
            redir = True

        if redir:
            self.send_response(301)
            self.send_header("Location", thisservice)
            self.end_headers()
            return 

        print self.state.articles
        
        response = self.renderpage()
        #self.send_header("Content-type", "text/html")
        #self.send_header("Content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)
        
    def do_zip_post(self):

        # automatically acquires a post url 
        u = urllib2.urlopen(serviceurl, data="any")
        h = json.loads(u.read())
        posturl = h["post_url"]
        redirect_url = h["redirect_url"]
        print "acquired post url", posturl
        print "redirected browser to", redirect_url

        
        args = [
            mwzip_cmd,
            '--daemonize',
            '--conf', "http://" +self.state.baseurl,
            '--posturl', posturl,
        ]
        
        for a in self.state.articles:
            a = a.split("/")[-1]
            if a:
                args.append('%s' % str(a))

        print "executing", mwzip_cmd, args
        daemonize()
        rc = subprocess.call(executable=mwzip_cmd, args=args)
        if rc != 0:
            self.send_response(500)
            self.end_headers()
            self.wfile.write("post failed")
        else:
            self.send_response(301)
            self.send_header("Location", redirect_url)
            self.end_headers()



def run():
    server_address = (host, port)
    httpd = BaseHTTPServer.HTTPServer(server_address, MyHandler)
    print "usage: %s [host=localhost] [port=8000]" % sys.argv[0]
    print "listening as http://%s:%d" % (host, port)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
