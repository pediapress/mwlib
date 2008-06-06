#!/usr/bin/env python
import urllib
import BaseHTTPServer
import SimpleHTTPServer
from mwlib import mwapidb
from mwlib import xhtmlwriter
from mwlib import advtree

default_baseurl = "http://en.wikipedia.org/w/"
default_shared_baseurl = "http://commons.wikimedia.org/w/"
imagesrcresolver = "/imageresolver/IMAGENAME"

class XMLHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def _servXML(self, title):
        base_url = default_baseurl # FIXME
        language = "en" # FIXME
        namespace="en.wikipedia.org" # FIXME
        debug = True # FIXME

        db = mwapidb.WikiDB(base_url, license=None)
        db.print_template = None # deactivate print template lookups
        tree = db.getParsedArticle(title, revision=None)
        advtree.buildAdvancedTree(tree)
        dbw = xhtmlwriter.MWXHTMLWriter(language=language, namespace=namespace, 
                                        imagesrcresolver=imagesrcresolver,
                                        debug=debug)
        #dbw = xhtmlwriter.XMLWriter()
        dbw.write(tree)
        if debug:
            dbw.writeparsetree(tree)

        response = dbw.asstring()
        
        self.send_response(200)
        self.send_header("Content-type", "text/xml")
        self.send_header("Content-length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)
        
        # shut down the connection
        self.wfile.flush()
        
        #self.send_response(500)
        #self.end_headers()


    def _resolveImage(self, title):
        base_url = default_baseurl # FIXME
        shared_base_url = default_shared_baseurl # FIXME
        size = 200 # FIXME

        db = mwapidb.ImageDB(base_url, shared_base_url)
        url = db.getURL(title.decode("utf8"), size=size)
        if not url:
            self.send_response(404)
            self.end_headers()
        else:
            self.send_response(301)
            self.send_header("Location", url)
            self.end_headers()


    def do_GET(self):
        print self.path
        parts = [urllib.unquote_plus(x) for x in self.path.split("/")]
        print parts
        if parts[1] == "mwxml" and len(parts)>2:
            self._servXML(title=parts[2])
        elif parts[1] == "imageresolver" and len(parts)>2:
            self._resolveImage(title=parts[2])
        else:
            SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)
        




def run(server_class = BaseHTTPServer.HTTPServer,
        handler_class = XMLHandler):
    server_address = ('', 8000)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
