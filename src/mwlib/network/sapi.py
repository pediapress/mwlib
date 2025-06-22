#! /usr/bin/env python

# Copyright (c) PediaPress GmbH

"""api.php client"""
import logging
import time
from http import cookiejar
from urllib import parse, request
from urllib.error import HTTPError, URLError

try:
    import simplejson as json
except ImportError:
    import json

from gevent.lock import Semaphore

from mwlib.core import authors
from mwlib.utils import conf

logger = logging.getLogger(__name__)





def loads(input_string):
    """Potentially remove UTF-8 BOM and call json.loads()"""

    if (
        input_string
        and isinstance(input_string, str)
        and input_string[:3] == "\xef\xbb\xbf"
    ):
        input_string = input_string[3:]
    return json.loads(input_string)


def merge_data(dst, src):
    todo = [(dst, src)]
    while todo:
        dst, src = todo.pop()
        if not isinstance(dst, type(src)):
            raise ValueError(f"cannot merge {type(dst)!r} with {type(src)!r}")

        if isinstance(dst, list):
            dst.extend(src)
        elif isinstance(dst, dict):
            for k, val in src.items():
                if k in dst:
                    todo.append((dst[k], val))
                else:
                    dst[k] = val


class MwApi:
    def __init__(self, apiurl, username=None, password=None):
        self.apiurl = apiurl
        self.baseurl = apiurl  # XXX

        if username:
            passman = request.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None, apiurl, username, password)
            auth_handler = request.HTTPBasicAuthHandler(passman)
            self.opener = request.build_opener(
                request.HTTPCookieProcessor(cookiejar.CookieJar()),
                auth_handler,
            )
        else:
            self.opener = request.build_opener(
                request.HTTPCookieProcessor(cookiejar.CookieJar())
            )
        self.opener.addheaders = [("User-Agent", conf.user_agent)]
        self.edittoken = None
        self.qccount = 0
        self.api_result_limit = conf.get("fetch", "api_result_limit", 500, int)
        self.api_request_limit = conf.get("fetch", "api_request_limit", 15, int)
        self.max_connections = conf.get("fetch", "max_connections", 20, int)
        self.max_retry_count = conf.get("fetch", "max_retry_count", 2, int)
        self.rvlimit = conf.get("fetch", "rvlimit", 500, int)
        self.limit_fetch_semaphore = None

    def report(self):
        """dummy method for compatibility with sapi"""
        pass

    def set_limit(self, limit=None):
        if self.limit_fetch_semaphore is not None:
            raise ValueError("limit already set")

        if limit is None:
            limit = self.api_request_limit

        self.limit_fetch_semaphore = Semaphore(limit)

    def __repr__(self):
        return f"<mwapi {self.apiurl} at {hex(id(self))}>"

    def _get_url_display(self, url):
        """Get a string representation of the URL for logging purposes."""
        return url.full_url if hasattr(url, 'full_url') else url

    def _should_retry(self, error_type, error_code=None, retry_count=0, max_retries=5):
        """Determine if a request should be retried based on the error type and retry count."""
        if retry_count >= max_retries:
            return False

        if error_type == 'http':
            # Retry on rate limiting (429) or server errors (5xx)
            return error_code == 429 or (500 <= error_code < 600)
        elif error_type == 'url':
            # Always retry URLErrors (connection issues) if we haven't exceeded max_retries
            return True

        # Don't retry other types of errors
        return False

    def _handle_retry(self, url, error_type, error_detail, retry_count, max_retries, delay, backoff_factor):
        """Handle retry logic including logging and sleeping."""
        url_display = self._get_url_display(url)

        if error_type == 'http':
            if error_detail == 429:
                logger.warning(f"Rate limit exceeded (HTTP 429) for {url_display}. "
                              f"Retrying in {delay} seconds. Retry {retry_count}/{max_retries}")
            else:
                logger.warning(f"Server error {error_detail} for {url_display}. "
                              f"Retrying in {delay} seconds. Retry {retry_count}/{max_retries}")
        elif error_type == 'url':
            logger.warning(f"URL error {error_detail} for {url_display}. "
                          f"Retrying in {delay} seconds. Retry {retry_count}/{max_retries}")

        time.sleep(delay)
        return delay * backoff_factor  # Return the new delay with exponential backoff

    def _log_error(self, url, error_type, error_detail, max_retries=None):
        """Log an error that won't be retried."""
        url_display = self._get_url_display(url)

        if error_type == 'http':
            logger.error(f"HTTP error {error_detail} for {url_display}")
        elif error_type == 'url':
            logger.error(f"URL error {error_detail} for {url_display} after {max_retries} retries")
        else:
            logger.error(f"Error fetching {url_display}: {error_detail}")

    def _fetch(self, url, max_retries=5, initial_delay=1, backoff_factor=2):
        """Fetch data from a URL with exponential backoff for transient errors.

        Args:
            url: URL to fetch (string or Request object)
            max_retries: Maximum number of retries for transient errors
            initial_delay: Initial delay in seconds before retrying
            backoff_factor: Factor by which the delay increases with each retry

        Returns:
            The data fetched from the URL

        Raises:
            HTTPError: For non-transient HTTP errors
            URLError: For non-transient URL errors
            Other exceptions that might be raised by urllib.request
        """
        if isinstance(url, str):
            logger.debug("fetching url: %r", url)
            url = request.Request(url)
            url.add_header("Referer", 'https://pediapress.com')

        retry_count = 0
        delay = initial_delay

        while True:
            try:
                url_opener = self.opener.open(url)
                data = url_opener.read()
                url_opener.close()
                return data

            except HTTPError as err:
                if self._should_retry('http', err.code, retry_count, max_retries):
                    retry_count += 1
                    delay = self._handle_retry(url, 'http', err.code, retry_count, max_retries, delay, backoff_factor)
                else:
                    self._log_error(url, 'http', err.code)
                    raise

            except URLError as err:
                if self._should_retry('url', retry_count=retry_count, max_retries=max_retries):
                    retry_count += 1
                    delay = self._handle_retry(url, 'url', err.reason, retry_count, max_retries, delay, backoff_factor)
                else:
                    self._log_error(url, 'url', err.reason, max_retries)
                    raise

            except Exception as err:
                # For other exceptions, log and re-raise
                self._log_error(url, 'other', err)
                raise

    def _build_url(self, **kwargs):
        args = {"format": "json"}
        args.update(**kwargs)
        for k, val in args.items():
            if isinstance(val, str):
                args[k] = val.encode("utf-8")
        query = parse.urlencode(args)
        query = query.replace("%3A", ":")  # fix for wrong quoting of url for images
        query = query.replace(
            "%7C", "|"
        )  # fix for wrong quoting of API queries (relevant for redirects)

        url = f"{self.apiurl}?{query}"
        return url

    def _request(self, **kwargs):
        url = self._build_url(**kwargs)
        return self._fetch(url)

    def _post(self, **kwargs):
        args = {"format": "json"}
        args.update(**kwargs)
        for k, val in args.items():
            if isinstance(val, str):
                args[k] = val.encode("utf-8")

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        postdata = parse.urlencode(args).encode()

        logger.debug("posting to %r", self.apiurl)
        req = request.Request(self.apiurl, postdata, headers)
        req.add_header("Referer", 'https://pediapress.com')
        res = loads(self._fetch(req))
        return res

    def do_request(self, use_post=False, **kwargs):
        sem = self.limit_fetch_semaphore
        if sem is not None:
            sem.acquire()

        try:
            if use_post:
                return self._post(**kwargs)
            return self._do_request(**kwargs)
        finally:
            if sem is not None:
                sem.release()

    def _handle_error(self, error, kwargs):
        error_info = (error.get("info", ""),)
        raise RuntimeError(f"{error_info}: [fetching {self._build_url(**kwargs)}]")

    def _handle_request(self, **kwargs):
        data = loads(self._request(**kwargs))
        error = data.get("error")
        if error:
            self._handle_error(error, kwargs)
        return data

    def _merge_data(self, retval, action, data):
        merge_data(retval, data[action])

    def _handle_query_continue(self, query_continue_data, last_qc, kwargs):
        self.qccount += 1
        self.report()
        new_kw = kwargs.copy()
        for query_dict in query_continue_data:
            for k, value in query_dict.items():
                new_kw[str(k)] = value

        if query_continue_data == last_qc:
            print("warning: cannot continue this query:", self._build_url(**new_kw))
            return None, True

        return new_kw, False

    def _do_request(self, query_continue=True, merge_data=None, **kwargs):
        last_qc = None
        action = kwargs["action"]
        retval = {}
        todo = kwargs

        while todo is not None:
            kwargs = todo
            todo = None

            data = self._handle_request(**kwargs)

            if merge_data:
                merge_data(retval, data[action])
            else:
                self._merge_data(retval, action, data)

            qc_values = list(data.get("query-continue", {}).values())
            if qc_values and query_continue:
                todo, stop_query = self._handle_query_continue(
                    qc_values, last_qc, kwargs
                )
                if stop_query:
                    return retval
                last_qc = qc_values

        return retval

    def ping(self):
        return self.do_request(action="query", meta="siteinfo", siprop="general")

    def get_categorymembers(self, cmtitle):
        return self.do_request(
            action="query", list="categorymembers", cmtitle=cmtitle, cmlimit=200
        )

    def get_siteinfo(self):
        siprop = ["general", "namespaces", "interwikimap", "namespacealiases", "magicwords", "rightsinfo"]
        while len(siprop) >= 3:
            try:
                req = self.do_request(
                    action="query", meta="siteinfo", siprop="|".join(siprop)
                )
                return req
            except Exception as err:
                logger.exception(err)
                siprop.pop()
        raise RuntimeError("could not get siteinfo")

    def login(self, username, password, domain=None, lgtoken=None):
        args = {
            "action": "login",
            "lgname": username.encode("utf-8"),
            "lgpassword": password.encode("utf-8"),
            "format": "json",
        }

        if domain is not None:
            args["lgdomain"] = domain.encode("utf-8")

        if lgtoken is not None:
            args["lgtoken"] = lgtoken.encode("utf-8")

        res = self._post(**args)

        login_result = res["login"]["result"]
        if login_result == "NeedToken" and lgtoken is None:
            return self.login(
                username, password, domain=domain, lgtoken=res["login"]["token"]
            )
        if login_result == "Success":
            return None

        raise RuntimeError("login failed: %r" % res)

    def fetch_used(self, titles=None, revids=None, fetch_images=True, expanded=False):
        if fetch_images:
            prop = "images" if expanded else "revisions|templates|images"
        else:
            prop = "" if expanded else "revisions|templates"

        kwargs = {
            "prop": prop,
            "rvprop": "ids",
            "imlimit": self.api_result_limit,
            "tllimit": self.api_result_limit,
        }
        if titles:
            kwargs["redirects"] = 1

        self._update_kwargs(kwargs, titles, revids)
        return self.do_request(action="query", **kwargs)

    def _update_kwargs(self, kwargs, titles, revids):
        if not titles and not revids:
            raise ValueError("either titles or revids must be set")

        if titles:
            kwargs["titles"] = "|".join(titles)
        if revids:
            kwargs["revids"] = "|".join([str(x) for x in revids])

    def upload(self, title, txt, summary):
        if self.edittoken is None:
            res = self.do_request(
                action="query", prop="info|revisions", intoken="edit", titles=title
            )
            self.edittoken = list(res["pages"].values())[0]["edittoken"]

        self._post(
            action="edit",
            title=title,
            text=txt,
            token=self.edittoken,
            summary=summary,
            format="json",
            bot=True,
        )

    def idle(self):
        sem = self.limit_fetch_semaphore
        if sem is None:
            return True
        return not sem.locked()

    def fetch_pages(self, titles=None, revids=None):
        kwargs = {
            "prop": "revisions",
            "rvprop": "ids|content|timestamp|user",
            "imlimit": self.api_result_limit,
            "tllimit": self.api_result_limit,
        }
        if titles:
            kwargs["redirects"] = 1

        self._update_kwargs(kwargs, titles, revids)

        rev_result = self.do_request(action="query", **kwargs)

        kwargs = {"prop": "categories", "cllimit": self.api_result_limit}
        if titles:
            kwargs["redirects"] = 1

        self._update_kwargs(kwargs, titles, revids)
        cat_result = self.do_request(action="query", **kwargs)
        merge_data(rev_result, cat_result)
        return rev_result

    def fetch_imageinfo(self, titles, iiurlwidth=800):
        kwargs = {
            "prop": "imageinfo|info",
            "iiprop": "url|user|comment|url|sha1|size",
            "iiurlwidth": iiurlwidth,
            "inprop": "url",
        }

        self._update_kwargs(kwargs, titles, [])
        return self.do_request(action="query", **kwargs)

    def get_edits(self, title, revision, rvlimit=None):
        rvlimit = rvlimit or self.rvlimit
        kwargs = {
            "titles": title,
            "redirects": 1,
            "prop": "revisions",
            "rvprop": "ids|user|flags|comment|size",
            "rvlimit": rvlimit,
            "rvdir": "older",
        }
        if revision is not None:
            kwargs["rvstartid"] = revision

        get_authors = authors.InspectAuthors()

        def merge_data(_, newdata):
            edits = list(newdata["pages"].values())
            for edit in edits:
                revs = edit["revisions"]
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
    if isinstance(url, bytes):
        url = url.decode("utf-8")

    try:
        scheme, netloc, path, _, _, _ = parse.urlparse(url)
    except ValueError:
        return retval

    if not (scheme and netloc):
        return retval

    if isinstance(path, bytes):
        path = path.decode("utf-8")

    if path.endswith("/wiki"):
        retval.append(f"{scheme}://{netloc}/w/api.php")

    path_prefix = ""
    if "/wiki/" in str(path):
        path_prefix = path[: path.find("/wiki/")]
    elif "/w/" in path:
        path_prefix = path[: path.find("/w/")]

    prefix = f"{scheme}://{netloc}{path_prefix}"

    if not url.endswith("/"):
        url += "/"

    for _path in (path + "/", "/w/", "/wiki/", "/"):
        base_url = f"{prefix}{_path}sapi.php"
        if base_url not in retval:
            retval.append(base_url)
    if url.endswith("/index.php"):
        retval.append(url[: -len("index.php")] + "api.php")
    if not url.endswith("api.php"):
        retval.append(f"{url}api.php")
    return retval


def main():
    mw_api = MwApi("https://en.wikipedia.org/w/api.php")
    print(mw_api.get_categorymembers("Category:Mainz"))


if __name__ == "__main__":
    main()
