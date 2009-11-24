#! /usr/bin/env python

"""api.php client, non-twisted version"""

import urllib
import urllib2


try:
    import simplejson as json
except ImportError:
    import json

def loads(s):
    """Potentially remove UTF-8 BOM and call json.loads()"""

    if s and isinstance(s, str) and s[:3] == '\xef\xbb\xbf':
        s = s[3:]
    return json.loads(s)

def merge_data(dst, src):
    todo = [(dst, src)]
    while todo:
        dst, src = todo.pop()
        assert type(dst)==type(src), "cannot merge %r with %r" % (type(dst), type(src))
        
        if isinstance(dst, list):
            dst.extend(src)
        elif isinstance(dst, dict):
            for k, v in src.items():
                if k in dst:
                    todo.append((dst[k], v))
                else:
                    dst[k] = v
    
class mwapi(object):    
    def __init__(self, apiurl):
        self.apiurl = apiurl
        
    def __repr__(self):
        return "<mwapi %s at %s>" % (self.apiurl, hex(id(self)))
    
    def _fetch(self, url):
        # print "_fetch:", url
        f=urllib2.urlopen(url)
        data = f.read()
        f.close()
        return data

    def _build_url(self,  **kwargs):
        args = {'format': 'json'}
        args.update(**kwargs)
        for k, v in args.items():
            if isinstance(v, unicode):
                args[k] = v.encode('utf-8')
        q = urllib.urlencode(args)
        q = q.replace('%3A', ':') # fix for wrong quoting of url for images
        q = q.replace('%7C', '|') # fix for wrong quoting of API queries (relevant for redirects)

        url = "%s?%s" % (self.apiurl, q)
        return url
    
    def _request(self, **kwargs):
        url = self._build_url(**kwargs)
        return self._fetch(url)
        
    def do_request(self, query_continue=True, **kwargs):
        last_qc = None
        
        retval = {}
        todo = kwargs
        while todo is not None:
            kwargs = todo
            todo = None
            
            data = json.loads(self._request(**kwargs))
            error = data.get("error")
            if error:
                raise RuntimeError("%s: [fetching %s]" % (error.get("info", ""), self._build_url(**kwargs)))
            merge_data(retval, data["query"])
            
            qc = data.get("query-continue", {}).values()
            
            if qc and query_continue:
                kw = kwargs.copy()
                for d in qc:
                    for k,v in d.items(): # dict of len(1)
                        kw[str(k)] = v

                if qc == last_qc:
                    print "warning: cannot continue this query:",  self._build_url(**kw)
                    return retval
                
                last_qc = qc
                todo = kw

        return retval

    def ping(self):
        return self.do_request(action="query", meta="siteinfo",  siprop="general")
                
    def get_categorymembers(self, cmtitle):
        return self.do_request(action="query", list="categorymembers", cmtitle=cmtitle,  cmlimit=200)


def main():
    s = mwapi("http://en.wikipedia.org/w/api.php")
    print s.get_categorymembers("Category:Mainz")
    
if __name__=="__main__":
    main()
