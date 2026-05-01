"""Tests for the HTTP client manager."""

from unittest.mock import ANY, MagicMock, patch

import httpx
import pytest

from mwlib.network.http_client import HttpClientManager


@pytest.fixture
def http_client_manager():
    """Fixture that returns a fresh HttpClientManager instance."""
    # Reset the singleton instance before each test
    HttpClientManager._instance = None
    HttpClientManager._clients = {}
    HttpClientManager._http2_support_cache = {}
    return HttpClientManager.get_instance()


@pytest.fixture
def mock_conf():
    """Fixture that mocks the conf module."""
    with patch("mwlib.network.http_client.conf") as mock_conf:
        # Set default configuration values
        mock_conf.get.return_value = False
        mock_conf.user_agent = "mwlib test"
        # Mock the as_bool function
        mock_conf.as_bool = lambda val: val in (True, "True", "true", "yes", "1")
        yield mock_conf


@pytest.fixture
def mock_oauth2_client():
    """Fixture that mocks OAuth2Client."""
    with patch("mwlib.network.http_client.OAuth2Client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_client, mock_instance


class TestHttpClientManager:
    """Tests for the HttpClientManager class."""

    def test_singleton_pattern(self):
        """Test that HttpClientManager follows the singleton pattern."""
        # Reset the singleton instance
        HttpClientManager._instance = None

        # Get two instances
        manager1 = HttpClientManager.get_instance()
        manager2 = HttpClientManager.get_instance()

        # They should be the same object
        assert manager1 is manager2

    def test_get_client_caching(self, http_client_manager, mock_conf):
        """Test that clients are cached by base URL and settings."""
        # Get a client for a URL
        client1 = http_client_manager.get_client("https://example.com")

        # Get another client for the same URL
        client2 = http_client_manager.get_client("https://example.com")

        # They should be the same object
        assert client1 is client2

    def test_get_client_different_urls(self, http_client_manager, mock_conf):
        """Test that different URLs get different clients."""
        # Get clients for different URLs
        client1 = http_client_manager.get_client("https://example.com")
        client2 = http_client_manager.get_client("https://example.org")

        # They should be different objects
        assert client1 is not client2

    def test_get_client_with_oauth2(self, http_client_manager, mock_conf, mock_oauth2_client):
        """Test that OAuth2 clients are created when use_oauth2 is True."""
        mock_client_class, mock_instance = mock_oauth2_client

        # Configure mock to return OAuth2 settings
        mock_conf.get.side_effect = lambda section, name, default=None, convert=None: {
            ("oauth2", "client_id"): "test_client_id",
            ("oauth2", "client_secret"): "test_client_secret",
            ("oauth2", "token_url"): "https://example.com/token",
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        # Set the user_agent attribute on the mock_conf
        mock_conf.user_agent = "mwlib test"

        # Get a client with OAuth2 explicitly enabled
        client = http_client_manager.get_client(
            "https://example.com/w/api.php", use_oauth2=True, use_http2=False
        )

        # Verify the client is the mocked OAuth2Client instance
        assert client is mock_instance

        # The OAuth2Client should have been created with the correct parameters
        mock_client_class.assert_called_once_with(
            client_id="test_client_id",
            client_secret="test_client_secret",
            token_endpoint="https://example.com/token",
            grant_type="client_credentials",
            http2=False,
            headers=ANY,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            limits=ANY,
        )

        # Verify the headers were set correctly
        called_headers = mock_client_class.call_args.kwargs["headers"]
        assert called_headers["User-Agent"] == "mwlib test"

    def test_get_client_with_http2(self, http_client_manager, mock_conf):
        """Test that HTTP/2 is enabled when use_http2 is True."""
        # Configure mock to return HTTP/2 settings
        mock_conf.get.side_effect = lambda section, name, default, convert=None: {
            ("oauth2", "enabled"): False,
            ("http2", "enabled"): True,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        # Get a client with HTTP/2 enabled
        client = http_client_manager.get_client("https://example.com/w/api.php")

        # The client should have been created with HTTP/2 enabled
        assert isinstance(client, httpx.Client)
        client_list = list(http_client_manager._clients.keys())
        assert len(client_list) == 1
        assert client_list[0].startswith("https://example.com|")
        assert "http2=True" in client_list[0]

    def test_detect_http2_support_success(self, http_client_manager):
        """Test HTTP/2 detection when the server supports it."""
        with patch.object(HttpClientManager, "detect_http2_support", return_value=True):
            http_client_manager.get_client("https://example.com")

        assert "http2=True" in list(http_client_manager._clients.keys())[0]

    def test_detect_http2_support_failure(self, http_client_manager):
        """Test HTTP/2 detection when the server doesn't support it."""
        with patch.object(HttpClientManager, "detect_http2_support", return_value=False):
            http_client_manager.get_client("https://example.com")

        assert "http2=False" in list(http_client_manager._clients.keys())[0]

    def test_detect_http2_support_exception(self, http_client_manager):
        """Test HTTP/2 detection when an exception occurs."""
        with patch("mwlib.network.http_client.StandardClient") as mock_client:
            mock_instance = mock_client.return_value.__enter__.return_value
            mock_instance.head.side_effect = Exception("Test Exception")

            http_client_manager.get_client("https://example.com")

        assert "http2=False" in list(http_client_manager._clients.keys())[0]

    def test_create_oauth2_client_missing_credentials(self, http_client_manager, mock_conf):
        """Test that a standard client is created when OAuth2 credentials are missing."""
        mock_conf.get.side_effect = lambda section, name, default, convert=None: {
            ("oauth2", "client_id"): "",
            ("oauth2", "client_secret"): "",
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        # Create an OAuth2 client with missing credentials
        http_client_manager.get_client("https://example.com")

        # A standard client should have been created instead
        assert "oauth2=False" in list(http_client_manager._clients.keys())[0]

    def test_get_client_with_oauth2_credentials_caches_under_oauth2_key(
        self, http_client_manager, mock_conf
    ):
        """OAuth2-enabled clients are cached under an ``oauth2=True`` key.

        Requests for OAuth2 vs standard auth go to different cache
        entries so callers asking for one don't get the other back.
        """
        mock_conf.get.side_effect = lambda section, name, default, convert=None: {
            ("oauth2", "client_id"): "client_id",
            ("oauth2", "client_secret"): "client_secret",
            ("oauth2", "enabled"): "True",
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        http_client_manager.get_client("https://example.com")

        assert "oauth2=True" in list(http_client_manager._clients.keys())[0]

    def test_invalidate_client_removes_cached_instance(self, http_client_manager, mock_conf):
        mock_conf.get.side_effect = lambda section, name, default=None, convert=None: {
            ("oauth2", "enabled"): False,
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        client1 = http_client_manager.get_client("https://example.com/w/api.php")
        http_client_manager.invalidate_client(
            "https://example.com/w/api.php", use_oauth2=False, use_http2=False
        )
        client2 = http_client_manager.get_client("https://example.com/w/api.php")

        assert client1 is not client2

    def test_invalidate_client_drops_all_oauth_fingerprints_for_origin(
        self, http_client_manager, mock_conf
    ):
        """Invalidate must close every cached OAuth client for the origin.

        Cache keys include a credential fingerprint, so the client
        cached under the *previous* fingerprint is unreachable through
        ``_cache_key`` once the credentials have rotated. Without
        prefix-match invalidation, those rotated-out clients leak
        forever.
        """

        def conf_with(secret):
            return lambda section, name, default=None, convert=None: {
                ("oauth2", "client_id"): "id-A",
                ("oauth2", "client_secret"): secret,
                ("oauth2", "token_url"): "https://example.com/token",
                ("oauth2", "enabled"): True,
                ("http2", "enabled"): False,
                ("http2", "auto_detect"): False,
                ("fetch", "max_connections"): 20,
            }.get((section, name), default)

        with patch("mwlib.network.http_client.OAuth2Client") as mock_cls:
            instances = [MagicMock(), MagicMock()]
            mock_cls.side_effect = instances

            mock_conf.get.side_effect = conf_with("secret-1")
            http_client_manager.get_client("https://example.com", use_oauth2=True)

            mock_conf.get.side_effect = conf_with("secret-2")
            http_client_manager.get_client("https://example.com", use_oauth2=True)

            # Two cached entries before invalidation…
            assert len(http_client_manager._clients) == 2

            # …and the current-cred caller invalidates BOTH.
            http_client_manager.invalidate_client(
                "https://example.com", use_oauth2=True, use_http2=False
            )

        assert http_client_manager._clients == {}
        # And we close() every dropped client, not just the current-cred one.
        for inst in instances:
            inst.close.assert_called_once()

    def test_get_client_normalizes_base_url_by_origin(self, http_client_manager, mock_conf):
        """Clients from the same origin should use a normalized base_url."""
        mock_conf.get.side_effect = lambda section, name, default=None, convert=None: {
            ("oauth2", "enabled"): False,
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        client1 = http_client_manager.get_client("https://example.com/w/api.php")
        client2 = http_client_manager.get_client("https://example.com/other/path")

        assert client1 is client2
        assert str(client1.base_url) == "https://example.com"

    def test_oauth2_without_credentials_caches_under_oauth2_false(
        self, http_client_manager, mock_conf
    ):
        """The blocker: OAuth2 fallback must update the cache key.

        Without this, a missing-credentials run would store a *standard*
        client under ``oauth2=True``, and the next caller asking for
        OAuth2 would get that standard client back while still treating
        it as OAuth2 (and try to fetch_token on it).
        """
        from httpx import Client as StandardClient

        mock_conf.get.side_effect = lambda section, name, default=None, convert=None: {
            ("oauth2", "client_id"): "",
            ("oauth2", "client_secret"): "",
            ("oauth2", "enabled"): True,
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        client = http_client_manager.get_client("https://example.com", use_oauth2=True)

        # The returned client is a plain httpx.Client, NOT an OAuth2Client.
        assert isinstance(client, StandardClient)
        # And it's cached under oauth2=False so the next caller (with or
        # without OAuth2) gets the right thing.
        keys = list(http_client_manager._clients.keys())
        assert any("oauth2=False" in k for k in keys)
        assert not any("oauth2=True" in k for k in keys)

    def test_get_client_serializes_concurrent_creation(self, http_client_manager, mock_conf):
        """Concurrent ``get_client`` callers must end up with one client, not two.

        We force the race by patching ``create_standard_client`` to wait
        on a barrier, then spawn two threads that both miss the cache
        and contend for the lock. The first one through must populate
        the cache and the second must observe it — without the lock the
        second thread would also call ``create_standard_client`` and we'd
        cache duplicates.
        """
        import threading
        import time as time_mod

        mock_conf.get.side_effect = lambda section, name, default=None, convert=None: {
            ("oauth2", "enabled"): False,
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        ready = threading.Event()
        proceed = threading.Event()
        original_create = http_client_manager.create_standard_client

        def slow_create(*args, **kwargs):
            ready.set()
            proceed.wait(timeout=2)
            return original_create(*args, **kwargs)

        results = []

        def worker():
            results.append(http_client_manager.get_client("https://example.com"))

        with patch.object(
            http_client_manager,
            "create_standard_client",
            side_effect=slow_create,
        ) as wrapped:
            t1 = threading.Thread(target=worker)
            t1.start()
            ready.wait(timeout=2)  # t1 is inside slow_create, holding the lock
            t2 = threading.Thread(target=worker)
            t2.start()
            time_mod.sleep(0.05)  # let t2 enter get_client and block on the lock
            proceed.set()
            t1.join(timeout=2)
            t2.join(timeout=2)

        assert wrapped.call_count == 1
        assert len(results) == 2
        assert results[0] is results[1]

    # ---- Round 4: credential fingerprint in cache key ----

    def test_oauth2_clients_with_different_credentials_get_different_cache_entries(
        self, http_client_manager, mock_conf
    ):
        """Rotating OAuth2 credentials must not silently reuse a stale-cred client.

        Without a credential fingerprint in the cache key, two callers
        asking for OAuth2 against the same origin with different
        ``client_id`` / ``client_secret`` would share a cached client
        configured with the first run's credentials.
        """

        def conf_with(secret):
            return lambda section, name, default=None, convert=None: {
                ("oauth2", "client_id"): "id-A",
                ("oauth2", "client_secret"): secret,
                ("oauth2", "token_url"): "https://example.com/token",
                ("oauth2", "enabled"): True,
                ("http2", "enabled"): False,
                ("http2", "auto_detect"): False,
                ("fetch", "max_connections"): 20,
            }.get((section, name), default)

        with patch("mwlib.network.http_client.OAuth2Client") as mock_cls:
            mock_cls.side_effect = lambda **kwargs: MagicMock(spec=[])

            mock_conf.get.side_effect = conf_with("secret-1")
            c1 = http_client_manager.get_client("https://example.com", use_oauth2=True)

            # Rotate the secret — same origin, same auth choice.
            mock_conf.get.side_effect = conf_with("secret-2")
            c2 = http_client_manager.get_client("https://example.com", use_oauth2=True)

        # Different credentials → different cached clients.
        assert c1 is not c2
        # The plaintext credentials never land in the cache key — the
        # whole OAuth config is hashed into a compact ``auth=...`` field.
        keys = list(http_client_manager._clients.keys())
        assert all("secret-1" not in k for k in keys)
        assert all("secret-2" not in k for k in keys)
        assert all("id-A" not in k for k in keys)
        assert any("auth=" in k for k in keys)

    # ---- Round 4: locked singleton ----

    def test_get_instance_is_safe_under_concurrent_first_call(self):
        """Two threads racing on first ``get_instance`` get the same singleton.

        Without the instance lock, a thread could observe ``_instance is None``
        between another thread's check and assignment and create a duplicate.
        """
        import threading

        HttpClientManager._instance = None
        results = []

        def worker():
            results.append(HttpClientManager.get_instance())

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)

        assert all(r is results[0] for r in results)


class TestEnsureOAuth2Token:
    """``ensure_oauth2_token`` keeps cached token info and the client in sync.

    The cache lives on ``MwApi._token_info`` (per-domain), while the
    actual OAuth-bearing token lives on the OAuth2 client itself. Those
    two pieces of state drift when the client is recreated; this class
    locks down the reconciliation behaviour.
    """

    def _domain_cache(self, token=None, *, expires_at=2000):
        return {
            "example.com": {
                "token": token or {"access_token": "abc", "expires_in": 3600},
                "expires_at": expires_at,
                "next_retry_at": 0,
                "retry_delay": 0,
            }
        }

    def test_pushes_cached_token_onto_client_with_no_token(self):
        from mwlib.network.auth import ensure_oauth2_token

        cached = {"access_token": "abc", "expires_in": 3600}
        token_info_map = self._domain_cache(token=cached)
        http_client = MagicMock()
        http_client.token = None  # client got recreated, lost its token

        ensure_oauth2_token(
            enabled=True,
            apiurl="https://example.com/w/api.php",
            token_info_map=token_info_map,
            http_client=http_client,
            logger=MagicMock(),
            current_time_fn=lambda: 1000,  # before expires_at=2000
        )

        # No refetch — fetch_token must not have been called.
        http_client.fetch_token.assert_not_called()
        # The client now carries the cached token.
        assert http_client.token == cached

    def test_does_not_refetch_when_client_and_cache_agree(self):
        from mwlib.network.auth import ensure_oauth2_token

        cached = {"access_token": "abc", "expires_in": 3600}
        token_info_map = self._domain_cache(token=cached)
        http_client = MagicMock()
        http_client.token = cached

        ensure_oauth2_token(
            enabled=True,
            apiurl="https://example.com/w/api.php",
            token_info_map=token_info_map,
            http_client=http_client,
            logger=MagicMock(),
            current_time_fn=lambda: 1000,
        )

        http_client.fetch_token.assert_not_called()

    def test_refetches_when_cache_expired(self):
        from mwlib.network.auth import ensure_oauth2_token

        token_info_map = self._domain_cache(expires_at=500)  # already expired
        http_client = MagicMock()
        http_client.fetch_token.return_value = {
            "access_token": "fresh",
            "expires_in": 3600,
        }
        http_client.headers = {"user-agent": "mwlib"}

        ensure_oauth2_token(
            enabled=True,
            apiurl="https://example.com/w/api.php",
            token_info_map=token_info_map,
            http_client=http_client,
            logger=MagicMock(),
            current_time_fn=lambda: 1000,
        )

        http_client.fetch_token.assert_called_once()
        assert token_info_map["example.com"]["token"]["access_token"] == "fresh"
