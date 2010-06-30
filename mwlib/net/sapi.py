#! /usr/bin/env python

"""api.php client, non-twisted version"""

import urllib, urllib2, cookielib



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
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
        self.edittoken = None
        
    def __repr__(self):
        return "<mwapi %s at %s>" % (self.apiurl, hex(id(self)))
    
    def _fetch(self, url):
        # print "_fetch:", url
        f=self.opener.open(url)
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
    
    def _post(self, **kwargs):
        args = {'format': 'json'}
        args.update(**kwargs)
        for k, v in args.items():
            if isinstance(v, unicode):
                args[k] = v.encode('utf-8')
                
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        postdata = urllib.urlencode(args)

        req = urllib2.Request(self.apiurl, postdata, headers)

        res = loads(self._fetch(req))
        return res
    
    def do_request(self, query_continue=True, **kwargs):
        last_qc = None
        action = kwargs["action"]
        retval = {}
        todo = kwargs
        while todo is not None:
            kwargs = todo
            todo = None
            
            data = json.loads(self._request(**kwargs))
            error = data.get("error")
            if error:
                raise RuntimeError("%s: [fetching %s]" % (error.get("info", ""), self._build_url(**kwargs)))
            merge_data(retval, data[action])
            
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

    def get_siteinfo(self):
        siprop = "general namespaces interwikimap namespacealiases magicwords rightsinfo".split()
        while len(siprop)>=3:
            try:
                r = self.do_request(action="query", meta="siteinfo", siprop="|".join(siprop))
                return r
            except Exception, err:
                print "ERR:",err
                siprop.pop()
        raise RuntimeError("could not get siteinfo")

    def login(self, username, password, domain=None):
        args = dict(action="login",
                    lgname=username.encode("utf-8"), 
                    lgpassword=password.encode("utf-8"), 
                    format="json", 
                    )
        
        if domain is not None:
            args['lgdomain'] = domain.encode('utf-8')

        res = self._post(**args)
        if res["login"]["result"]=="Success":
            return

        print "login failed:", res
        
        raise RuntimeError("login failed")

    
    def upload(self, title, txt, summary):
        if self.edittoken is None:
            res = self.do_request(action="query", prop="info|revisions",  intoken="edit",  titles=title)
            self.edittoken = res["pages"].values()[0]["edittoken"]

        self._post(action="edit", title=title, text=txt, token=self.edittoken, summary=summary,  format="json", bot=True)
            
def main():
    s = mwapi("http://en.wikipedia.org/w/api.php")
    print s.get_categorymembers("Category:Mainz")
    
if __name__=="__main__":
    main()
