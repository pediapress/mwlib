#! /usr/bin/env python

"""upload zipfile to mediawiki via api.php"""

# http://www.mediawiki.org/wiki/API:Edit_-_Create%26Edit_pages

import sys
import urllib
import json

from mwlib import zipwiki

def callapi(url, args):
    args = args.copy()
    args['format'] = "json"
    for k, v in args.items():
        if isinstance(v, unicode):
            args[k] = v.encode('utf-8')
            
    q = urllib.urlencode(args)
    #q = q.replace('%3A', ':') # fix for wrong quoting of url for images
    #q = q.replace('%7C', '|') # fix for wrong quoting of API queries (relevant for redirects)

    res = urllib.urlopen(url, q).read()
    res = json.loads(unicode(res, 'utf-8'))
    return res


class api(object):
    def __init__(self, url, edittoken='+\\'):
        self.url = url
        self.edittoken = edittoken
        
    def edit(self, title, text):
        token = self.edittoken
        if token is None:
            res = callapi(self.url, dict(action="query", prop="info", intoken="edit", titles=title))
            token = res['query']['pages'].values()[0]['edittoken']
            
        res = callapi(self.url, dict(action="edit", title=title, text=text, token=token))
        assert res['edit']['result']=='Success', 'got bad result: %r' % (res,)
        
        return res


def main():
    url, zipfile = sys.argv[1:]

    a = api(url)
    zw = zipwiki.Wiki(zipfile)

    def edit(title, content):
        if content is None:
            print "WARNING: %r is empty" % (title,)
            return
        print "uploading %s chars to %r" % (len(content), title)
        a.edit(title, content)
        
    for name in zw.articles:
        content = zw.getRawArticle(name)
        edit(name, content)

        
    for name in zw.templates:
        content = zw.getTemplate(name)
        edit('Template:'+name, content)
        
    

if __name__=='__main__':
    main()
    
    
#url = "http://mw/dewiki/api.php"

#print callapi(url, dict(action="query", prop="info", intoken="edit", titles="Main Page"))
#print callapi(url, dict(action="edit", title="Rtest", text="fuck", token='+\\'))
