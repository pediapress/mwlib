#! /usr/bin/env python

# Copyright (c) 2007-2011 PediaPress GmbH
# See README.rst for additional licensing information.

import os, sys, urlparse, urllib2, time, traceback
import gevent, gevent.pool, gevent.coros, gevent.event

import sqlite3dbm
from lxml import etree

from mwlib import utils, nshandling, conf, myjson as json
from mwlib.net import sapi as mwapi


class shared_progress(object):
    status = None
    last_percent = 0.0

    def __init__(self, status=None):
        self.key2count = {}
        self.status = status
        self.stime = time.time()

    def report(self):
        isatty = getattr(sys.stdout, "isatty", None)
        done, total = self.get_count()
        if not total:
            total = 1

        if total < 50:
            percent = done / 5.0
        else:
            percent = 100.0 * done / total

        percent = round(percent, 3)

        needed = time.time() - self.stime
        if needed < 60.0:
            percent *= needed / 60.0

        if percent <= self.last_percent:
            percent = self.last_percent

        self.last_percent = percent

        if isatty and isatty():
            msg = "%s/%s %.2f %.2fs" % (done, total, percent, needed)
            if sys.platform in ("linux2", "linux3"):
                from mwlib import linuxmem
                msg += " %.1fMB" % linuxmem.resident()
            sys.stdout.write("\x1b[K" + msg + "\r")
            sys.stdout.flush()

        if self.status:
            try:
                s = self.status.stdout
                self.status.stdout = None
                self.status(status="fetching", progress=percent)
            finally:
                self.status.stdout = s

    def set_count(self, key, done, total):
        self.key2count[key] = (done, total)
        self.report()

    def get_count(self):
        done = 0
        total = 0
        for (d, t) in self.key2count.values():
            done += d
            total += t
        return done, total


class fsoutput(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        assert not os.path.exists(self.path)
        os.makedirs(os.path.join(self.path, "images"))
        self.revfile = open(os.path.join(self.path, "revisions-1.txt"), "wb")
        self.seen = dict()
        self.imgcount = 0
        self.nfo = None

        for storage in ['authors', 'html', 'imageinfo']:
            fn = os.path.join(self.path, storage + '.db')
            db = sqlite3dbm.open(fn, 'n')
            db.conn.execute("PRAGMA synchronous = 0")
            setattr(self, storage, db)

    def set_db_key(self, name, key, value):
        storage = getattr(self, name, None)
        assert storage is not None, 'storage not existant %s' % name
        storage[key] = json.dumps(value)

    def close(self):
        if self.nfo is not None:
            self.dump_json(nfo=self.nfo)
        self.revfile.close()
        self.revfile = None

    def get_imagepath(self, title):
        p = os.path.join(self.path, "images", "%s" % (utils.fsescape(title),))
        self.imgcount += 1
        return p

    def dump_json(self, **kw):
        for k, v in kw.items():
            p = os.path.join(self.path, k + ".json")
            json.dump(v, open(p, "wb"), indent=4, sort_keys=True)

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

            for r in revisions:
                revid = r.get("revid")
                txt = r["*"]
                if revid not in self.seen:
                    rev = dict(title=title, ns=ns)
                    if revid is not None:
                        self.seen[revid] = rev
                        rev["revid"] = revid
                    self.seen[title] = rev

                    header = "\n --page-- %s\n" % json.dumps(rev, sort_keys=True)
                    self.revfile.write(header)
                    self.revfile.write(txt.encode("utf-8"))
                # else:
                #     print "fsoutput: skipping duplicate:", dict(revid=revid, title=title)

    def write_authors(self):
        self.authors.close()

    def write_html(self):
        self.html.close()

    def write_redirects(self, redirects):
        self.dump_json(redirects=redirects)


def splitblocks(lst, limit):
    """Split list lst in blocks of max. limit entries. Return list of blocks."""
    res = []
    start = 0
    while start < len(lst):
        res.append(lst[start:start + limit])
        start += limit
    return res


def getblock(lst, limit):
    """Return first limit entries from list lst and remove them from the list"""

    r = lst[-limit:]
    del lst[-limit:]
    return r


def callwhen(event, fun):
    while 1:
        try:
            event.wait()
            event.clear()
            fun()
        except gevent.GreenletExit:
            raise
        except Exception:
            traceback.print_exc()
            pass


def download_to_file(url, path, temp_path):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'mwlib')]

    try:
        out = None
        size_read = 0
        f = opener.open(url)
        while 1:
            data = f.read(16384)
            if not data:
                break
            size_read += len(data)
            if out is None:
                out = open(temp_path, "wb")
            out.write(data)

        if out is not None:
            out.close()
            os.rename(temp_path, path)
        # print "GOT", url, size_read

    except Exception, err:
        print "ERROR DOWNLOADING", url, err
        raise


class fetcher(object):
    def __init__(self, api, fsout, pages, licenses,
                 status=None,
                 progress=None,
                 print_template_pattern=None,
                 template_exclusion_category=None,
                 cover_image=None,
                 imagesize=800, fetch_images=True):

        self.dispatch_event = gevent.event.Event()
        self.api_semaphore = gevent.coros.Semaphore(20)

        self.print_template_pattern = None
        self.template_exclusion_category = None
        self.template_blacklist = None
        self.cover_image = cover_image

        self.pages = pages

        self.image_download_pool = gevent.pool.Pool(10)

        self.fatal_error = "stopped by signal"

        self.api = api
        self.api.report = self.report
        self.api_cache = {self.api.apiurl: self.api,}

        self.fsout = fsout
        self.licenses = licenses
        self.status = status
        self.progress = progress or shared_progress(status=status)

        self.imagesize = imagesize
        self.fetch_images = fetch_images

        self.scheduled = set()

        self.count_total = 0
        self.count_done = 0
        self.redirects = {}
        self.cat2members = {}

        self.img_max_retries = 2

        self.title2latest = {}

        self.pages_todo = []
        self.revids_todo = []
        self.imageinfo_todo = []
        self.imagedescription_todo = {}  # base path -> list
        self._nshandler = None

        siteinfo = self.get_siteinfo_for(self.api)
        self.fsout.write_siteinfo(siteinfo)
        self.nshandler = nshandling.nshandler(siteinfo)
        if self.template_exclusion_category:
            ns, partial, fqname = self.nshandler.splitname(self.template_exclusion_category, 14)
            if ns != 14:
                print "bad category name:", repr(self.template_exclusion_category)

        params = mwapi.get_collection_params(api)
        self.__dict__.update(params)
        if template_exclusion_category:
            self.template_exclusion_category = template_exclusion_category

        if print_template_pattern:
            self.print_template_pattern = print_template_pattern

        if self.print_template_pattern:
            self.make_print_template = utils.get_print_template_maker(self.print_template_pattern)
        else:
            self.make_print_template = None

        titles, revids = self._split_titles_revids(pages)

        self.pool = gevent.pool.Pool()
        self.refcall_pool = gevent.pool.Pool(1024)

        self._refcall(self.fetch_html, "page", titles)
        self._refcall(self.fetch_html, "oldid", revids)

        self._refcall(self.fetch_used, "titles", titles)
        self._refcall(self.fetch_used, "revids", revids)

    def run(self):
        self.report()
        dispatch_gr = gevent.spawn(callwhen, self.dispatch_event, self.dispatch)
        try:
            self.pool.join()
        finally:
            dispatch_gr.kill()

        self.finish()

        assert not self.imageinfo_todo
        assert not self.revids_todo
        assert not self.pages_todo

    def extension_img_urls(self, data):
        html = data['text']['*']
        root = etree.HTML(html)

        img_urls = set()
        for img_node in root.xpath('.//img'):
            src = img_node.get('src')
            frags = src.split('/')
            if len(frags):
                fullurl = urlparse.urljoin(self.api.baseurl, src)
                if img_node.get('class') != 'thumbimage' and \
                       ('extensions' in src or 'math' in src):

                    img_urls.add(fullurl)
        return img_urls

    def fetch_html(self, name, lst):
        def fetch(c):
            with self.api_semaphore:
                kw = {name: c}
                res = self.api.do_request(action="parse", redirects="1", **kw)
                res[name] = c

            self.fsout.set_db_key('html', c, res)
            img_urls = self.extension_img_urls(res)
            for url in img_urls:
                fn = url.rsplit('/', 1)[1]
                title = self.nshandler.splitname(fn, defaultns=6)[2]
                self.schedule_download_image(str(url), title)

        self.count_total += len(lst)
        for c in lst:
            self._refcall_noinc(fetch, c)

    def fetch_used(self, name, lst):
        limit = self.api.api_request_limit
        pool = gevent.pool.Pool()
        blocks = splitblocks(lst, limit)
        self.count_total += len(blocks)
        for bl in blocks:
            pool.add(self._refcall_noinc(self.fetch_used_block, name, bl))
        pool.join()

        if conf.noedits:
            return

        items = self.title2latest.items()
        self.title2latest = {}
        self.count_total += len(items)
        for title, rev in items:
            self._refcall_noinc(self.get_edits, title, rev)

    def fetch_used_block(self, name, lst):
        kw = {name: lst, "fetch_images": self.fetch_images}
        used = self.api.fetch_used(**kw)

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

        if self.cover_image:
            images.add(self.nshandler.get_fqname(self.cover_image, 6))
            self.cover_image = None

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

    def get_siteinfo_for(self, m):
        return m.get_siteinfo()

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

    def get_edits(self, title, rev):
        inspect_authors = self.api.get_edits(title, rev)
        authors = inspect_authors.get_authors()
        # print "GOT_EDITS:", title, authors
        self.fsout.set_db_key('authors', title, authors)

    def report(self):
        qc = self.api.qccount

        limit = self.api.api_request_limit
        jt = self.count_total + len(self.pages_todo) // limit + len(self.revids_todo) // limit
        jt += len(self.title2latest)

        self.progress.set_count(self, self.count_done + qc,  jt + qc)

    def _add_catmember(self, title, entry):
        try:
            self.cat2members[title].append(entry)
        except KeyError:
            self.cat2members[title] = [entry]

    def _handle_categories(self, data):
        pages = data.get("pages", {}).values()
        for p in pages:
            categories = p.get("categories")
            if not categories:
                continue

            e = dict(title=p.get("title"), ns=p.get("ns"), pageid=p.get("pageid"))

            for c in categories:
                cattitle = c.get("title")
                if cattitle:
                    self._add_catmember(cattitle, e)

    def _find_redirect(self,  data):
        pages = data.get("pages", {}).values()
        targets = []
        for p in pages:

            title = p.get("title")
            revisions = p.get("revisions")

            if revisions is None:
                continue

            for r in revisions:
                txt = r["*"]
                if not txt:
                    continue

                redirect = self.nshandler.redirect_matcher(txt)
                if redirect:
                    self.redirects[title] = redirect
                    targets.append(redirect)

        if targets:
            self.fetch_used("titles", targets)

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
                self.redirects[f] = t

    def schedule_download_image(self, url, title):
        key = (url, title)
        if key in self.scheduled:
            return
        self.scheduled.add(key)
        self._refcall(self._download_image, url, title)

    def _download_image(self, url, title):
        path = self.fsout.get_imagepath(title)
        temp_path = (path + u'\xb7').encode("utf-8")
        gr = self.image_download_pool.spawn(download_to_file, url, path, temp_path)
        self.pool.add(gr)

    def fetch_imageinfo(self, titles):
        data = self.api.fetch_imageinfo(titles=titles, iiurlwidth=self.imagesize)
        infos = data.get("pages", {}).values()
        # print infos[0]
        new_basepaths = set()

        for i in infos:
            title = i.get("title")

            ii = i.get("imageinfo", [])
            if not ii:
                continue
            ii = ii[0]
            self.fsout.set_db_key('imageinfo', title, ii)
            thumburl = ii.get("thumburl", None)

            if thumburl is None:  # fallback for old mediawikis
                thumburl = ii.get("url", None)

            # FIXME limit number of parallel downloads
            if thumburl:
                # FIXME: add Callback that checks correct file size
                if thumburl.startswith('/'):
                    thumburl = urlparse.urljoin(self.api.baseurl, thumburl)
                self.schedule_download_image(thumburl, title)

                descriptionurl = ii.get("descriptionurl", "")
                if not descriptionurl:
                    descriptionurl = i.get('fullurl', '')

                if descriptionurl and "/" in descriptionurl:
                    path, localname = descriptionurl.rsplit("/", 1)
                    t = (title, descriptionurl)
                    if path in self.imagedescription_todo:
                        self.imagedescription_todo[path].append(t)
                    else:
                        new_basepaths.add(path)
                        self.imagedescription_todo[path] = [t]

        for path in new_basepaths:
            self._refcall(self.handle_new_basepath, path)

    def _get_nshandler(self):
        if self._nshandler is not None:
            return self._nshandler
        return nshandling.get_nshandler_for_lang('en')  # FIXME

    def _set_nshandler(self, nshandler):
        self._nshandler = nshandler

    nshandler = property(_get_nshandler, _set_nshandler)

    def fetch_image_page(self, titles, api):
        data = api.fetch_pages(titles)

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

    def handle_new_basepath(self, path):
        api = self._get_mwapi_for_path(path)
        todo = self.imagedescription_todo[path]
        del self.imagedescription_todo[path]

        titles = set([x[0] for x in todo])
        # "-d-" is just some prefix to make the names here not clash with local names
        titles = [t for t in titles if "-d-" + t not in self.scheduled]
        self.scheduled.update(["-d-" + x for x in titles])
        if not titles:
            return

        siteinfo = self.get_siteinfo_for(api)

        ns = nshandling.nshandler(siteinfo)
        nsname = ns.get_nsname_by_number(6)

        local_names = []
        for x in titles:
            partial = x.split(":", 1)[1]
            local_names.append("%s:%s" % (nsname, partial))

        for bl in splitblocks(local_names, api.api_request_limit):
            self._refcall(self.fetch_image_page, bl, api)

        for title in local_names:
            self._refcall(self.get_image_edits, title, api)

    def get_image_edits(self, title, api):
        get_authors = api.get_edits(title, None)
        local_nsname = self.nshandler.get_nsname_by_number(6)
        # change title prefix to make them look like local pages
        prefix, partial = title.split(":", 1)
        title = '%s:%s' % (local_nsname, partial)
        authors = get_authors.get_authors()
        self.fsout.set_db_key('authors', title, authors)

    def _get_mwapi_for_path(self, path):
        urls = mwapi.guess_api_urls(path)
        for url in urls:
            if url in self.api_cache:
                return self.api_cache[url]
        for url in urls:
            try:
                api = mwapi.mwapi(url)
                api.ping()
                api.set_limit()
                self.api_cache[url] = api
                return api
            except Exception:
                # traceback.print_exc()
                continue

        raise RuntimeError("cannot guess api url for %r" % (path,))

    def dispatch(self):
        limit = self.api.api_request_limit

        def fetch_pages(**kw):
            data = self.api.fetch_pages(**kw)
            self._find_redirect(data)
            r = data.get("redirects", [])
            self._update_redirects(r)
            self._handle_categories(data)
            self.fsout.write_pages(data)

        def doit(name, lst):
            while lst and self.api.idle():
                bl = getblock(lst, limit)
                self.scheduled.update(bl)
                kw = {name: bl}
                self._refcall(fetch_pages, **kw)

        while self.imageinfo_todo and self.api.idle():
            bl = getblock(self.imageinfo_todo, limit)
            self.scheduled.update(bl)
            self._refcall(self.fetch_imageinfo, bl)

        doit("revids", self.revids_todo)
        doit("titles", self.pages_todo)

        self.report()

    def _compute_excluded(self):
        if self.template_exclusion_category:
            ns, partial, fqname = self.nshandler.splitname(self.template_exclusion_category, 14)
            excluded = self.cat2members.get(fqname)
            if excluded:
                self.fsout.write_excluded(excluded)

    def _sanity_check(self):
        seen = self.fsout.seen
        for title, revid in self.pages:
            if revid is not None:
                if revid in seen:
                    continue

            n = self.nshandler.get_fqname(title)
            n = self.redirects.get(n, n)

            if n in seen:
                continue
            print "WARNING: %r could not be fetched" % ((title, revid),)
            # raise RuntimeError("%r could not be fetched" % ((title, revid), ))

        seen = self.fsout.seen

    def finish(self):
        self._sanity_check()
        self._compute_excluded()
        self.fsout.write_redirects(self.redirects)
        self.fsout.write_licenses(self.licenses)
        if self.fsout.nfo and self.print_template_pattern:
            self.fsout.nfo["print_template_pattern"] = self.print_template_pattern
        self.fsout.close()

    def _refcall(self, fun, *args, **kw):
        """Increment refcount, schedule call of fun
        decrement refcount after fun has finished.
        """
        self.count_total += 1
        self.report()
        return self._refcall_noinc(fun, *args, **kw)

    def _refcall_noinc(self, fun, *args, **kw):
        def refcall_fun():
            try:
                fun(*args, **kw)
            finally:
                self.count_done += 1
                self.dispatch_event.set()

        gr = self.refcall_pool.spawn(refcall_fun)
        self.pool.add(gr)
        return gr


def pages_from_metabook(mb):
    articles = mb.articles()
    pages = [(x.title, x.revision) for x in articles]
    return pages
