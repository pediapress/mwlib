#! /usr/bin/env python

# Copyright (c) PediaPress GmbH

"""api.php client."""

import logging
import random
import time
from collections import deque
from http import cookiejar
from urllib import parse
from urllib.error import HTTPError, URLError

try:
    import simplejson as json
except ImportError:
    import json

import httpx
from gevent.lock import Semaphore

from mwlib.core import authors
from mwlib.network import api as network_api
from mwlib.network import auth as network_auth
from mwlib.network.http_client import HttpClientManager
from mwlib.utils import conf

logger = logging.getLogger(__name__)


def loads(input_string):
    """Potentially remove UTF-8 BOM and call json.loads()."""
    if input_string and isinstance(input_string, str) and input_string[:3] == "\xef\xbb\xbf":
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


class RateLimiter:
    """Token-bucket rate limiter for gevent-based concurrency.

    Limits the number of operations allowed within a sliding time window.
    """

    def __init__(self, max_calls: int, period: float = 1.0):
        """Initialize the rate limiter.

        Args:
            max_calls: Maximum number of calls allowed within the period.
            period: Time window in seconds (default: 1.0).

        """
        self._max_calls = max_calls
        self._period = period
        self._timestamps: deque[float] = deque()
        self._lock = Semaphore(1)

    def acquire(self):
        """Block until a request is allowed under the rate limit."""
        while True:
            with self._lock:
                now = time.monotonic()
                # Remove timestamps outside the sliding window
                while self._timestamps and self._timestamps[0] <= now - self._period:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._max_calls:
                    self._timestamps.append(now)
                    return

                # Calculate how long to wait until the oldest entry expires
                wait_time = self._period - (now - self._timestamps[0])

            time.sleep(max(wait_time, 0.01))


class MwApi:
    # Track domains and their token expiration timestamps
    _token_info = {}  # Format: {domain: {'token': token, 'expires_at': timestamp}}
    request_counter = 0
    _rate_limiters = {}  # Format: {origin: RateLimiter}
    _rate_limiter_rps = {}  # Format: {origin: max_rps}
    _rate_limiter_lock = Semaphore(1)

    def __init__(self, apiurl, username=None, password=None, use_oauth2=None, use_http2=None):
        self.apiurl = apiurl
        self.baseurl = apiurl  # XXX

        # Determine whether to use OAuth2 and HTTP/2 from configuration if not specified
        self.use_oauth2 = (
            use_oauth2 if use_oauth2 is not None else conf.get("oauth2", "enabled", False, bool)
        )
        self.use_http2 = (
            use_http2 if use_http2 is not None else conf.get("http2", "enabled", True, bool)
        )

        # Get HTTP client from manager
        self.http_client = HttpClientManager.get_instance().get_client(
            self.apiurl, use_oauth2=self.use_oauth2, use_http2=self.use_http2
        )

        # Set basic auth if username is provided and OAuth2 is not enabled
        if username and not self.use_oauth2:
            self.http_client.auth = httpx.BasicAuth(username, password or "")

        self.edittoken = None
        self.qccount = 0
        self.api_result_limit = conf.get("fetch", "api_result_limit", 500, int)
        self.api_request_limit = conf.get("fetch", "api_request_limit", 15, int)
        self.max_connections = conf.get("fetch", "max_connections", 20, int)
        self.max_retry_count = conf.get("fetch", "max_retry_count", 2, int)
        self.rvlimit = conf.get("fetch", "rvlimit", 500, int)
        self.limit_fetch_semaphore = None

    def report(self):
        """Guarantee compatibility with sapi using this placeholder method."""
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
        # With httpx, we're always using string URLs
        return url

    def _origin(self, url):
        parsed = parse.urlparse(str(url))
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        parsed_api = parse.urlparse(str(self.apiurl))
        return f"{parsed_api.scheme}://{parsed_api.netloc}"

    def _acquire_rate_limit(self, url):
        max_rps = conf.get("fetch", "max_requests_per_second", 0, int)
        if max_rps <= 0:
            return

        origin = self._origin(url)
        with MwApi._rate_limiter_lock:
            limiter = MwApi._rate_limiters.get(origin)
            limiter_rps = MwApi._rate_limiter_rps.get(origin)
            if limiter is None or limiter_rps != max_rps:
                limiter = RateLimiter(max_calls=max_rps, period=1.0)
                MwApi._rate_limiters[origin] = limiter
                MwApi._rate_limiter_rps[origin] = max_rps
                logger.info(
                    f"Rate limiter initialized for {origin}: {max_rps} requests/second"
                )

        limiter.acquire()

    def _normalize_http_method(self, method):
        method_normalized = method.upper()
        if method_normalized not in {"GET", "POST"}:
            raise ValueError(f"Unsupported HTTP method: {method}")
        return method_normalized

    def _build_request_headers(self, headers=None):
        request_headers = dict(self.http_client.headers)
        has_referer = any(key.lower() == "referer" for key in request_headers)
        if not has_referer:
            request_headers["Referer"] = "https://pediapress.com"
        if headers:
            request_headers.update(headers)

        if self.use_oauth2:
            token = getattr(self.http_client, "token", None)
            if token and "access_token" in token:
                request_headers["Authorization"] = f"Bearer {token['access_token']}"

        return request_headers

    def _send_http_request(self, method, url, data, request_headers):
        if method == "POST":
            response = self.http_client.post(url, data=data, headers=request_headers)
        else:
            response = self.http_client.get(url, headers=request_headers)
        response.raise_for_status()
        return response.content

    def _retry_or_raise(self, *, url, error, retry_state, retry_policy):
        return network_api.retry_or_raise(
            url=url,
            error=error,
            retry_state=retry_state,
            retry_policy=retry_policy,
            logger=logger,
            sleep_fn=time.sleep,
            uniform_fn=random.uniform,
        )

    def _classify_retryable_fetch_error(self, url, err):
        return network_api.classify_retryable_fetch_error(url, err, logger=logger)

    def _build_retry_policy(self, max_retries, backoff_factor, jitter, max_delay):
        return network_api.build_fetch_retry_policy(
            max_retries,
            backoff_factor,
            jitter,
            max_delay,
        )

    def _log_error(self, url, error_type, error_detail, max_retries=None):
        network_api.log_fetch_error(
            url,
            error_type,
            error_detail,
            logger=logger,
            max_retries=max_retries,
        )

    def _fetch(
        self,
        url,
        max_retries=0,
        initial_delay=1,
        backoff_factor=2,
        method="GET",
        data=None,
        headers=None,
        max_delay=None,
        jitter=0.0,
    ):
        """Fetch data from a URL with exponential backoff for transient errors.

        Args:
            url: URL to fetch (string)
            max_retries: Maximum number of retries for transient errors
            initial_delay: Initial delay in seconds before retrying
            backoff_factor: Factor by which the delay increases with each retry
            method: HTTP method to use (GET or POST)
            data: Data to send in the request body (for POST requests)
            headers: Additional headers to send with the request
            max_delay: Maximum delay before retrying
            jitter: fraction, e.g. 0.1 => random factor in [0.9, 1.1]

        Returns:
            The data fetched from the URL

        Raises:
            httpx.HTTPStatusError: For non-transient HTTP errors
            httpx.RequestError: For non-transient request errors
            Other exceptions that might be raised by httpx

        """
        if isinstance(url, str):
            logger.debug("fetching url: %r", url)

        method_normalized = self._normalize_http_method(method)
        origin = self._origin(url)
        logger.debug(f"Starting API request [{method_normalized}] to {origin}: {url}")

        self._acquire_rate_limit(url)

        request_headers = self._build_request_headers(headers=headers)
        retry_policy = self._build_retry_policy(max_retries, backoff_factor, jitter, max_delay)
        retry_state = network_api.FetchRetryState(delay=initial_delay)

        while True:
            try:
                return self._send_http_request(method_normalized, url, data, request_headers)

            except (
                httpx.HTTPStatusError,
                httpx.LocalProtocolError,
                httpx.ReadTimeout,
                httpx.RequestError,
            ) as err:
                error = self._classify_retryable_fetch_error(url, err)
                should_retry, retry_state = self._retry_or_raise(
                    url=url,
                    error=error,
                    retry_state=retry_state,
                    retry_policy=retry_policy,
                )
                if should_retry:
                    continue
                raise

            except Exception as err:
                # For other exceptions, log and re-raise
                self._log_error(url, "other", err)
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
        data = self._fetch(url, method="GET", max_retries=self.max_retry_count)
        return data

    def _post(self, **kwargs):
        args = {"format": "json"}
        args.update(**kwargs)
        for k, val in args.items():
            if isinstance(val, str):
                args[k] = val.encode("utf-8")

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        postdata = parse.urlencode(args).encode()

        logger.debug("posting to %r", self.apiurl)
        data = self._fetch(self.apiurl, method="POST", data=postdata, headers=headers)
        res = loads(data)
        return res

    def _ensure_oauth2_token(self):
        network_auth.ensure_oauth2_token(
            enabled=self.use_oauth2,
            apiurl=self.apiurl,
            token_info_map=self._token_info,
            http_client=self.http_client,
            logger=logger,
            current_time_fn=time.time,
        )

    def do_request(self, use_post=False, **kwargs):
        sem = self.limit_fetch_semaphore
        if sem is not None:
            sem.acquire()

        try:
            self._ensure_oauth2_token()
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
        self.request_counter += 1
        logger.debug(
            f"Request #{self.request_counter}: ACTION:{kwargs.get('action')} PROP:{kwargs.get('prop')}"
        )
        response_data = self._request(**kwargs)
        # Convert bytes to string if necessary
        if isinstance(response_data, bytes):
            response_data = response_data.decode("utf-8")
        data = loads(response_data)
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
                todo, stop_query = self._handle_query_continue(qc_values, last_qc, kwargs)
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
        siprop = [
            "general",
            "namespaces",
            "interwikimap",
            "namespacealiases",
            "magicwords",
            "rightsinfo",
        ]
        while len(siprop) >= 3:
            try:
                req = self.do_request(action="query", meta="siteinfo", siprop="|".join(siprop))
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
            return self.login(username, password, domain=domain, lgtoken=res["login"]["token"])
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
        """Get edit history for a given page title up to a specific revision.

        Args:
            title (str): Title of the page to get edit history for
            revision (int): Revision ID to start from. If None, starts from latest revision
            rvlimit (int, optional): Maximum number of revisions to retrieve. Defaults to
                                     self.rvlimit

        Returns:
            InspectAuthors: Object containing edit history and author statistics

        """
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

    def get_contributors(self, titles: list[str], rvlimit=None):
        """Get contributors for a list of page titles using the contributors API.

        This method fetches contributors directly using prop=contributors, which is more
        efficient than fetching all revisions and extracting authors from them.

        Args:
            titles (list[str]): List of page titles to get authors for
            rvlimit (int, optional): Maximum number of contributors to retrieve. Defaults to
                                     self.rvlimit

        Returns:
            dict: Dictionary mapping titles to their respective InspectAuthors objects

        """
        rvlimit = rvlimit or self.rvlimit
        kwargs = {
            "titles": "|".join(titles),
            "redirects": 1,
            "prop": "contributors",
            "pclimit": rvlimit,
        }

        # Dictionary to store InspectAuthors objects for each title
        contributors_by_title = {}

        # Initialize InspectAuthors objects for each title
        for title in titles:
            contributors_by_title[title] = authors.InspectAuthors()

        # Dictionary to store title to pageid mapping
        pageid_to_title = {}

        def merge_data(_, newdata):
            # Process redirects to update title mapping
            redirects = newdata.get("redirects", [])
            for redirect in redirects:
                from_title = redirect.get("from")
                to_title = redirect.get("to")
                if from_title and to_title and from_title in contributors_by_title:
                    # Move the InspectAuthors object to the new title
                    contributors_by_title[to_title] = contributors_by_title[from_title]
                    del contributors_by_title[from_title]

            # Process pages
            pages = newdata.get("pages", {})
            for pageid, page in pages.items():
                title = page.get("title")
                if title:
                    pageid_to_title[pageid] = title

                    # Get the InspectAuthors object for this title
                    if title in contributors_by_title:
                        get_authors = contributors_by_title[title]
                    else:
                        # Create a new InspectAuthors object if needed
                        get_authors = authors.InspectAuthors()
                        contributors_by_title[title] = get_authors

                    # Process anonymous contributors
                    anon_count = page.get("anoncontributors", 0)
                    get_authors.num_anon += anon_count

                    # Process named contributors
                    contributors = page.get("contributors", [])
                    for contributor in contributors:
                        name = contributor.get("name", "")
                        if name and not get_authors.bot_rex.search(name):
                            get_authors.authors.add(name)

        self.do_request(action="query", merge_data=merge_data, **kwargs)
        return contributors_by_title


def _append_unique(values, value):
    if value not in values:
        values.append(value)


def _get_path_prefix(path):
    for marker in ("/wiki/", "/w/"):
        if marker in path:
            return path[: path.find(marker)]
    return ""


def guess_api_urls(url):
    """Guesses possible api.php URLs from a MediaWiki article URL.

    Args:
        url (str): URL of a MediaWiki article

    Returns:
        list: List of possible api.php URLs

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
        _append_unique(retval, f"{scheme}://{netloc}/w/api.php")

    path_prefix = _get_path_prefix(str(path))

    prefix = f"{scheme}://{netloc}{path_prefix}"

    if not url.endswith("/"):
        url += "/"

    for _path in (path + "/", "/w/", "/wiki/", "/"):
        base_url = f"{prefix}{_path}sapi.php"
        _append_unique(retval, base_url)
    if url.endswith("/index.php"):
        _append_unique(retval, url[: -len("index.php")] + "api.php")
    if not url.endswith("api.php"):
        _append_unique(retval, f"{url}api.php")
    return retval


def main():
    mw_api = MwApi("https://en.wikipedia.org/w/api.php")
    print(mw_api.get_categorymembers("Category:Mainz"))


if __name__ == "__main__":
    main()
