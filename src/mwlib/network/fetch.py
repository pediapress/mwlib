#! /usr/bin/env python

# Copyright (c) 2007-2011 PediaPress GmbH
# See README.rst for additional licensing information.

import contextlib
import logging
import os
import re
import shutil
import sys
import time
import traceback
from collections import defaultdict
from hashlib import sha1
from urllib import parse, request
from urllib.error import HTTPError

import gevent
import gevent.event
import gevent.pool
import httpx
from authlib.integrations.httpx_client import OAuth2Client
from gevent.lock import Semaphore
from lxml import etree
from sqlitedict import SqliteDict

from mwlib.core import nshandling
from mwlib.network import sapi as mwapi
from mwlib.network.http_client import HttpClientManager
from mwlib.network.infobox import DEPRECATED_ALBUM_INFOBOX_PARAMS
from mwlib.network.sapi import MwApi
from mwlib.utils import conf, linuxmem, unorganized
from mwlib.utils import myjson as json

logger = logging.getLogger(__name__)


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
        self.revfile = open(os.path.join(self.path, "revisions-1.txt"), "w", encoding="utf8")  # noqa: SIM115
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
        self.revfile = open(os.path.join(self.path, "revisions-1.txt"), encoding="utf8")  # noqa: SIM115

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
        path = os.path.join(self.path, "images", f"{unorganized.fs_escape(title)}")
        self.imgcount += 1
        return path

    def copy_image(self, image_to_be_copied, new_image_name):
        image_to_be_copied_path = os.path.join(
            self.path, "images", f"{unorganized.fs_escape(image_to_be_copied)}"
        )
        new_image_path = os.path.join(
            self.path, "images", f"{unorganized.fs_escape(new_image_name)}"
        )
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

                    header = "\n --page-- %s\n" % json.dumps(rev, sort_keys=True)
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
    """Split list lst in blocks of max. limit entries. Return list of blocks."""
    res = []
    start = 0
    while start < len(lst):
        res.append(lst[start : start + limit])
        start += limit
    return res


def get_block(lst, limit):
    """Return first limit entries from list lst and remove them from the list."""
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


def download_to_file(url, path, temp_path, max_retries=0, initial_delay=1, backoff_factor=2):
    """Download a file from a URL to a local path with exponential backoff for HTTP 429 errors.

    Args:
        url: URL to download from
        path: Final path where the file should be saved
        temp_path: Temporary path to download to before moving to final path
        max_retries: Maximum number of retries for HTTP 429 errors
        initial_delay: Initial delay in seconds before retrying
        backoff_factor: Factor by which the delay increases with each retry

    """
    # Parse the URL to get the base URL for HTTP/2 detection
    parsed_url = parse.urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    # Check if HTTP/2 is enabled in configuration
    use_http2 = conf.get("http2", "enabled", True, bool)

    # Detect HTTP/2 support if auto-detect is enabled
    http2_auto_detect = conf.get("http2", "auto_detect", True, bool)
    http2_supported = False

    if use_http2 and http2_auto_detect:
        # Use the HttpClientManager to detect HTTP/2 support
        client_manager = HttpClientManager.get_instance()
        http2_supported = client_manager.detect_http2_support(base_url)
        logger.debug(f"HTTP/2 support detected for {base_url}: {http2_supported}")

    # Get a client with appropriate HTTP/2 settings
    client_manager = HttpClientManager.get_instance()
    client = client_manager.get_client(
        base_url=base_url, use_http2=use_http2 and (http2_supported or not http2_auto_detect)
    )
    if isinstance(client, OAuth2Client) and (
        not hasattr(client, "token") or not client.token or client.token.is_expired()
    ):
        client.fetch_token()

    retry_count = 0
    delay = initial_delay

    while True:
        try:
            size_read = 0
            # Use httpx streaming to download the file in chunks
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(temp_path, "wb") as out:
                    for chunk in response.iter_bytes(chunk_size=16384):
                        size_read += len(chunk)
                        out.write(chunk)

            logger.debug(f"read {size_read} bytes from {url}")
            os.rename(temp_path, path)
            return  # Success, exit the retry loop

        except httpx.HTTPStatusError as err:
            if err.response.status_code == 429 and retry_count < max_retries:
                retry_count += 1
                logger.warning(
                    f"Received HTTP 429 (Too Many Requests) for {url}. Retrying in {delay} seconds. Retry {retry_count}/{max_retries}"
                )
                time.sleep(delay)
                delay *= backoff_factor  # Exponential backoff
            else:
                # Either not a 429 error or we've exceeded max retries
                logger.info(f"ERROR DOWNLOADING {url}: {err}")
                raise
        except Exception as err:
            logger.info(f"ERROR DOWNLOADING {url}: {err}")
            raise


class Fetcher:
    titles_pending_contributor_lookup = defaultdict(list)
    title_mapping = {}

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

        # store revisions in memory for later use
        # KLUDGE: in memory storage might fail for very large collections
        self.revisions = []

    def lower_infobox_parameters(self, text):
        parameters_to_lower = {
            "| Type": "| type",
            "| Label": "| label",
            "| Released": "| released",
            "| Artist": "| artist",
            "| Name": "| name",
            "| Cover": "| cover",
            "| Producer": "| producer",
            "| Length": "| length",
            "| Recorded": "| recorded",
            "| Genre": "| genre",
        }

        delete_pattern = r"^\|\s*(?:This album|Last album|Next album).*\n"
        text = re.sub(delete_pattern, "", text, flags=re.MULTILINE)

        for old_param, new_param in parameters_to_lower.items():
            text = re.sub(rf"({re.escape(old_param)})\s*=", f"{new_param} =", text)
        return text

    def update_infobox_parameters(self, text):
        parameters = DEPRECATED_ALBUM_INFOBOX_PARAMS
        escaped_parameters = [re.escape(param) for param in parameters]
        delete_pattern = r"^\|\s*(?:" + "|".join(escaped_parameters) + r")\s*=\s*.*\n"
        text = re.sub(delete_pattern, "", text, flags=re.MULTILINE)

        return text

    def expand_templates_from_revid(self, revid):
        res = self.api.do_request(
            action="query", prop="revisions", rvprop="content", revids=str(revid)
        )
        page = list(res["pages"].values())[0]

        title = page["title"]
        text = page["revisions"][0]["*"]
        text = self.lower_infobox_parameters(text)
        text = self.update_infobox_parameters(text)
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
            self.get_edits(title)

    def expand_templates_from_title(self, title):
        nsnum, _, _ = self.nshandler.splitname(title)

        text = "{{:%s}}" % title if nsnum == 0 else "{{%s}}" % title

        # produces deprecated output format, might have to add prop param and handle output
        # check https://commons.wikimedia.org/w/api.php?action=help&modules=expandtemplates
        res = self.api.do_request(action="expandtemplates", title=title, text=text)
        txt = res.get("*")
        if txt:
            self.fsout.write_expanded_page(title, nsnum, txt)
            self.get_edits(title)

    def run(self):
        self.report()
        dispatch_gr = gevent.spawn(call_when, self.dispatch_event, self.dispatch)
        try:
            self.pool.join()
        finally:
            dispatch_gr.kill()

        self.finish()
        self._save_timeline_info()
        self._save_map_frame_image_info()
        if self.imageinfo_todo or self.revids_todo or self.pages_todo:
            raise ValueError("not all items processed")

    def _save_timeline_info(self):
        html_content_pages = self.fsout.get_db_keys("html")

        for page in html_content_pages:
            txt = self.find_source_by_title_or_revid(page)
            rev_timeline_tag_contents = self.find_timeline_tags_from_rev_content(txt)

            html_content = self.fsout.get_db_key("html", page)
            image_nodes = self._get_timeline_image_nodes(html_content)
            timeline_image_urls = self.timeline_image_urls(image_nodes)

            for url, rev_timeline_tag_content in zip(
                timeline_image_urls, rev_timeline_tag_contents, strict=False
            ):
                filename = url.rsplit("/", 1)[1]
                digest = self.calculate_hash_from_timeline_content(rev_timeline_tag_content)
                filename_extension = filename.rsplit(".", 1)[1]
                title = self.nshandler.splitname(filename, defaultns=6)[2]
                self.fsout.copy_image(title, f"{digest}.{filename_extension}")

    def _save_map_frame_image_info(self):
        html_content_pages = self.fsout.get_db_keys("html")

        for page in html_content_pages:
            txt = self.find_source_by_title_or_revid(page)
            rev_map_frame_tag_contents = self.find_map_frame_tags_from_rev_content(txt)

            html_content = self.fsout.get_db_key("html", page)
            image_nodes = self._get_map_image_nodes(html_content)
            map_image_urls = self.map_image_urls(image_nodes)

            for url, rev_map_tag_content in zip(
                map_image_urls, rev_map_frame_tag_contents, strict=False
            ):
                filename = url.rsplit("/", 1)[1]
                filename = filename.split("?")[0]
                digest = self.calculate_hash_from_map_content(rev_map_tag_content)
                filename_extension = filename.rsplit(".", 1)[1]
                title = self.nshandler.splitname(filename, defaultns=6)[2]
                self.fsout.copy_image(title, f"{digest}.{filename_extension}")

    def find_source_by_title_or_revid(self, title_or_revid):
        title = int(title_or_revid) if title_or_revid.isdigit() else title_or_revid
        if not self.revisions:
            self.fsout.open_rev_file_for_reading()
            rev_file_content = self.fsout.revfile.read()
            pages = rev_file_content.split("\n --page-- ")
            for page in pages[1:]:
                header, txt = page.split("\n", 1)
                rev = json.loads(header)
                rev["text"] = txt
                self.revisions.append(rev)
            self.fsout.revfile.close()
        result = [r for r in self.revisions if r.get("title") == title or r.get("revid") == title]
        if result:
            return result[0]["text"]

    def calculate_hash_from_timeline_content(self, timeline_content):
        return sha1(timeline_content.encode("utf-8")).hexdigest()

    def calculate_hash_from_map_content(self, map_content_attributes):
        height = map_content_attributes.get("height", "")
        width = map_content_attributes.get("width", "")
        latitude = map_content_attributes.get("latitude", "")
        longitude = map_content_attributes.get("longitude", "")
        zoom = map_content_attributes.get("zoom", "")
        identifier = f"{height}x{width}x{latitude}x{longitude}x{zoom}"
        digest = sha1()
        digest.update(identifier.encode("utf8"))
        ident = digest.hexdigest()
        return ident

    def find_timeline_tags_from_rev_content(self, content):
        if not content:
            return []
        return re.findall(r"<timeline>(.*?)<\/timeline>", content, re.DOTALL)

    def find_map_frame_tags_from_rev_content(self, content):
        if not content:
            return []
        mapframes = re.findall(r"<mapframe(.*?)>", content, re.DOTALL)

        mapframes_with_attributes = []

        for map_frame in mapframes:
            attributes = self.extract_attributes_from_map_frame_tag(map_frame)
            if not attributes:
                continue
            map_frame_content = re.search(
                r"<div class=\"mw-kartographer-map\"(.*?)<\/div>", content, re.DOTALL
            )
            if map_frame_content:
                attributes.append(map_frame_content.group(1))
            attributes_dict = {}
            for key, value in attributes:
                attributes_dict[key] = value
            mapframes_with_attributes.append(attributes_dict)
        return mapframes_with_attributes

    def extract_attributes_from_map_frame_tag(self, tag):
        return re.findall(r'(\w+)\s*=\s*"(.*?)"', tag)

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

    def map_image_urls(self, image_nodes):
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

    def _get_timeline_image_nodes(self, data):
        html = data["text"]["*"]
        root = etree.HTML(html)
        return root.xpath(".//div[contains(@class, 'timeline-wrapper')]/img")

    def _get_map_image_nodes(self, data):
        html = data["text"]["*"]
        root = etree.HTML(html)
        return root.xpath(".//a[contains(@class, 'mw-kartographer-map')]/img")

    def fetch_html(self, name, lst):
        def fetch(content):
            with self.api_semaphore:
                kwargs = {name: content}
                res = self.api.do_request(action="parse", redirects="1", **kwargs)
                res[name] = content

            self.fsout.set_db_key("html", content, res)
            image_nodes = self._get_image_nodes(res)
            timeline_nodes = self._get_timeline_image_nodes(res)
            map_nodes = self._get_map_image_nodes(res)
            img_urls = self.extension_img_urls(image_nodes)
            timeline_image_urls = self.timeline_image_urls(timeline_nodes)
            map_image_urls = self.map_image_urls(map_nodes)
            all_urls = list(set(list(img_urls) + list(timeline_image_urls)))
            for url in all_urls:
                filename = url.rsplit("/", 1)[1]
                title = self.nshandler.splitname(filename, defaultns=6)[2]
                self.schedule_download_image(str(url), title)
            for url in map_image_urls:
                filename = url.rsplit("/", 1)[1]
                filename = filename.split("?")[0]
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
            pool.add(self._refcall_noinc(self.fetch_used_block, name, block, expanded))
        pool.join()

        if conf.noedits:
            return

        items = list(self.title2latest.items())
        self.title2latest = {}
        self.count_total += len(items)
        for title, rev in items:
            self._refcall_noinc(self.get_edits, title, rev)

    def fetch_used_block(self, name, lst, expanded):
        kwargs = {name: lst, "fetch_images": self.fetch_images, "expanded": expanded}
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

    def get_edits(self, title):
        """Get contributors for a given page title.

        This method is now a wrapper around _add_to_titles_pending_contributor_lookup,
        which collects titles for batched processing. The actual API request is made
        when the batch is full or when explicitly flushed.

        Args:
            title (str): Title of the page to get edit history for

        """
        # Add the title to the batch
        self._add_to_titles_pending_contributor_lookup(title, self.api)

    def _add_to_titles_pending_contributor_lookup(self, title, api: MwApi):
        """Add a title to the authors batch for processing.

        If the batch reaches the API request limit, it will be processed automatically.

        Args:
            title (str): Title of the page to add to the batch
            api (MwApi): MwApi instance

        """
        if not api:
            api = self.api
        # Add the title to the batch
        self.titles_pending_contributor_lookup[api].append(title)

        # Process the batch if it reaches the API request limit
        if len(self.titles_pending_contributor_lookup[api]) >= 50:  # MediaWiki API allows up to 50 titles per request
            self._lookup_contributors(api)

    def _lookup_contributors(self, api: MwApi) -> None:
        """Process the current batch of titles for author information.

        This method makes a single API request for all titles in the batch,
        then processes the results and stores them in the database.
        """
        # Make the API request for all titles in the batch
        title_to_authors = api.get_contributors(self.titles_pending_contributor_lookup[api])

        # Process the results for each title
        authors_dict = {}
        title: str
        for title in self.titles_pending_contributor_lookup[api]:
            # Skip if the title is not in the results (e.g., if it was redirected)
            if title not in title_to_authors:
                continue

            # Get the InspectAuthors object for this title
            inspect_authors = title_to_authors[title]

            # Get the authors for this title
            authors = inspect_authors.get_authors()

            # Use the mapped title if available (for image pages)
            db_title = title
            if title in self.title_mapping:
                db_title = self.title_mapping[title]

            # Store the authors in the database
            self.fsout.set_db_key("authors", db_title, authors)

            # Store the authors in a dictionary for future use
            authors_dict[title] = authors

        # Clear the batch
        self.authors_batch = []


    def report(self):
        query_count = self.api.qccount

        limit = self.api.api_request_limit
        job_total = (
            self.count_total + len(self.pages_todo) // limit + len(self.revids_todo) // limit
        )
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
        greenlet_task = self.image_download_pool.spawn(download_to_file, url, path, temp_path)
        self.pool.add(greenlet_task)

    def fetch_imageinfo(self, titles):
        """Fetch and process image information for given titles.

        This method retrieves image information from the MediaWiki API for the specified titles,
        including thumbnails and description URLs. It processes the retrieved data by:
        1. Extracting image info and storing it in the output
        2. Scheduling thumbnail downloads
        3. Collecting base paths for image descriptions

        Args:
            titles: List of image titles to fetch information for

        The method handles the scheduling of image downloads and triggers processing of
        description pages through handle_new_basepath().

        """
        data = self.api.fetch_imageinfo(titles=titles, iiurlwidth=self.imagesize)
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

    def _extract_info_from_image(self, image, imageinfo, new_base_paths, title):
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

    def get_image_edits(self, title: str, api: MwApi):
        """Get edit history for an image page.

        This method is now a wrapper around _add_to_authors_batch, which collects titles
        for batched processing. The actual API request is made when the batch is full
        or when explicitly flushed.

        Args:
            title (str): Title of the image page to get edit history for
            api (MwApi): API instance to use for the request

        """
        local_nsname = self.nshandler.get_nsname_by_number(6)
        # change title prefix to make them look like local pages
        _, partial = title.split(":", 1)
        local_title = f"{local_nsname}:{partial}"

        # Add the title to the batch
        self._add_to_titles_pending_contributor_lookup(title, api)

        # Map the original title to the local title for later use
        self.title_mapping[title] = local_title

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
        """Dispatch all requests to the appropriate handlers."""
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
            if (
                fully_qualified_name in seen
                or self.redirects.get(fully_qualified_name, fully_qualified_name) in seen
            ):
                continue
            print(f"WARNING: {title, revid} could not be fetched")

    def lookup_contributors_for_remaining_titles(self):
        """Flush any pending authors batch.

        This method should be called at the end of processing to ensure that
        all authors are processed and stored.
        """
        for api in self.titles_pending_contributor_lookup:
            if self.titles_pending_contributor_lookup[api]:
                self._lookup_contributors(api)

    def finish(self):
        self._sanity_check()
        # Process any pending authors batch
        self.lookup_contributors_for_remaining_titles()
        for api in self.titles_pending_contributor_lookup:
            logger.info(f"did {api.request_counter} requests to {api.baseurl}")
        self.fsout.write_redirects(self.redirects)
        self.fsout.write_licenses(self.licenses)
        self.fsout.close()

    def _refcall(self, fun, *args, **kw):
        """Increment refcount, schedule call of fun and decrement refcount after fun has finished."""
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
    articles = meta_book.get_articles()
    pages = [(article.title, article.revision) for article in articles]
    return pages
