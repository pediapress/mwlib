#! /usr/bin/env python

# Copyright (c) 2007-2011 PediaPress GmbH
# See README.rst for additional licensing information.

import contextlib
import os
import sys
import time
import traceback
from urllib import parse, request
import re
import gevent
import gevent.event
import gevent.pool
from gevent.lock import Semaphore
from lxml import etree
from sqlitedict import SqliteDict
from hashlib import sha1
import shutil

from mwlib import nshandling
from mwlib.configuration import conf
from mwlib.net import sapi as mwapi
from mwlib.utilities import myjson as json
from mwlib.utilities import utils


class SharedProgress:
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

        percent = done / 5.0 if total < 50 else 100.0 * done / total

        percent = round(percent, 3)

        needed = time.time() - self.stime
        if needed < 60.0:
            percent *= needed / 60.0

        if percent <= self.last_percent:
            percent = self.last_percent

        self.last_percent = percent

        if isatty and isatty():
            msg = f"{done} of {total}, {percent:.2f}%, {needed:.2f} seconds,"
            if sys.platform in ("linux2", "linux3"):
                from mwlib import linuxmem

                msg += " %.1f MB mem used" % linuxmem.resident()
            sys.stdout.write("\x1b[K" + msg + "\r")
            sys.stdout.flush()

        if self.status:
            stdout = ""
            try:
                stdout = self.status.stdout
                self.status.stdout = None
                self.status(status="fetching", progress=percent)
            finally:
                self.status.stdout = stdout

    def set_count(self, key, done, total):
        self.key2count[key] = (done, total)
        self.report()

    def get_count(self):
        done_count = 0
        total_count = 0
        done = 0
        for done, total in self.key2count.values():
            done_count += done
            total_count += total
        return done, total_count


class FsOutput:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        if os.path.exists(self.path):
            raise ValueError(f"output path exists: {self.path}")
        os.makedirs(os.path.join(self.path, "images"))
        self.revfile = open(os.path.join(self.path, "revisions-1.txt"), "w",
                            encoding="utf8")
        self.seen = {}
        self.imgcount = 0
        self.nfo = None

        for storage in ["authors", "html", "imageinfo"]:
            db_path = os.path.join(self.path, storage + ".db")
            if os.path.exists(db_path):
                os.remove(db_path)
            database = SqliteDict(db_path, autocommit=True)
            setattr(self, storage, database)

    def open_rev_file_for_reading(self):
        self.revfile = open(os.path.join(self.path, "revisions-1.txt"), "r",
                            encoding="utf8")

    def set_db_key(self, name, key, value):
        storage = getattr(self, name, None)
        if storage is None:
            raise ValueError(f"storage does not exist {name}")
        storage[key] = json.dumps(value)

    def get_db_key(self, name, key):
        storage = getattr(self, name, None)
        if storage is None:
            raise ValueError(f"storage does not exist {name}")
        return json.loads(storage[key])

    def get_db_keys(self, name):
        storage = getattr(self, name, None)
        if storage is None:
            raise ValueError(f"storage does not exist {name}")
        return storage.keys()

    def close(self):
        if self.nfo is not None:
            self.dump_json(nfo=self.nfo)
        self.revfile.close()
        self.revfile = None

    def get_imagepath(self, title):
        path = os.path.join(self.path, "images", f"{utils.fs_escape(title)}")
        self.imgcount += 1
        return path

    def copy_image(self, image_to_be_copied, new_image_name):
        image_to_be_copied_path = os.path.join(self.path, "images", f"{utils.fs_escape(image_to_be_copied)}")
        new_image_path = os.path.join(self.path, "images", f"{utils.fs_escape(new_image_name)}")
        shutil.copyfile(image_to_be_copied_path, new_image_path)

    def dump_json(self, **kw):
        for key, value in kw.items():
            path = os.path.join(self.path, key + ".json")
            with open(path, "w", encoding="utf8") as out_file:
                json.dump(value, out_file, indent=4, sort_keys=True)

    def write_siteinfo(self, siteinfo):
        self.dump_json(siteinfo=siteinfo)

    def write_excluded(self, excluded):
        self.dump_json(excluded=excluded)

    def write_licenses(self, licenses):
        self.dump_json(licenses=licenses)

    def write_expanded_page(self, title, name_space, txt, revid=None):
        rev = {"title": title, "ns": name_space, "expanded": 1}
        if revid is not None:
            rev["revid"] = revid

        header = "\n --page-- %s\n" % json.dumps(rev, sort_keys=True)
        self.revfile.write(header)
        self.revfile.write(txt)
        self.seen[title] = rev

    def write_pages(self, data):
        pages = list(data.get("pages", {}).values())
        for page in pages:
            title = page.get("title")
            namespace = page.get("ns")
            revisions = page.get("revisions")

            if revisions is None:
                continue

            for revision in revisions:
                revid = revision.get("revid")
                txt = revision["*"]
                if revid not in self.seen:
                    rev = {
                        "title": title,
                        "ns": namespace,
                    }
                    if revid is not None:
                        self.seen[revid] = rev
                        rev["revid"] = revid
                    self.seen[title] = rev

                    header = "\n --page-- %s\n" % json.dumps(rev,
                                                              sort_keys=True)
                    self.revfile.write(header)
                    self.revfile.write(txt)

    def write_authors(self):
        if hasattr(self, "authors"):
            self.authors.close()

    def write_html(self):
        if hasattr(self, "html"):
            self.html.close()

    def write_redirects(self, redirects):
        self.dump_json(redirects=redirects)


def split_blocks(lst, limit):
    """Split list lst in blocks of max.
    limit entries. Return list of blocks."""
    res = []
    start = 0
    while start < len(lst):
        res.append(lst[start: start + limit])
        start += limit
    return res


def get_block(lst, limit):
    """Return first limit entries from list lst and remove them from the list"""

    last_n_elements = lst[-limit:]
    del lst[-limit:]
    return last_n_elements


def call_when(event, fun):
    while True:
        try:
            event.wait()
            event.clear()
            fun()
        except gevent.GreenletExit:
            raise
        except Exception as exc:
            print("call_when", exc)
            traceback.print_exc()


def download_to_file(url, path, temp_path):
    opener = request.build_opener()
    opener.addheaders = [("User-Agent", conf.user_agent)]

    try:
        out = None
        size_read = 0
        remote_file = opener.open(url)
        while True:
            data = remote_file.read(16384)
            if not data:
                break
            size_read += len(data)
            if out is None:
                out = open(temp_path, "wb")
            out.write(data)

        if out is not None:
            out.close()
            os.rename(temp_path, path)
        print(f"read {size_read} bytes from {url}")

    except Exception as err:
        print("ERROR DOWNLOADING", url, err)
        raise


class Fetcher:
    def __init__(
            self,
            api,
            fsout,
            pages,
            licenses,
            status=None,
            progress=None,
            cover_image=None,
            imagesize=800,
            fetch_images=True,
    ):
        self.dispatch_event = gevent.event.Event()
        self.api_semaphore = Semaphore(20)

        self.cover_image = cover_image

        self.pages = pages

        self.image_download_pool = gevent.pool.Pool(10)

        self.fatal_error = "stopped by signal"

        self.api = api
        self.api.report = self.report
        self.api_cache = {
            self.api.apiurl: self.api,
        }

        self.fsout = fsout
        self.licenses = licenses
        self.status = status
        self.progress = progress or SharedProgress(status=status)

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
        self.nshandler = nshandling.NsHandler(siteinfo)

        self.make_print_template = None

        titles, revids = self._split_titles_revids(pages)

        self.pool = gevent.pool.Pool()
        self.refcall_pool = gevent.pool.Pool(1024)

        self._refcall(self.fetch_html, "page", titles)
        self._refcall(self.fetch_html, "oldid", revids)

        self._refcall(self.fetch_used, "titles", titles, True)
        self._refcall(self.fetch_used, "revids", revids, True)

        for title in titles:
            self._refcall(self.expand_templates_from_title, title)

        for rev_id in revids:
            self._refcall(self.expand_templates_from_revid, int(rev_id))

    def expand_templates_from_revid(self, revid):
        res = self.api.do_request(
            action="query", prop="revisions", rvprop="content",
            revids=str(revid)
        )
        page = list(res["pages"].values())[0]

        title = page["title"]
        text = page["revisions"][0]["*"]
        res = self.api.do_request(
            use_post=True, action="expandtemplates", title=title, text=text
        ).get("expandtemplates", {})

        txt = res.get("*")
        if txt:
            redirect = self.nshandler.redirect_matcher(txt)
            if redirect:
                self.redirects[title] = redirect
                self._refcall(self.expand_templates_from_title, redirect)
                self._refcall(self.fetch_used, "titles", [redirect], True)

            self.fsout.write_expanded_page(title, page["ns"], txt, revid=revid)
            self.get_edits(title, revid)

    def expand_templates_from_title(self, title):
        nsnum, _, _ = self.nshandler.splitname(title)

        text = "{{:%s}}" % title if nsnum == 0 else "{{%s}}" % title

        res = self.api.do_request(action="expandtemplates", title=title,
                                  text=text)
        txt = res.get("*")
        if txt:
            self.fsout.write_expanded_page(title, nsnum, txt)
            self.get_edits(title, None)

    def run(self):
        self.report()
        dispatch_gr = gevent.spawn(call_when, self.dispatch_event,
                                   self.dispatch)
        try:
            self.pool.join()
        finally:
            dispatch_gr.kill()

        self.finish()
        self._save_timeline_info()
        if self.imageinfo_todo or self.revids_todo or self.pages_todo:
            raise ValueError("not all items processed")
        
    def _save_timeline_info(self):
        html_content_pages = self.fsout.get_db_keys("html")
        
        
        for page in html_content_pages:
            txt = self.read_page_by_title(page)
            rev_timeline_tag_contents = self.find_timeline_tags_from_rev_content(txt)
            
            html_content = self.fsout.get_db_key("html", page)
            image_nodes = self._get_timeline_images(html_content)
            timeline_image_urls = self.timeline_image_urls(image_nodes)
            
            for (url, rev_timeline_tag_content) in zip(timeline_image_urls, rev_timeline_tag_contents):
                filename = url.rsplit("/", 1)[1]
                digest = self.calculate_hash_from_timeline_content(rev_timeline_tag_content)
                filename_extension = filename.rsplit(".", 1)[1]
                title = self.nshandler.splitname(filename, defaultns=6)[2]
                self.fsout.copy_image(title, f"{digest}.{filename_extension}")
    
    def read_page_by_title(self, target_title):
        self.fsout.open_rev_file_for_reading()
        rev_file_content = self.fsout.revfile.read()
        pages = rev_file_content.split("\n --page-- ")
        for page in pages[1:]:
            header, txt = page.split("\n", 1)
            rev = json.loads(header)
            if rev["title"] == target_title:
                self.fsout.revfile.close()
                return txt
        self.fsout.revfile.close()
        return None

    def calculate_hash_from_timeline_content(self, timeline_content):
        return sha1(timeline_content.encode("utf-8")).hexdigest()

    def find_timeline_tags_from_rev_content(self, content):
        if not content:
            return []
        return re.findall(r'<timeline>(.*?)<\/timeline>', content, re.DOTALL)

    def extension_img_urls(self, image_nodes):
        img_urls = set()
        for img_node in image_nodes:
            src = img_node.get("src")
            frags = src.split("/")
            if len(frags):
                full_url = parse.urljoin(self.api.baseurl, src)
                if img_node.get("class") != "thumbimage" and (
                        "extensions" in src or "math" in src
                ):
                    img_urls.add(full_url)
        return img_urls

    def timeline_image_urls(self, image_nodes):
        img_urls = set()
        for img_node in image_nodes:
            src = img_node.get("src")
            frags = src.split("/")
            if len(frags):
                full_url = parse.urljoin(self.api.baseurl, src)
                img_urls.add(full_url)
        return img_urls
    
    def _get_image_nodes(self, data):
        html = data["text"]["*"]
        root = etree.HTML(html)
        return root.xpath(".//img")
    
    def _get_timeline_images(self, data):
        html = data["text"]["*"]
        root = etree.HTML(html)
        return root.xpath(".//div[contains(@class, 'timeline-wrapper')]/img")

    def fetch_html(self, name, lst):
        def fetch(content):
            with self.api_semaphore:
                kwargs = {name: content}
                res = self.api.do_request(action="parse", redirects="1", **kwargs)
                res[name] = content

            self.fsout.set_db_key("html", content, res)
            image_nodes = self._get_image_nodes(res)
            timeline_nodes = self._get_timeline_images(res)
            img_urls = self.extension_img_urls(image_nodes)
            timeline_image_urls = self.timeline_image_urls(timeline_nodes)
            all_urls = list(set(list(img_urls) + list(timeline_image_urls)))
            for url in all_urls:
                filename = url.rsplit("/", 1)[1]
                title = self.nshandler.splitname(filename, defaultns=6)[2]
                self.schedule_download_image(str(url), title)

        self.count_total += len(lst)
        for item in lst:
            self._refcall_noinc(fetch, item)

    def fetch_used(self, name, lst, expanded=False):
        limit = self.api.api_request_limit
        pool = gevent.pool.Pool()
        blocks = split_blocks(lst, limit)
        self.count_total += len(blocks)
        for block in blocks:
            pool.add(self._refcall_noinc(self.fetch_used_block,
                                         name, block, expanded))
        pool.join()

        if conf.noedits:
            return

        items = list(self.title2latest.items())
        self.title2latest = {}
        self.count_total += len(items)
        for title, rev in items:
            self._refcall_noinc(self.get_edits, title, rev)

    def fetch_used_block(self, name, lst, expanded):
        kwargs = {name: lst, "fetch_images": self.fetch_images,
              "expanded": expanded}
        used = self.api.fetch_used(**kwargs)

        self._update_redirects(used.get("redirects", []))

        pages = list(used.get("pages", {}).values())

        revids = set()
        for page in pages:
            tmp = self._extract_attribute(page.get("revisions", []), "revid")
            if tmp:
                latest = max(tmp)
                title = page.get("title", None)
                old = self.title2latest.get(title, 0)
                self.title2latest[title] = max(old, latest)

            revids.update(tmp)

        templates = set()
        images = set()
        for page in pages:
            images.update(self._extract_title(page.get("images", [])))
            templates.update(self._extract_title(page.get("templates", [])))

        if self.cover_image:
            images.add(self.nshandler.get_fqname(self.cover_image, 6))
            self.cover_image = None

        for image in images:
            if image not in self.scheduled:
                self.imageinfo_todo.append(image)
                self.scheduled.add(image)

        for rev in revids:
            if rev not in self.scheduled:
                self.revids_todo.append(rev)
                self.scheduled.add(rev)

        for template in templates:
            if template not in self.scheduled:
                self.pages_todo.append(template)
                self.scheduled.add(template)

    def get_siteinfo_for(self, api):
        return api.get_siteinfo()

    def _split_titles_revids(self, pages):
        titles = set()
        revids = set()

        for page in pages:
            if page[1] is not None:
                revids.add(page[1])
            else:
                titles.add(page[0])

        titles = sorted(titles)

        revids = list(revids)
        revids.sort()
        return titles, revids

    def get_edits(self, title, rev):
        inspect_authors = self.api.get_edits(title, rev)
        authors = inspect_authors.get_authors()
        self.fsout.set_db_key("authors", title, authors)

    def report(self):
        query_count = self.api.qccount

        limit = self.api.api_request_limit
        job_total = self.count_total + len(self.pages_todo) // limit + len(self.revids_todo) // limit
        job_total += len(self.title2latest)

        self.progress.set_count(self, self.count_done + query_count, job_total + query_count)

    def _add_catmember(self, title, entry):
        try:
            self.cat2members[title].append(entry)
        except KeyError:
            self.cat2members[title] = [entry]

    def _handle_categories(self, data):
        pages = list(data.get("pages", {}).values())
        for page in pages:
            categories = page.get("categories")
            if not categories:
                continue
            page_details = {
                "title": page.get("title"),
                "ns": page.get("ns"),
                "pageid": page.get("pageid"),
            }

            for category in categories:
                cattitle = category.get("title")
                if cattitle:
                    self._add_catmember(cattitle, page_details)

    def _find_redirect(self, data):
        pages = list(data.get("pages", {}).values())
        targets = []
        for page in pages:
            title = page.get("title")
            revisions = page.get("revisions")

            if revisions is None:
                continue

            for rev in revisions:
                txt = rev["*"]
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
        for item in lst:
            attribute_value = item.get(attr)
            if attribute_value:
                res.append(attribute_value)

        return res

    def _extract_title(self, lst):
        return self._extract_attribute(lst, "title")

    def _update_redirects(self, lst):
        for item in lst:
            to_title = item.get("to")
            from_title = item.get("from")
            if to_title and from_title:
                self.redirects[from_title] = to_title

    def schedule_download_image(self, url, title):
        key = (url, title)
        if key in self.scheduled:
            return
        self.scheduled.add(key)
        self._refcall(self._download_image, url, title)

    def _download_image(self, url, title):
        path = self.fsout.get_imagepath(title)
        temp_path = (path + "\xb7").encode("utf-8")
        greenlet_task = self.image_download_pool.spawn(download_to_file, url, path,
                                            temp_path)
        self.pool.add(greenlet_task)

    def fetch_imageinfo(self, titles):
        data = self.api.fetch_imageinfo(titles=titles,
                                        iiurlwidth=self.imagesize)
        infos = list(data.get("pages", {}).values())
        new_base_paths = set()

        for info in infos:
            title = info.get("title")

            image_info = info.get("imageinfo", [])
            if not image_info:
                continue
            image_info = image_info[0]
            self._extract_info_from_image(info, image_info, new_base_paths, title)

        for path in new_base_paths:
            self._refcall(self.handle_new_basepath, path)

    def _extract_info_from_image(self, image, imageinfo,
                                 new_base_paths, title):
        self.fsout.set_db_key("imageinfo", title, imageinfo)
        thumb_url = imageinfo.get("thumburl", None)
        if thumb_url is None:  # fallback for old mediawikis
            thumb_url = imageinfo.get("url", None)
        # FIXME limit number of parallel downloads
        if thumb_url:
            # FIXME: add Callback that checks correct file size
            if thumb_url.startswith("/"):
                thumb_url = parse.urljoin(self.api.baseurl, thumb_url)
            self.schedule_download_image(thumb_url, title)

            description_url = imageinfo.get("descriptionurl", "")
            if not description_url:
                description_url = image.get("fullurl", "")

            if description_url and "/" in description_url:
                path, _ = description_url.rsplit("/", 1)
                title_url_tuple = (title, description_url)
                if path in self.imagedescription_todo:
                    self.imagedescription_todo[path].append(title_url_tuple)
                else:
                    new_base_paths.add(path)
                    self.imagedescription_todo[path] = [title_url_tuple]

    def _get_nshandler(self):
        if self._nshandler is not None:
            return self._nshandler
        return nshandling.get_nshandler_for_lang("en")  # FIXME

    def _set_nshandler(self, nshandler):
        self._nshandler = nshandler

    nshandler = property(_get_nshandler, _set_nshandler)

    def fetch_image_page(self, titles, api):
        data = api.fetch_pages(titles)

        local_nsname = self.nshandler.get_nsname_by_number(6)

        pages = list(data.get("pages", {}).values())
        # change title prefix to make them look like local pages
        for page in pages:
            title = page.get("title")
            _, partial = title.split(":", 1)
            page["title"] = f"{local_nsname}:{partial}"

            revisions = page.get("revisions", [])
            # the revision id's could clash with some local ids. remove them.
            for rev in revisions:
                with contextlib.suppress(KeyError):
                    del rev["revid"]
        # XXX do we also need to handle redirects here?
        self.fsout.write_pages(data)

    def handle_new_basepath(self, path):
        api = self._get_mwapi_for_path(path)
        todo = self.imagedescription_todo[path]
        del self.imagedescription_todo[path]

        titles = {x[0] for x in todo}
        # "-d-" is just some prefix to make the names here
        # not clash with local names
        titles = [t for t in titles if "-d-" + t not in self.scheduled]
        self.scheduled.update(["-d-" + x for x in titles])
        if not titles:
            return

        siteinfo = self.get_siteinfo_for(api)

        ns_handler = nshandling.NsHandler(siteinfo)
        nsname = ns_handler.get_nsname_by_number(6)

        local_names = []
        for title in titles:
            partial = title.split(":", 1)[1]
            local_names.append(f"{nsname}:{partial}")

        for block in split_blocks(local_names, api.api_request_limit):
            self._refcall(self.fetch_image_page, block, api)

        for title in local_names:
            self._refcall(self.get_image_edits, title, api)

    def get_image_edits(self, title, api):
        get_authors = api.get_edits(title, None)
        local_nsname = self.nshandler.get_nsname_by_number(6)
        # change title prefix to make them look like local pages
        _, partial = title.split(":", 1)
        title = f"{local_nsname}:{partial}"
        authors = get_authors.get_authors()
        self.fsout.set_db_key("authors", title, authors)

    def _get_mwapi_for_path(self, path):
        urls = mwapi.guess_api_urls(path)
        for url in urls:
            if url in self.api_cache:
                return self.api_cache[url]
        for url in urls:
            try:
                api = mwapi.MwApi(url)
                api.ping()
                api.set_limit()
                self.api_cache[url] = api
                return api
            except Exception:
                # traceback.print_exc()
                continue

        raise RuntimeError(f"cannot guess api url for {path}")

    def _fetch_pages(self, *args, **kwargs):
        data = self.api.fetch_pages(**kwargs)
        self._find_redirect(data)
        redirects = data.get("redirects", [])
        self._update_redirects(redirects)
        self._handle_categories(data)
        self.fsout.write_pages(data)

    def _doit(self, name, lst, limit):
        while lst and self.api.idle():
            block = get_block(lst, limit)
            self.scheduled.update(block)
            kwargs = {name: block}
            self._refcall(self._fetch_pages, **kwargs)

    def dispatch(self):
        limit = self.api.api_request_limit
        while self.imageinfo_todo and self.api.idle():
            block = get_block(self.imageinfo_todo, limit)
            self.scheduled.update(block)
            self._refcall(self.fetch_imageinfo, block)
        self._doit("revids", self.revids_todo, limit)
        self._doit("titles", self.pages_todo, limit)        
        self.report()

    def _sanity_check(self):
        seen = self.fsout.seen
        for title, revid in self.pages:
            if revid is not None and revid in seen:
                continue

            fully_qualified_name = self.nshandler.get_fqname(title)
            if fully_qualified_name in seen or self.redirects.get(fully_qualified_name, fully_qualified_name) in seen:
                continue
            print(f"WARNING: {title, revid} could not be fetched")

    def finish(self):
        self._sanity_check()
        self.fsout.write_redirects(self.redirects)
        self.fsout.write_licenses(self.licenses)
        self.fsout.close()

    def _refcall(self, fun, *args, **kw):
        """Increment refcount, schedule call of fun
        decrement refcount after fun has finished.
        """
        self.count_total += 1
        self.report()
        return self._refcall_noinc(fun, *args, **kw)

    def _refcall_noinc(self, fun, *args, **kwargs):
        def refcall_fun():
            try:
                fun(*args, **kwargs)
            finally:
                self.count_done += 1
                self.dispatch_event.set()

        greenlet_instance = self.refcall_pool.spawn(refcall_fun)
        self.pool.add(greenlet_instance)
        return greenlet_instance


def pages_from_metabook(meta_book):
    articles = meta_book.articles()
    pages = [(article.title, article.revision) for article in articles]
    return pages
