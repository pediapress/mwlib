#! /usr/bin/env python

# Copyright (c) PediaPress GmbH
# See README.rst for additional licensing information.

"""api.php client"""

import urllib, urllib2, urlparse, cookielib, re

try:
    import simplejson as json
except ImportError:
    import json

from mwlib import conf, authors


def loads(s):
    """Potentially remove UTF-8 BOM and call json.loads()"""

    if s and isinstance(s, str) and s[:3] == '\xef\xbb\xbf':
        s = s[3:]
    return json.loads(s)


def merge_data(dst, src):
    todo = [(dst, src)]
    while todo:
        dst, src = todo.pop()
        assert type(dst) == type(src), "cannot merge %r with %r" % (type(dst), type(src))

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
        self.baseurl = apiurl  # XXX
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
        self.edittoken = None
        self.qccount = 0
        self.api_result_limit = conf.get("fetch", "api_result_limit", 500, int)
        self.api_request_limit = conf.get("fetch", "api_request_limit", 15, int)
        self.max_connections = conf.get("fetch", "max_connections", 20, int)
        self.max_retry_count = conf.get("fetch", "max_retry_count", 2, int)
        self.rvlimit = conf.get("fetch", "rvlimit", 500, int)
        self.limit_fetch_semaphore = None

    def report(self):
        pass

    def set_limit(self, limit=None):
        assert self.limit_fetch_semaphore is None, "limit already set"

        if limit is None:
            limit = self.api_request_limit

        from gevent import coros
        self.limit_fetch_semaphore = coros.Semaphore(limit)

    def __repr__(self):
        return "<mwapi %s at %s>" % (self.apiurl, hex(id(self)))

    def _fetch(self, url):
        f = self.opener.open(url)
        data = f.read()
        f.close()
        return data

    def _build_url(self, **kwargs):
        args = {'format': 'json'}
        args.update(**kwargs)
        for k, v in args.items():
            if isinstance(v, unicode):
                args[k] = v.encode('utf-8')
        q = urllib.urlencode(args)
        q = q.replace('%3A', ':')  # fix for wrong quoting of url for images
        q = q.replace('%7C', '|')  # fix for wrong quoting of API queries (relevant for redirects)

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

    def do_request(self, **kwargs):
        sem = self.limit_fetch_semaphore
        if sem is not None:
            sem.acquire()

        try:
            return self._do_request(**kwargs)
        finally:
            if sem is not None:
                sem.release()

    def _do_request(self, query_continue=True, merge_data=merge_data, **kwargs):
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
                self.qccount += 1
                self.report()
                kw = kwargs.copy()
                for d in qc:
                    for k, v in d.items():  # dict of len(1)
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
        while len(siprop) >= 3:
            try:
                r = self.do_request(action="query", meta="siteinfo", siprop="|".join(siprop))
                return r
            except Exception, err:
                print "ERR:", err
                siprop.pop()
        raise RuntimeError("could not get siteinfo")

    def login(self, username, password, domain=None, lgtoken=None):
        args = dict(action="login",
                    lgname=username.encode("utf-8"),
                    lgpassword=password.encode("utf-8"),
                    format="json")

        if domain is not None:
            args['lgdomain'] = domain.encode('utf-8')

        if lgtoken is not None:
            args["lgtoken"] = lgtoken.encode("utf-8")

        res = self._post(**args)

        login_result = res["login"]["result"]
        if login_result == "NeedToken" and lgtoken is None:
            return self.login(username, password, domain=domain, lgtoken=res["login"]["token"])
        elif login_result == "Success":
            return

        raise RuntimeError("login failed: %r" % res)

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

    def _update_kwargs(self, kwargs, titles, revids):
        assert titles or revids and not (titles and revids), 'either titles or revids must be set'

        if titles:
            kwargs["titles"] = "|".join(titles)
        if revids:
            kwargs["revids"] = "|".join([str(x) for x in revids])

    def upload(self, title, txt, summary):
        if self.edittoken is None:
            res = self.do_request(action="query", prop="info|revisions",  intoken="edit",  titles=title)
            self.edittoken = res["pages"].values()[0]["edittoken"]

        self._post(action="edit", title=title, text=txt, token=self.edittoken, summary=summary,  format="json", bot=True)

    def idle(self):
        sem = self.limit_fetch_semaphore
        if sem is None:
            return True
        return not sem.locked()

    def fetch_pages(self, titles=None, revids=None):
        kwargs = dict(prop="revisions",
                      rvprop='ids|content|timestamp|user',
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)
        if titles:
            kwargs['redirects'] = 1

        self._update_kwargs(kwargs, titles, revids)

        rev_result = self.do_request(action="query", **kwargs)

        kwargs = dict(prop="categories",
                      cllimit=self.api_result_limit)
        if titles:
            kwargs['redirects'] = 1

        self._update_kwargs(kwargs, titles, revids)
        cat_result = self.do_request(action="query", **kwargs)
        merge_data(rev_result, cat_result)
        return rev_result

    def fetch_imageinfo(self, titles, iiurlwidth=800):
        kwargs = dict(prop="imageinfo|info",
                      iiprop="url|user|comment|url|sha1|size",
                      iiurlwidth=iiurlwidth,
                      inprop='url'
                      )

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

        # def setrvlimit(res):
        #     print "setting rvlimit to 50 for %s" % (self.baseurl, )
        #     self.rvlimit=50
        #     return res

        # # XXX
        # def retry(err):
        #     if rvlimit <= 50:
        #         return err

        #     kwargs["rvlimit"] = 50

        #     return self.do_request(action="query", **kwargs).addCallback(setrvlimit)

        get_authors = authors.inspect_authors()

        def merge_data(retval, newdata):
            edits = newdata["pages"].values()
            for e in edits:
                revs = e["revisions"]
                get_authors.scan_edits(revs)

        self.do_request(action="query", merge_data=merge_data, **kwargs)
        return get_authors


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

    for _path in (path + "/", '/w/', '/wiki/', '/'):
        base_url = '%s%sapi.php' % (prefix, _path)
        if base_url not in retval:
            retval.append(base_url)
    if url.endswith('/index.php'):
        retval.append(url[:-len('index.php')] + 'api.php')
    return retval


def get_collection_params(api):
    r = api._post(action="expandtemplates",
                         format="json",
                         text="""
template_blacklist={{Mediawiki:coll-template_blacklist_title}}
template_exclusion_category={{Mediawiki:coll-exclusion_category_title}}
print_template_pattern={{Mediawiki:coll-print_template_pattern}}
""")

    allowed = "template_blacklist template_exclusion_category print_template_pattern".split()
    res = dict()
    try:
        txt = r["expandtemplates"]["*"]
    except KeyError:
        return res

    for k, v in re.findall("([a-z_]+)=(.*)", txt):
        v = v.strip()

        if v.startswith("[[") or not v:
            continue

        if k in allowed:
            res[str(k)] = v
    return res


def main():
    s = mwapi("http://en.wikipedia.org/w/api.php")
    print s.get_categorymembers("Category:Mainz")

if __name__ == "__main__":
    main()
