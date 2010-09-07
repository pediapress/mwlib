
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
from mwlib.net import fetch, mwapi
from mwlib.parse_collection_page import extract_metadata
from mwlib.metabook import get_licenses, parse_collection_page, collection
from mwlib import myjson
from twisted.internet import reactor,  defer
import urllib

class start_fetcher(object):
    progress = None
    
    def __init__(self, **kw):
        self.fetcher = None
        self.__dict__.update(kw)
        self.nfo = {}

    def get_api(self):
        api = mwapi.mwapi(self.api_url)
        if self.username:
            return api.login(self.username, self.password, self.domain)
        return defer.succeed(api)

    def fetch_pages_from_metabook(self,  api):
        fsout = self.fsout
        metabook=self.metabook
        
        fsout.dump_json(metabook=metabook)
        nfo = self.nfo.copy()

        nfo.update({
                'format': 'nuwiki',
                'base_url': self.base_url,
                'script_extension': self.options.script_extension})


        if self.options.print_template_pattern:
            nfo["print_template_pattern"] = self.options.print_template_pattern
            
        fsout.nfo = nfo

        # fsout.dump_json(nfo=nfo)

        pages = fetch.pages_from_metabook(metabook)
        self.fetcher = fetch.fetcher(api, fsout, pages,
                                     licenses=self.licenses,
                                     status=self.status,
                                     progress=self.progress, 
                                     print_template_pattern=self.options.print_template_pattern,
                                     template_exclusion_category=self.options.template_exclusion_category,
                                     imagesize=self.options.imagesize,
                                     cover_image=metabook.cover_image,
                                     fetch_images=not self.options.noimages)
        return self.fetcher.result
    
    def init_variables(self):
        base_url = self.base_url
        options = self.options
        
        if not base_url.endswith("/"):
            base_url += "/"
        api_url = "".join([base_url, "api", options.script_extension])
        if isinstance(api_url,  unicode):
            api_url = api_url.encode("utf-8")
        self.api_url = api_url

        self.username = options.username
        self.password = options.password
        self.domain   = options.domain
        
        self.fsout = fetch.fsoutput(self.fsdir)

    def fetch_collectionpage(self, api):
        cp = self.options.collectionpage
        if cp is None:
            return api

        try:
            cp = unicode(urllib.unquote(str(cp)), "utf-8")
        except Exception, err:
            pass
            # print "ERR:", err

        self.nfo["collectionpage"] = cp


        def got_pages(val):
            rawtext = val["pages"].values()[0]["revisions"][0]["*"]
            mb = self.metabook = parse_collection_page(rawtext)
            wikitrust(api.baseurl, mb) # XXX blocking twisted reactor. we really should use gevent

            # XXX: localised template parameter names???
            meta = extract_metadata(rawtext, ("cover-image", "cover-color", "text-color", "editor", "description", "sort_as"))
            mb.editor = meta["editor"]
            mb.cover_image = meta["cover-image"]
            mb.cover_color = meta["cover-color"]
            mb.text_color = meta["text-color"]
            mb.description = meta["description"]
            mb.sort_as = meta["sort_as"]

            p = os.path.join(self.fsout.path, "collectionpage.txt")
            if isinstance(rawtext, unicode):
                rawtext=rawtext.encode("utf-8")
            open(p,"wb").write(rawtext)
            return api
        
        return api.fetch_pages([cp]).addBoth(got_pages)
        
    def run(self):
        self.init_variables()
        
        self.licenses = get_licenses(self.metabook)
        podclient = self.podclient
        if podclient is not None:
            old_class = podclient.__class__
            podclient.__class__ = fetch.PODClient

        def login_failed(res):
            print "Fatal error: login failed:", res.getErrorMessage()
            return res

        def reset_podclient(val):
            if podclient is not None:
                podclient.__class__ = old_class
            return val
        
        return (self.get_api()
                .addErrback(login_failed)
                .addCallback(self.fetch_collectionpage)
                .addCallback(self.fetch_pages_from_metabook)
                .addBoth(reset_podclient))

def wikitrust(baseurl, metabook):
    if not os.environ.get("TRUSTEDREVS"):
        return


    if not baseurl.startswith("http://en.wikipedia.org/w/"):
        return

    from mwlib import trustedrevs
    tr = trustedrevs.TrustedRevisions()

    for x in metabook.articles():
        if x.revision:
            continue

        try:
            r = tr.getTrustedRevision(x.title)
            x.revision = r["revid"]

            print "chosen trusted revision: title=%-20r age=%6.1fd revid=%10d user=%-20r" % (r["title"], r["age"], r["revid"], r["user"])
        except Exception, err:
            print "error choosing trusted revision for", repr(x.title),  repr(err)

def make_nuwiki(fsdir, metabook, options, podclient=None, status=None):
    id2wiki = {}
    for x in metabook.wikis:
        id2wiki[x.ident] = (x, [])

    for x in metabook.articles():
        assert x.wikiident in id2wiki, "no wikiconf for %r (%s)" % (x.wikiident,  x)
        id2wiki[x.wikiident][1].append(x)

    is_multiwiki = len(id2wiki)>1
    
    if is_multiwiki:
        progress = fetch.shared_progress(status=status)
    else:
        progress = None
        
    fetchers =[]
    for id, (wikiconf, articles) in id2wiki.items():
        if id is None:
            id = ""
            assert not is_multiwiki, "id must be set in multiwiki"

        if not is_multiwiki:
            id = ""
        
        assert "/" not in id, "bad id: %r" % (id,)
        my_fsdir = os.path.join(fsdir, id)
        
        if is_multiwiki:
            my_mb = collection()
            my_mb.items = articles
        else:
            my_mb = metabook

        wikitrust(wikiconf.baseurl, my_mb)

        fetchers.append(start_fetcher(fsdir=my_fsdir, progress=progress, base_url=wikiconf.baseurl, metabook=my_mb, options=options, podclient=podclient, status=status))

    if is_multiwiki:
        if not os.path.exists(fsdir):
            os.makedirs(fsdir)
        open(os.path.join(fsdir, "metabook.json"),  "wb").write(metabook.dumps())
        myjson.dump(dict(format="multi-nuwiki"), open(os.path.join(fsdir, "nfo.json"), "wb"))
        
        
    retval = []
    def done(listres):
        retval.extend(listres)
        reactor.stop()

    def run():
        return defer.DeferredList([x.run() for x in fetchers])
            
    reactor.callLater(0.0, lambda: run().addBoth(done))
    reactor.run()
    import signal
    signal.signal(signal.SIGINT,  signal.SIG_DFL)
    signal.signal(signal.SIGTERM,  signal.SIG_DFL)
    
    if not retval:
        raise KeyboardInterrupt("interrupted")

    for success, val in retval:
        if not success:
            raise RuntimeError(str(val))
