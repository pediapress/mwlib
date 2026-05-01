"""HTTP client manager for mwlib.

This module provides a singleton HTTP client manager that handles:
1. Shared HTTP clients with caching by base URL
2. OAuth2 authentication when enabled
3. HTTP/2 support detection and usage
"""

import hashlib
import logging
import threading
import time
from typing import Dict, Optional, Union
from urllib.parse import urlparse

import httpx
from authlib.integrations.httpx_client import OAuth2Client
from httpx import Client as StandardClient

from mwlib.utils import conf

logger = logging.getLogger(__name__)


def _oauth2_cache_identity() -> str:
    """Return a fingerprint of the current OAuth2 config for cache keying.

    Two callers asking for OAuth2 against the same origin but with
    different ``client_id`` / ``client_secret`` / ``token_url`` must NOT
    share a cached client — otherwise a credential rotation (or a
    multi-tenant test suite that swaps configs) silently keeps using the
    old client. The secret is hashed so it never lands in logs or cache
    keys in plaintext.
    """
    client_id = conf.get("oauth2", "client_id", "")
    client_secret = conf.get("oauth2", "client_secret", "")
    token_url = conf.get(
        "oauth2", "token_url", "https://meta.wikimedia.org/w/rest.php/oauth2/access_token"
    )
    secret_hash = hashlib.sha256(client_secret.encode("utf-8")).hexdigest()[:16]
    return f"client_id={client_id}|token_url={token_url}|secret={secret_hash}"


class HttpClientManager:
    """Singleton manager for HTTP clients.

    This class provides a centralized way to create and manage HTTP clients,
    supporting both standard and OAuth2 authentication, as well as HTTP/2
    when available.
    """

    _instance = None
    _clients: Dict[str, Union[StandardClient, OAuth2Client]] = {}
    _http2_support_cache: Dict[str, Dict[str, float | bool]] = {}
    _http2_cache_ttl_seconds = 300
    # Guard against two greenlets/threads creating duplicate clients for
    # the same cache key. gevent's Semaphore would also work; threading.Lock
    # is monkey-patched under gevent and is correct under both runtimes.
    _client_lock = threading.Lock()
    _instance_lock = threading.Lock()
    # HTTP/2 probe is a real network HEAD request — keep it short so it
    # doesn't dominate startup latency on slow networks. The result is
    # cached for ``_http2_cache_ttl_seconds`` so this only matters once
    # per origin.
    _http2_probe_timeout_seconds = 2.0

    @classmethod
    def get_instance(cls) -> "HttpClientManager":
        """Get the singleton instance of HttpClientManager."""
        # Double-checked locking: avoid the lock on the hot path, take it
        # only when the instance might genuinely need to be created.
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _origin(self, url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    @staticmethod
    def _cache_key(origin: str, *, use_oauth2: bool, use_http2: bool) -> str:
        """Build the cache key used by both ``get_client`` and ``invalidate_client``.

        For OAuth2 clients the key includes a fingerprint of the
        currently-configured credentials so that rotations create a fresh
        client rather than reusing a stale-credential one. The secret is
        hashed before being interpolated.
        """
        auth_identity = _oauth2_cache_identity() if use_oauth2 else "standard"
        return f"{origin}|oauth2={use_oauth2}|http2={use_http2}|auth={auth_identity}"

    def invalidate_client(self, base_url: str, *, use_oauth2: bool, use_http2: bool) -> None:
        origin = self._origin(base_url)
        cache_key = self._cache_key(origin, use_oauth2=use_oauth2, use_http2=use_http2)
        client = self._clients.pop(cache_key, None)
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.exception("Failed to close http client during invalidation")

    def get_client(
        self, base_url: str, use_oauth2: Optional[bool] = None, use_http2: Optional[bool] = None
    ) -> Union[StandardClient, OAuth2Client]:
        """Get an HTTP client for the given base URL.

        If a client for the given base URL already exists, it will be returned.
        Otherwise, a new client will be created with the specified settings.

        Args:
            base_url: The base URL for the client. Used for detecting HTTP/2
            use_oauth2: Whether to use OAuth2 authentication. If None, uses the
                configuration value.
            use_http2: Whether to use HTTP/2. If None, uses the configuration value.

        Returns:
            Union[httpx.Client, OAuth2Client]: The HTTP client.

        """
        # Determine whether to use OAuth2 and HTTP/2 from configuration if not specified
        if use_oauth2 is None:
            use_oauth2 = conf.get("oauth2", "enabled", False, bool)

        # Resolve OAuth2 *before* building the cache key. Falling back from
        # OAuth2 to standard inside ``create_oauth2_client`` would otherwise
        # leave a standard client cached under ``oauth2=True`` — and a
        # later caller asking for OAuth2 would get that standard client
        # back, while ``MwApi.use_oauth2`` stayed True and tried to call
        # ``fetch_token`` on a non-OAuth2 client. By deciding here, both
        # the cache key and the eventual ``isinstance`` check on the
        # returned client agree.
        if use_oauth2:
            client_id = conf.get("oauth2", "client_id", "")
            client_secret = conf.get("oauth2", "client_secret", "")
            if not client_id or not client_secret:
                logger.warning(
                    "OAuth2 is enabled but client_id or client_secret is not set. "
                    "Using standard client instead."
                )
                use_oauth2 = False

        if use_http2 is None:
            use_http2 = conf.get("http2", "enabled", True, bool)

        # Auto-detect HTTP/2 support if configured. Probe the origin
        # rather than the full ``api.php?...`` URL — heavy routes can
        # take significantly longer to HEAD, and the result is cached
        # per-origin anyway so the probe only hits one endpoint.
        if use_http2 and conf.get("http2", "auto_detect", True, bool):
            use_http2 = self.detect_http2_support(self._origin(base_url))

        origin = self._origin(base_url)

        headers: dict = {}
        if hasattr(conf, "headers"):
            headers.update(getattr(conf, "headers").as_dict())

        headers["User-Agent"] = getattr(conf, "user_agent", "mwlib")

        # Cache key includes the base URL, the auth choice, the HTTP/2
        # decision, and (for OAuth2) a fingerprint of the credentials so
        # rotations don't reuse a stale-cred client.
        cache_key = self._cache_key(origin, use_oauth2=use_oauth2, use_http2=use_http2)

        # Fast path: cache hit. Don't take the lock if we don't have to.
        if cache_key in self._clients:
            return self._clients[cache_key]

        # Slow path: serialize creation so two callers racing on the same
        # cache key don't end up creating duplicate clients (and leaking
        # whichever loses the race).
        with self._client_lock:
            if cache_key in self._clients:
                return self._clients[cache_key]

            max_conns = conf.get("fetch", "max_connections", 20, int)
            limits = httpx.Limits(
                max_connections=max_conns,
                max_keepalive_connections=min(max_conns, 10),
                keepalive_expiry=30.0,
            )

            # Normalize client base_url to origin to match cache key
            normalized_base_url = origin

            if use_oauth2:
                client = self.create_oauth2_client(
                    normalized_base_url, use_http2, limits=limits, headers=headers
                )
            else:
                client = self.create_standard_client(
                    normalized_base_url, use_http2, limits=limits, headers=headers
                )

            http2_version = "HTTP/2" if use_http2 else "HTTP/1.1"
            kind = "OAuth2 client" if use_oauth2 else "standard client"
            logger.info("Created %s using %s for %s", kind, http2_version, base_url)

            self._clients[cache_key] = client
            return client

    def create_oauth2_client(
        self,
        base_url: str,
        use_http2: bool = True,
        limits: httpx.Limits = None,
        headers: Optional[dict] = None,
    ) -> OAuth2Client:
        """Create an OAuth2 client for the given base URL.

        Caller is expected to have already verified that ``client_id`` and
        ``client_secret`` are configured — ``get_client`` does this and
        falls back to ``create_standard_client`` when they aren't, so the
        cache key and ``MwApi.use_oauth2`` agree on the auth choice.
        """
        client_id = conf.get("oauth2", "client_id", "")
        client_secret = conf.get("oauth2", "client_secret", "")
        token_url = conf.get(
            "oauth2", "token_url", "https://meta.wikimedia.org/w/rest.php/oauth2/access_token"
        )

        return OAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint=token_url,
            grant_type="client_credentials",
            http2=use_http2,
            headers=headers,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            limits=limits,
        )

    def create_standard_client(
        self,
        base_url: str,
        use_http2: bool = True,
        limits: httpx.Limits = None,
        headers: Optional[dict] = None,
    ) -> StandardClient:
        """Create a standard HTTP client for the given base URL."""
        client = StandardClient(
            http2=use_http2,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers=headers,
            base_url=base_url,
            limits=limits,
        )

        return client

    def detect_http2_support(self, url: str) -> bool:
        """Detect if the server at the given URL supports HTTP/2."""
        origin = self._origin(url)
        now = time.time()
        cached = self._http2_support_cache.get(origin)
        if cached and now < cached.get("expires_at", 0):
            return bool(cached.get("supported", False))

        try:
            # Create a temporary client with HTTP/2 enabled. Cap the probe
            # timeout aggressively — this fires once per origin during
            # client creation, so a slow server here would otherwise block
            # every first fetch behind a 30s connect.
            with StandardClient(
                http2=True,
                timeout=httpx.Timeout(self._http2_probe_timeout_seconds),
            ) as client:
                # Make a HEAD request to check the HTTP version
                response = client.head(url)
                supported = response.http_version == "HTTP/2"
                self._http2_support_cache[origin] = {
                    "supported": supported,
                    "expires_at": now + self._http2_cache_ttl_seconds,
                }
                return supported
        except Exception as e:
            logger.warning(f"Error detecting HTTP/2 support for {url}: {e}")
            self._http2_support_cache[origin] = {
                "supported": False,
                "expires_at": now + self._http2_cache_ttl_seconds,
            }
            return False
