"""HTTP client manager for mwlib.

This module provides a singleton HTTP client manager that handles:
1. Shared HTTP clients with caching by base URL
2. OAuth2 authentication when enabled
3. HTTP/2 support detection and usage
"""

import logging
import time
from typing import Dict, Optional, Union, Any
from urllib.parse import urlparse

import httpx
from httpx import Client as StandardClient
from authlib.integrations.httpx_client import OAuth2Client

from mwlib.utils import conf

logger = logging.getLogger(__name__)


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

    @classmethod
    def get_instance(cls) -> "HttpClientManager":
        """Get the singleton instance of HttpClientManager.

        Returns:
            HttpClientManager: The singleton instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _origin(self, url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    def invalidate_client(self, base_url: str, *, use_oauth2: bool, use_http2: bool) -> None:
        origin = self._origin(base_url)
        cache_key = f"{origin}|oauth2={use_oauth2}|http2={use_http2}"
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

        if use_http2 is None:
            use_http2 = conf.get("http2", "enabled", True, bool)

        # Auto-detect HTTP/2 support if configured
        if use_http2 and conf.get("http2", "auto_detect", True, bool):
            use_http2 = self.detect_http2_support(base_url)

        origin = self._origin(base_url)

        headers: dict = {}
        if hasattr(conf, "headers"):
            headers.update(getattr(conf, "headers").as_dict())

        headers["User-Agent"] = getattr(conf, "user_agent", "mwlib")

        # Create a cache key that includes the base URL, authentication and HTTP/2 settings
        cache_key = f"{origin}|oauth2={use_oauth2}|http2={use_http2}"

        # Return cached client if it exists
        if cache_key in self._clients:
            return self._clients[cache_key]

        # apply connection limits
        max_conns = conf.get("fetch", "max_connections", 20, int)
        limits = httpx.Limits(
            max_connections=max_conns,
            max_keepalive_connections=min(max_conns, 10),
            keepalive_expiry=30.0,
        )

        # Normalize client base_url to origin to match cache key
        normalized_base_url = origin

        # Create a new client with the appropriate settings
        if use_oauth2:
            client = self.create_oauth2_client(
                normalized_base_url, use_http2, limits=limits, headers=headers
            )
        else:
            client = self.create_standard_client(
                normalized_base_url, use_http2, limits=limits, headers=headers
            )

        http2_version = "HTTP/2" if use_http2 else "HTTP/1.1"
        if use_oauth2:
            logger.info(f"Created OAuth2 client and using {http2_version} for {base_url}")
        else:
            logger.info(f"Created standard client and using {http2_version} for {base_url}")

        # Cache and return the client
        self._clients[cache_key] = client
        return client

    def create_oauth2_client(
        self,
        base_url: str,
        use_http2: bool = True,
        limits: httpx.Limits = None,
        headers: Optional[dict] = None,
    ) -> OAuth2Client | StandardClient:
        """Create an OAuth2 client for the given base URL.

        Args:
            base_url: The base URL for the client.
            use_http2: Whether to use HTTP/2.
            limits: httpx.Limits instance

        Returns:
            OAuth2Client: The OAuth2 client.
        """
        client_id = conf.get("oauth2", "client_id", "")
        client_secret = conf.get("oauth2", "client_secret", "")

        token_url = conf.get(
            "oauth2", "token_url", "https://meta.wikimedia.org/w/rest.php/oauth2/access_token"
        )

        if not client_id or not client_secret:
            logger.warning(
                "OAuth2 is enabled but client_id or client_secret is not set. "
                "Using standard client instead."
            )
            return self.create_standard_client(base_url, use_http2, limits=limits, headers=headers)

        # Create an OAuth2 client with client_credentials grant
        client = OAuth2Client(
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

        return client

    def create_standard_client(
        self,
        base_url: str,
        use_http2: bool = True,
        limits: httpx.Limits = None,
        headers: Optional[dict] = None,
    ) -> StandardClient:
        """Create a standard HTTP client for the given base URL.

        Args:
            base_url: The base URL for the client.
            use_http2: Whether to use HTTP/2.

        Returns:
            httpx.Client: The standard HTTP client.
        """
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
        """Detect if the server at the given URL supports HTTP/2.
        // ... existing code ...
        """
        origin = self._origin(url)
        now = time.time()
        cached = self._http2_support_cache.get(origin)
        if cached and now < cached.get("expires_at", 0):
            return bool(cached.get("supported", False))

        try:
            # Create a temporary client with HTTP/2 enabled
            with StandardClient(http2=True) as client:
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
