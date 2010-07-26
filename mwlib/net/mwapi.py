# -*- compile-command: "python mwapi.py" -*-
"""api.php client, url guessing"""

import os
import re
import urlparse
import urllib
from twisted.internet import reactor, defer
from twisted.web import client 
from twisted.python import failure

try:
    import json
except ImportError:
    import simplejson as json

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
    
def guess_api_urls(url):
    """
    @param url: URL of a MediaWiki article
    @type url: str
    
    @returns: list of possible api.php urls
    @rtype: list
    """
    retval = []
    if isinstance(url, unicode):
        url = url.encode("utf-8")
        
    try:
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    except ValueError:
        return retval
    
    if not (scheme and netloc):
        return retval
    

    path_prefix = ''
    if '/wiki/' in path:
        path_prefix = path[:path.find('/wiki/')]
    elif '/w/' in path:
        path_prefix = path[:path.find('/w/')]
    
    prefix = '%s://%s%s' % (scheme, netloc, path_prefix)

    for _path in (path+"/", '/w/', '/wiki/', '/'):
        base_url = '%s%sapi.php' % (prefix, _path)
        retval.append(base_url)
    
    return retval

def try_api_urls(urls, apipool=None):
    """return mwapi instance for the first url which looks like it's working api.php or None"""
    if apipool is None:
        apipool=pool()

    return apipool.try_api_urls(urls)

        

def find_api_for_url(url):
    return try_api_urls(guess_api_urls(url))

class multiplier(object):
    def __init__(self):
        self.key2val = {}
        self.waiting = {}

    def _done(self,  val,  key):
        self.key2val[key] = val
        tmp = self.waiting[key]
        del self.waiting[key]
        for x in tmp:
            x.callback(val)
            
    def get(self, key, fun, *args):
        if key in self.key2val:
            return defer.succeed(self.key2val[key])
        
        d = defer.Deferred()
        if key in self.waiting:
            self.waiting[key].append(d)
            return d
        
        self.waiting[key] = [d] 
        fun(*args).addBoth(self._done, key)
        return d
                 
class pool(object):
    def __init__(self):
        self.multi = multiplier()
        
    def _connect(self,  url):
        m = mwapi(url)
        def done(res):
            return m
        
        return m.ping().addCallback(done)
        
    def get_api(self,  url):
        return self.multi.get(url, self._connect,  url)
    
    def try_api_urls(self, urls):
        urls = list(urls)
        urls.reverse()

        d = defer.Deferred()

        def doit(_):
            if not urls:
                d.callback(None)
                return

            url = urls.pop()
            
            
            def got_api(api):
                d.callback(api)
                return api
            
            # TODO: retry count
            self.get_api(url).addCallbacks(got_api,  doit)

        doit(None)
        return d
    
class mwapi(object):
    api_result_limit = 500 # 5000 for bots
    api_request_limit = 20 # at most 50 titles at once

    max_connections = 20
    siteinfo = None
    max_retry_count = 2
    try:
        rvlimit = int(os.environ.get("RVLIMIT", "500"))
    except ValueError:
        rvlimit = 500
    
    def __init__(self, baseurl, script_extension='.php'):
        self.baseurl = baseurl
        self.script_extension = script_extension
        self._todo = []
        self.num_running = 0
        self.qccount = 0
        self.cookies = {}

        
    def __repr__(self):
        return "<mwapi %s at %s>" % (self.baseurl, hex(id(self)))

    def report(self):
        pass
    
    def idle(self):
        """Return whether another connection is possible at the moment"""

        return self.num_running < self.max_connections

    def login(self, username, password, domain=None, lgtoken=None):
        args = dict(action="login",
                    lgname=username.encode("utf-8"), 
                    lgpassword=password.encode("utf-8"), 
                    format="json", 
                    )
        
        if domain is not None:
            args['lgdomain'] = domain.encode('utf-8')

        if lgtoken is not None:
            args["lgtoken"] = lgtoken.encode("utf-8")

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        postdata = urllib.urlencode(args)
        
        def got_page(res):
            res = loads(res)
            if res["login"]["result"]=="NeedToken" and lgtoken is None:
                return self.login(username, password, domain=domain, lgtoken=res["login"]["token"])

            if res["login"]["result"]=="Success":
                return self
            raise RuntimeError("login failed: %r" % (res, ))
            
        return client.getPage(self.baseurl, method="POST",  postdata=postdata, headers=headers,  cookies=self.cookies).addCallback(got_page)

    def post_request(self, **kw):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        for k,v in kw.items():
            if isinstance(v, unicode):
                kw[k] = v.encode("utf-8")
        
        postdata = urllib.urlencode(kw)
        return client.getPage(self.baseurl,  method="POST",  postdata=postdata, headers=headers, cookies=self.cookies)
    
    def _fetch(self, url):
        errors = []
        d = defer.Deferred()
        
        def done(val):
            if isinstance(val, failure.Failure):
                errors.append(val)
                if len(errors)<self.max_retry_count:
                    print "retrying: could not fetch %r" % (url,)
                    client.getPage(url, cookies=self.cookies).addCallbacks(done, done)
                else:
                    # print "error: could not fetch %r" % (url,)
                    d.callback(val)
            else:
                d.callback(val)
            
        try:
            client.getPage(url, cookies=self.cookies).addCallbacks(done, done)
        except Exception, err: # pyopenssl missing??
            print "FATAL:", err
            os._exit(10)
            
        return d
    
    def _maybe_fetch(self):
        def decref(res):
            self.num_running -= 1
            reactor.callLater(0.0, self._maybe_fetch)
            return res
        
        while self.num_running<self.max_connections and self._todo:
            url, d = self._todo.pop()
            self.num_running += 1
            # print url
            self._fetch(url).addCallbacks(decref, decref).addCallback(loads).chainDeferred(d)


    def _build_url(self,  **kwargs):
        args = {'format': 'json'}
        args.update(**kwargs)
        for k, v in args.items():
            if isinstance(v, unicode):
                args[k] = v.encode('utf-8')
        q = urllib.urlencode(args)
        q = q.replace('%3A', ':') # fix for wrong quoting of url for images
        q = q.replace('%7C', '|') # fix for wrong quoting of API queries (relevant for redirects)

        url = "%s?%s" % (self.baseurl, q)
        return url
    
    def _request(self, **kwargs):
        url = self._build_url(**kwargs)
        
        d=defer.Deferred()
        self._todo.append((url, d))
        reactor.callLater(0.0, self._maybe_fetch)
        return d
        
    def do_request(self, query_continue=True, **kwargs):
        result = defer.Deferred()
        
        retval = {}
        last_qc = [None]
        action = kwargs["action"]

        def got_err(err):
            result.errback(err)

        def got_result(data):
            
            try:
                error = data.get("error")
            except:
                print "ERROR:", data, kwargs
                raise
            
            if error:
                raise RuntimeError("%r: [fetching %r]" % (error.get("info", ""), self._build_url(**kwargs)))
            
            merge_data(retval, data[action])
            
            qc = data.get("query-continue", {}).values()
            
            if qc and query_continue:
                kw = kwargs.copy()
                for d in qc:
                    for k,v in d.items(): # dict of len(1)
                        kw[str(k)] = v

                # print self._build_url(**kw)
                if qc == last_qc[0]:
                    print "warning: cannot continue this query:",  self._build_url(**kw)
                    result.callback(retval)
                    return
                

                last_qc[0] = qc
                        
                self.qccount += 1
                
                schedule(**kw)
                self.report()
                return
            
                # return self._request(**kw).addCallback(got_result)
            result.callback(retval)

        def schedule(**kwargs):
            reactor.callLater(0.0, lambda: self._request(**kwargs).addCallback(got_result).addErrback(got_err))

        schedule(**kwargs)
            
        return result

    def ping(self):
        return self._request(action="query", meta="siteinfo",  siprop="general")
        
    def get_siteinfo(self):
        if self.siteinfo is not None:
            return defer.succeed(self.siteinfo)

        siprop = "general namespaces interwikimap namespacealiases magicwords rightsinfo".split()

        def got_err(r):
            siprop.pop()
            if len(siprop)<3:
                return r
            return doit()
        
        def got_it(siteinfo):
            self.siteinfo = siteinfo
            return siteinfo
        
        def doit():
            return self.do_request(action="query", meta="siteinfo", siprop="|".join(siprop)).addCallbacks(got_it, got_err)

        return doit()

    def _update_kwargs(self, kwargs, titles, revids):
        assert titles or revids and not (titles and revids), 'either titles or revids must be set'

        if titles:
            kwargs["titles"] = "|".join(titles)
        if revids:
            kwargs["revids"] = "|".join([str(x) for x in revids])
        
    def fetch_used(self, titles=None, revids=None, fetch_images=True):
        if fetch_images:
            prop = "revisions|templates|images"
        else:
            prop = "revisions|templates"
            
        kwargs = dict(prop=prop,
                      rvprop='ids',
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)
        if titles:
            kwargs['redirects'] = 1

        self._update_kwargs(kwargs, titles, revids)
        return self.do_request(action="query", **kwargs)

    def fetch_categories(self, titles=None, revids=None):
        kwargs = dict(prop="categories",
                      # rvprop='ids',
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)
        if titles:
            kwargs['redirects'] = 1

        self._update_kwargs(kwargs, titles, revids)
        return self.do_request(action="query", **kwargs)
        
    def fetch_pages(self, titles=None, revids=None):        
        kwargs = dict(prop="revisions|categories",
                      rvprop='ids|content|timestamp|user',
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)
        if titles:
            kwargs['redirects'] = 1

        self._update_kwargs(kwargs, titles, revids)
        return self.do_request(action="query", **kwargs)

    def fetch_imageinfo(self, titles, iiurlwidth=800):
        kwargs = dict(prop="imageinfo",
                      iiprop="url|user|comment|url|sha1|size",
                      iiurlwidth=iiurlwidth)
        
        self._update_kwargs(kwargs, titles, [])
        return self.do_request(action="query", **kwargs)
    
    def get_edits(self, title, revision, rvlimit=None):
        rvlimit = rvlimit or self.rvlimit
        kwargs = {
            'titles': title,
            'redirects': 1,
            'prop': 'revisions',
            'rvprop': 'ids|user|flags|comment|size',
            'rvlimit': rvlimit,
            'rvdir': 'older',
        }
        if revision is not None:
            kwargs['rvstartid'] = revision

        def setrvlimit(res):
            print "setting rvlimit to 50 for %s" % (self.baseurl, )
            self.rvlimit=50
            return res
        
        def retry(err):
            if rvlimit <= 50:
                return err
            
            kwargs["rvlimit"] = 50
            
            return self.do_request(action="query", **kwargs).addCallback(setrvlimit)
                
            
        return self.do_request(action="query", **kwargs).addErrback(retry)
        
    def get_categorymembers(self, cmtitle):
        return self.do_request(action="query", list="categorymembers", cmtitle=cmtitle,  cmlimit=200)

def get_collection_params(api):
    def done(r):
        r = loads(r)
        allowed = "template_blacklist template_exclusion_category print_template_pattern".split()
        res = dict()
        try:
            txt = r["expandtemplates"]["*"]
        except KeyError:
            return res
        
        
        for k,v in re.findall("([a-z_]+)=(.*)", txt):
            v = v.strip()

            if v.startswith("[[") or not v:
                continue

            if k in allowed:
                res[str(k)] = v
        return res

    return api.post_request(action="expandtemplates",
                            format="json",
                            text="""
template_blacklist={{Mediawiki:coll-template_blacklist_title}}
template_exclusion_category={{Mediawiki:coll-exclusion_category_title}}
print_template_pattern={{Mediawiki:coll-print_template_pattern}}
""").addCallback(done)
    
    

def stop(val):
    print val
    reactor.stop()
    
def main():
    p = pool()
    url = "http://de.wikipedia.org/w/api.php"
    # url = "http://simple.pediapress.com/w/api.php"

    def show(r):
        print r

      # print "gotit:",  r

    # p.try_api_urls(["http://de.wikipedia.org/", "http://de.wikipedia.org/w/api.php"]).addBoth(stop)
                   
    api = mwapi(url)
    get_collection_params(api).addBoth(stop)

    # p.get_api(url).addBoth(show)
    # p.get_api(url).addBoth(show)
    # p.get_api(url).addBoth(show)
    # p.get_api(url).addBoth(show)
    
    
if __name__=="__main__":
    reactor.callLater(0.0,  main)
    reactor.run()
