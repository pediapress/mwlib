#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

"""client for mediawiki's api.php using twisted"""

import os
import sys
import urllib
import urlparse
import pprint
from mwlib.nshandling import nshandler 
from mwlib import metabook, podclient, utils

from twisted.python import failure, log
from twisted.web import client 
from twisted.internet import reactor, defer

try:
    import json
except ImportError:
    import simplejson as json

class PODClient(podclient.PODClient):
    nextdata = None
    running = False
    def _post(self, data, content_type=None):
        if content_type is None:
            content_type = "application/x-www-form-urlencoded"
            headers = {'Content-Type': content_type}

        
        def postit(postdata, headers):
            client.getPage(self.posturl, method="POST", postdata=postdata, headers=headers).addCallbacks(done, done)
        
        def done(val):
            if self.nextdata:
                postdata, headers = self.nextdata
                self.nextdata = None
                reactor.callLater(0.0, postit, postdata, headers)
            else:
                self.running = False
                
        self.nextdata = (data, headers)
        if self.running:
            return
        
        self.running = True
        reactor.callLater(0.0, postit, data, headers)

def merge_data(dst, src):
    orig = dst 
    
    args = (dst, src)
    
    todo = [(dst, src)]
    while todo:
        dst, src = todo.pop()
        assert type(dst)==type(src), "cannot merge %r with %r" % (type(dst), type(src))
        
        if isinstance(dst, list):
            dst.extend(src)
        elif isinstance(dst, dict):
            for k, v in src.items():
                if k in dst:
                    
                    #assert isinstance(dst[k], (dict,list)), "wrong type %r" % (dict(k=k, v=v, d=dst[k]),)
                    
                    todo.append((dst[k], v))
                else:
                    dst[k] = v
        else:
            assert dst==src
    
def guess_api_urls(url):
    """
    @param url: URL of a MediaWiki article
    @type url: str
    
    @returns: APIHelper instance or None if it couldn't be guessed
    @rtype: @{APIHelper}
    """
    
    try:
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    except ValueError:
        return []
    
    if not (scheme and netloc):
        return []
    

    path_prefix = ''
    if '/wiki/' in path:
        path_prefix = path[:path.find('/wiki/')]
    elif '/w/' in path:
        path_prefix = path[:path.find('/w/')]
    
    prefix = '%s://%s%s' % (scheme, netloc, path_prefix)

    retval = []
    for path in ('/w/', '/wiki/', '/'):
        base_url = '%s%sapi.php' % (prefix, path)
        retval.append(base_url)
    return retval


class mwapi(object):
    api_result_limit = 500 # 5000 for bots
    api_request_limit = 20 # at most 50 titles at once

    max_connections = 20
    siteinfo = None
    max_retry_count = 2
    
    def __init__(self, baseurl, script_extension='.php'):
        self.baseurl = baseurl
        self.script_extension = script_extension
        self._todo = []
        self.num_running = 0
        self.qccount = 0
        
    def idle(self):
        """Return whether another connection is possible at the moment"""

        return self.num_running < self.max_connections

    def _fetch(self, url):
        errors = []
        d = defer.Deferred()
        
        def done(val):
            if isinstance(val, failure.Failure):
                errors.append(val)
                if len(errors)<self.max_retry_count:
                    print "retrying: could not fetch %r" % (url,)
                    client.getPage(url).addCallbacks(done, done)
                else:
                    # print "error: could not fetch %r" % (url,)
                    d.callback(val)
            else:
                d.callback(val)
            
                
        client.getPage(url).addCallbacks(done, done)
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
            self._fetch(url).addCallbacks(decref, decref).addCallback(json.loads).chainDeferred(d)
            
    def _request(self, **kwargs):
        args = {'format': 'json'}
        args.update(**kwargs)
        for k, v in args.items():
            if isinstance(v, unicode):
                args[k] = v.encode('utf-8')
        q = urllib.urlencode(args)
        q = q.replace('%3A', ':') # fix for wrong quoting of url for images
        q = q.replace('%7C', '|') # fix for wrong quoting of API queries (relevant for redirects)

        url = "%s?%s" % (self.baseurl, q)
        #print "url:", url
        
        d=defer.Deferred()
        self._todo.append((url, d))
        reactor.callLater(0.0, self._maybe_fetch)
        return d
        
    def do_request(self, **kwargs):
        retval = {}
        
        def got_result(data):
            try:
                error = data.get("error")
            except:
                print "ERROR:", data, kwargs
                raise
            
            if error:
                return failure.Failure(RuntimeError(error.get("info", "")))

            merge_data(retval, data["query"])
            
            qc = data.get("query-continue", {}).values()
            
            if qc:
                self.qccount += 1
                
                #print "query-continuel:", qc, kwargs
                kw = kwargs.copy()
                for d in qc:
                    for k,v in d.items(): # dict of len(1)
                        kw[str(k)] = v
                return self._request(**kw).addCallback(got_result)
            return retval
        
        return self._request(**kwargs).addCallback(got_result)

    def get_siteinfo(self):
        def got_it(siteinfo):
            self.siteinfo = siteinfo
            return siteinfo
        
        if self.siteinfo is not None:
            return defer.succeed(self.siteinfo)
        
        return self.do_request(action="query", meta="siteinfo", siprop="general|namespaces|namespacealiases|magicwords|interwikimap").addCallback(got_it)

    def _update_kwargs(self, kwargs, titles, revids):
        assert titles or kwargs
        
        if titles:
            kwargs["titles"] = "|".join(titles)
        if revids:
            kwargs["revids"] = "|".join([str(x) for x in revids])
        
    def fetch_used(self, titles=None, revids=None):
        kwargs = dict(prop="revisions|templates|images",
                      rvprop='ids',
                      redirects=1,
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)

        self._update_kwargs(kwargs, titles, revids)
        return self.do_request(action="query", **kwargs)
        
    def fetch_pages(self, titles=None, revids=None):        
        kwargs = dict(prop="revisions",
                      rvprop='ids|content',
                      redirects=1,
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)

        self._update_kwargs(kwargs, titles, revids)
        return self.do_request(action="query", **kwargs)

    def fetch_imageinfo(self, titles, iiurlwidth=800):
        kwargs = dict(prop="imageinfo",
                      iiprop="url|user|comment|url|sha1|metadata|size",
                      iiurlwidth=iiurlwidth)
        
        self._update_kwargs(kwargs, titles, [])
        return self.do_request(action="query", **kwargs)
    
    def get_edits(self, title, revision, rvlimit=500):
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

        return self.do_request(action="query", **kwargs)
        
    def get_categorymembers(self, cmtitle):
        return self.do_request(action="query", list="categorymembers", cmtitle=cmtitle)
    

class FSOutput(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        assert not os.path.exists(self.path)
        os.makedirs(os.path.join(self.path, "images"))
        self.revfile = open(os.path.join(self.path, "revisions-1.txt"), "wb")
        # self.revfile.write("\n -*- mode: wikipedia -*-\n")
        self.seen = set()
        self.imgcount = 0
        
    def close(self):
        self.revfile.close()
        self.revfile = None
        
        
    def get_imagepath(self, title):
        p = os.path.join(self.path, "images", "%s" % (utils.fsescape(title),))
        self.imgcount+=1
        return p
        
    def dump_json(self, **kw):
        for k, v in kw.items():
            p = os.path.join(self.path, k+".json")
            json.dump(v, open(p, "wb"), indent=4)
            
                
    def write_siteinfo(self, siteinfo):
        self.dump_json(siteinfo=siteinfo)

    def write_excluded(self, excluded):
        self.dump_json(excluded=excluded)

    def write_licenses(self, licenses):
        self.dump_json(licenses=licenses)
        
    def write_pages(self, data):
        pages = data.get("pages", {}).values()
        for p in pages:
            
            title = p.get("title")
            ns = p.get("ns")
            revisions = p.get("revisions")
            
            if revisions is None:
                continue

            tmp = []
            for x in revisions:
                x = x.copy()
                x["*"] = len(x["*"])
                tmp.append(x)
            
            for r in revisions:
                revid = r.get("revid")
                txt = r["*"]
                if revid not in self.seen:
                    rev = dict(title=title, ns=ns)
                    if revid is not None:
                        self.seen.add(revid)
                        rev["revid"] = revid

                    header = "\n --page-- %s\n" % json.dumps(rev)
                    self.revfile.write(header)
                    self.revfile.write(txt.encode("utf-8"))
                # else:    
                #     print "FSOutput: skipping duplicate:", dict(revid=revid, title=title)

    def write_edits(self, edits):
        self.dump_json(edits=edits)

    def write_redirects(self, redirects):
        self.dump_json(redirects=redirects)
        
                        
def splitblocks(lst, limit):
    """Split list lst in blocks of max. lmit entries. Return list of blocks."""

    res = []
    start = 0
    while start<len(lst):
        res.append(lst[start:start+limit])
        start+=limit
    return res

def getblock(lst, limit):
    """Return first limit entries from list lst and remove them from the list"""

    r = lst[-limit:]
    del lst[-limit:]
    return r


class Fetcher(object):
    def __init__(self, api, fsout, pages, licenses,
                 podclient=None,
                 print_template_pattern=None,
                 template_exclusion_category=None):
        self.fatal_error = "stopped by signal"
        
        self.api = api
        self.fsout = fsout
        self.licenses = licenses
        self.podclient = podclient
        self.template_exclusion_category = template_exclusion_category
        self.print_template_pattern = print_template_pattern

        if self.print_template_pattern:
            self.make_print_template = utils.get_print_template_maker(self.print_template_pattern)
        else:
            self.make_print_template = None
            
        
        self.redirects = {}
        
        self.count_total = 0
        self.count_done = 0

        self.title2latest = {}
    
        self.edits = []
        self.lambda_todo = []
        self.pages_todo = []
        self.revids_todo = []
        self.imageinfo_todo = []
        self.imagedescription_todo = {} # base path -> list
        self.basepath2mwapi = {}        # base path -> mwapi instance 
        
        self.scheduled = set()

        
        self._refcall(lambda:self.api.get_siteinfo()
                      .addCallback(self._cb_siteinfo)
                      .addErrback(self.make_die_fun("could not get siteinfo")))
                      
        titles, revids = self._split_titles_revids(pages)
        

        limit = self.api.api_request_limit
        dl = []

        def fetch_used(name, lst):            
            for bl in splitblocks(lst, limit):
                kw = {name:bl}
                dl.append(self._refcall(lambda: self.api.fetch_used(**kw).addCallback(self._cb_used)))

        
        fetch_used("titles", titles)
        fetch_used("revids", revids)


        self._refcall(lambda: defer.DeferredList(dl).addCallbacks(self._cb_finish_used, self._cb_finish_used))
        
            
        self.report()
        self.dispatch()

    def _split_titles_revids(self, pages):
        titles = set()
        revids = set()        
           
        for p in pages:
            if p[1] is not None:
                revids.add(p[1])
            else:
                titles.add(p[0])
                
        titles = list(titles)
        titles.sort()

        revids = list(revids)
        revids.sort()
        return titles, revids

    def _cb_finish_used(self, data):
        for title, rev in self.title2latest.items():
             self._refcall(lambda: self.api.get_edits(title, rev).addCallback(self._got_edits))
        self.title2latest = {}
        
    def _cb_siteinfo(self, siteinfo):
        self.fsout.write_siteinfo(siteinfo)
        self.nshandler = nshandler(siteinfo)
        if self.template_exclusion_category:
            ns, partial, fqname = self.nshandler.splitname(self.template_exclusion_category, 14)
            if ns!=14:
                print "bad category name:", repr(self.template_exclusion_category)
            else:
                self._refcall(lambda: self.api.get_categorymembers(fqname).addCallback(self._cb_excluded_category))
            
    def _cb_excluded_category(self, data):
        members = data.get("categorymembers")
        self.fsout.write_excluded(members)
        
        
        
    def report(self):
        qc = self.api.qccount
        done = self.count_done+qc
        total = self.count_total+qc

        limit = self.api.api_request_limit
        jt = self.count_total+len(self.pages_todo)//limit+len(self.revids_todo)//limit
        jt += len(self.title2latest)
        msg = "%s/%s/%s jobs -- %s/%s running" % (self.count_done, self.count_total, jt, self.api.num_running, self.api.max_connections)

        if jt < 10:
            progress = self.count_done
        else:
            progress =  100.0*self.count_done /  jt
            
        if self.podclient:
            self.podclient.post_status(status=msg, progress=progress)

            
        isatty = getattr(sys.stdout, "isatty", None)
        if isatty and isatty():
            sys.stdout.write("\x1b[K"+msg+"\r")
            sys.stdout.flush()
            
    def _got_edits(self, data):
        edits = data.get("pages").values()
        self.edits.extend(edits)
        
    def _got_pages(self, data):
        r = data.get("redirects", [])
        self._update_redirects(r)        
        self.fsout.write_pages(data)
        return data

    def _extract_attribute(self, lst, attr):
        res = []
        for x in lst:
            t = x.get(attr)
            if t:
                res.append(t)
        
        return res
    def _extract_title(self, lst):
        return self._extract_attribute(lst, "title")

    def _update_redirects(self, lst):
        for x in lst:
            t = x.get("to")
            f = x.get("from")
            if t and f:
                self.redirects[f]=t
                
    def _cb_used(self, used):
        self._update_redirects(used.get("redirects", []))        
        
        pages = used.get("pages", {}).values()
        
        revids = set()
        for p in pages:
            tmp = self._extract_attribute(p.get("revisions", []), "revid")
            if tmp:
                latest = max(tmp)
                title = p.get("title", None)
                old = self.title2latest.get(title, 0)
                self.title2latest[title] = max(old, latest)    
                
            revids.update(tmp)
        
        templates = set()
        images = set()
        for p in pages:
            images.update(self._extract_title(p.get("images", [])))
            templates.update(self._extract_title(p.get("templates", [])))

        for i in images:
            if i not in self.scheduled:
                self.imageinfo_todo.append(i)
                self.scheduled.add(i)
                
        for r in revids:
            if r not in self.scheduled:
                self.revids_todo.append(r)
                self.scheduled.add(r)
                
        for t in templates:
            if t not in self.scheduled:
                self.pages_todo.append(t)
                self.scheduled.add(t)

            if self.print_template_pattern is not None and ":" in t:
                t = self.make_print_template(t)                
                if t not in self.scheduled:
                    self.pages_todo.append(t)
                    self.scheduled.add(t)
        
    def _cb_imageinfo(self, data):
        # print "data:", data
        infos = data.get("pages", {}).values()
        # print infos[0]
        new_basepaths = set()
        
        for i in infos:
            title = i.get("title")
            
            ii = i.get("imageinfo", [])
            if not ii:
                continue
            ii = ii[0]
            thumburl = ii.get("thumburl", None)
            # FIXME limit number of parallel downloads
            if thumburl:
                # FIXME: add Callback that checks correct file size
                if thumburl.startswith('/'):
                    thumburl = urlparse.urljoin(self.api.baseurl, thumburl)
                self._refcall(lambda: client.downloadPage(str(thumburl), self.fsout.get_imagepath(title)))

                descriptionurl = ii.get("descriptionurl", "")
                if "/" in descriptionurl:
                    path, localname = descriptionurl.rsplit("/", 1)
                    t = (title, descriptionurl)
                    if path in self.imagedescription_todo:
                        self.imagedescription_todo[path].append(t)
                    else:
                        new_basepaths.add(path)
                        self.imagedescription_todo[path] = [t]
                        
        for path in new_basepaths:
            self._refcall(lambda: self._get_mwapi_for_path(path).addCallback(self._cb_got_api, path))



    def _cb_image_edits(self, data):
        edits = data.get("pages").values()

        # FIXME: self.nshandler might not be initialized
        local_nsname = self.nshandler.get_nsname_by_number(6)
        
        # change title prefix to make them look like local pages
        for e in edits:
            title = e.get("title")
            prefix, partial = title.split(":", 1)
            e["title"] = "%s:%s" % (local_nsname, partial)

        self.edits.extend(edits)

    def _cb_image_contents(self, data):
        # FIXME: self.nshandler might not be initialized
        local_nsname = self.nshandler.get_nsname_by_number(6)
        
        pages = data.get("pages", {}).values()
        # change title prefix to make them look like local pages
        for p in pages:
            title = p.get("title")
            prefix, partial = title.split(":", 1)
            p["title"] = "%s:%s" % (local_nsname, partial)

            revisions = p.get("revisions", [])
            # the revision id's could clash with some local ids. remove them.
            for r in revisions:
                try:
                    del r["revid"]
                except KeyError:
                    pass
            
            
        # XXX do we also need to handle redirects here?
        self.fsout.write_pages(data)
    
    def _cb_got_api(self, api, path):
        todo = self.imagedescription_todo[path]
        del self.imagedescription_todo[path]
        
        titles = set([x[0] for x in todo])
        # "-d-" is just some prefix to make the names here not clash with local names
        titles = [t for t in titles if "-d-"+t not in self.scheduled]
        self.scheduled.update(["-d-"+x for x in titles])
        if not titles:
            return
        
        def got_siteinfo(siteinfo):
            ns = nshandler(siteinfo)
            nsname = ns.get_nsname_by_number(6)
            
            local_names=[]
            for x in titles:
                partial = x.split(":", 1)[1]
                local_names.append("%s:%s" % (nsname, partial))


            for bl in splitblocks(local_names, api.api_request_limit):
                self.lambda_todo.append(lambda bl=bl: api.fetch_pages(titles=bl).addCallback(self._cb_image_contents))

            for k in local_names:
                self.lambda_todo.append(lambda title=k: api.get_edits(title, None).addCallback(self._cb_image_edits))
        
        # print "got api for", repr(path), len(todo)
        return api.get_siteinfo().addCallback(got_siteinfo)
        
            
    def _get_mwapi_for_path(self, path):
        if isinstance(path, unicode):
            path = path.encode("utf-8")
            
        urls = guess_api_urls(path)
        if not urls:
            return defer.fail("cannot guess api url for %r" % (path,))

        if self.api.baseurl in urls:
            return defer.succeed(self.api)

        if path in self.basepath2mwapi:
            return defer.succeed(self.basepath2mwapi[path])
        
        
        dlist = []
        for k in urls:
            m = mwapi(k)
            m.max_retry_count = 1
            dlist.append(m.get_siteinfo().addCallback(lambda siteinfo, api=m: (api, siteinfo)))

        def got_api(results):
            for r in results:
                if r[0]:
                    api, siteinfo = r[1]
                    api.max_retry_count = 2
                    self.basepath2mwapi[path] = api
                    return api
            self.basepath2mwapi[path] = self.api
            return self.api # FIXME: better would be returning None, skipping images (?)
                   
        return defer.DeferredList(dlist, consumeErrors=True).addCallback(got_api)
            
    def dispatch(self):
        limit = self.api.api_request_limit

        def doit(name, lst):
            while lst and self.api.idle():
                bl = getblock(lst, limit)
                self.scheduled.update(bl)
                kw = {name:bl}
                self._refcall(lambda: self.api.fetch_pages(**kw).addCallback(self._got_pages))

        while self.imageinfo_todo and self.api.idle():
            bl = getblock(self.imageinfo_todo, limit)
            self.scheduled.update(bl)
            self._refcall(lambda: self.api.fetch_imageinfo(titles=bl).addCallback(self._cb_imageinfo))
            
        doit("revids", self.revids_todo)
        doit("titles", self.pages_todo)

        while self.lambda_todo:
            self._refcall(self.lambda_todo.pop())

        self.report()
        
        if self.count_done==self.count_total:
            self.finish()
            self.fatal_error = None
            print
            reactor.stop()

    def finish(self):
        self.fsout.write_edits(self.edits)
        self.fsout.write_redirects(self.redirects)
        self.fsout.write_licenses(self.licenses)
        self.fsout.close()
        
    def _refcall(self, fun):
        """Increment refcount, schedule call of fun (returns Deferred)
        decrement refcount after fun has finished.
        """

        self._incref()
        try:
            d=fun()
            assert isinstance(d, defer.Deferred), "got %r" % (d,)
        except:
            print "function failed"
            raise
        return d.addCallbacks(self._decref, self._decref)
        
    def _incref(self):
        self.count_total += 1
        self.report()
        
    def _decref(self, val):
        self.count_done += 1
        reactor.callLater(0.0, self.dispatch)
        if isinstance(val, failure.Failure):
            log.err(val)

    def make_die_fun(self, reason):
        def fatal(val):
            self.fatal_error = reason
            reactor.stop()
            print "fatal: %s [%s]" % (reason, val)        
            
        return fatal
    
        
def done(data):
    print "done", json.dumps(data, indent=4)
        

    
def doit(pages):
    api = mwapi("http://en.wikipedia.org/w/api.php")
    api.api_request_limit = 10

    # api.get_categorymembers("Category:Exclude in print").addCallback(done)
    # return
    
    
    api.fetch_imageinfo(titles=["File:DSC00996.JPG", "File:MacedonEmpire.jpg"]).addCallback(done)
    return
    # api.fetch_used([p[0] for p in pages]).addCallback(done)
    # return

    
    fs = FSOutput("tmp")

    
    f = Fetcher(api, fs, pages)
    
def pages_from_metabook(mb):
    articles = metabook.get_item_list(mb, "article")
    pages = [(x["title"], x.get("revision")) for x in articles]
    return pages
    
def main():
    mb = json.load(open("metabook.json"))
    pages = pages_from_metabook(mb)
    
    # pages = [("___user___:___schmir  __", None)] #, ("Mainz", None)]
    
    # log.startLogging(sys.stdout)
    reactor.callLater(0.0, doit, pages)
    reactor.run()
    
if __name__=="__main__":
    main()
    
