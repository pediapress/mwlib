#!/usr/bin/env pytest

"""Unit tests for mwlib.network.sapi module."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from pytest_httpx import HTTPXMock

from mwlib.network.http_client import HttpClientManager
from mwlib.network.sapi import MwApi


class TestMwApi:
    """Tests for the MwApi class."""

    @pytest.fixture
    def reset_http_client_manager(self):
        """Reset shared singletons / class state before each test.

        ``request_counter`` lives on the instance now, so it doesn't need
        a class-level reset — but the cached HTTP clients, rate limiters,
        and OAuth token state are class-shared and must be cleared.
        """
        HttpClientManager._instance = None
        HttpClientManager._clients = {}
        MwApi._rate_limiters = {}
        MwApi._rate_limiter_rps = {}
        MwApi._token_info = {}
        yield
        HttpClientManager._instance = None
        HttpClientManager._clients = {}
        MwApi._rate_limiters = {}
        MwApi._rate_limiter_rps = {}
        MwApi._token_info = {}

    @pytest.fixture
    def mw_api(self, reset_http_client_manager):
        """Create a MwApi instance for testing."""
        return MwApi("https://test.wikipedia.org/w/api.php", use_oauth2=False)

    def test_fetch_success(self, mw_api, httpx_mock):
        """Test successful fetch."""
        httpx_mock.add_response(text="test data")
        # Call _fetch with a URL
        result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query")

        # Verify the result
        assert result == b"test data"
        # Verify that get was called with the correct URL
        requests = httpx_mock.get_requests()
        assert requests[0].url == "https://test.wikipedia.org/w/api.php?action=query"

    def test_fetch_http_429_retry_success(self, mw_api, httpx_mock):
        """Test retry on HTTP 429 error with eventual success."""
        # Create a response for the 429 error
        httpx_mock.add_response(status_code=429, content="Too Many Requests")
        httpx_mock.add_response(status_code=200, content="test data")

        # Mock gevent.sleep to avoid waiting during tests
        mock_sleep = MagicMock()

        with patch("mwlib.network.sapi.gevent.sleep", mock_sleep):
            # Call _fetch with a URL
            result = mw_api._fetch(
                "https://test.wikipedia.org/w/api.php?action=query", max_retries=2
            )

            # Verify the result
            assert result == b"test data"
            assert len(httpx_mock.get_requests()) == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_maxlag_injected_on_query(self, mw_api, httpx_mock):
        """``maxlag`` is added to read queries so the server can ask us to back
        off before it hard-rate-limits us."""
        httpx_mock.add_response(json={"query": {}})

        mw_api.do_request(action="query", meta="siteinfo")

        assert mw_api.maxlag == 5
        assert "maxlag=5" in str(httpx_mock.get_requests()[0].url)

    def test_maxlag_error_is_retried_then_succeeds(self, mw_api, httpx_mock):
        """A maxlag refusal is transient — back off and retry instead of
        failing the fetch."""
        httpx_mock.add_response(
            json={"error": {"code": "maxlag", "info": "Waiting for a database server"}}
        )
        httpx_mock.add_response(json={"query": {"pages": {}}})

        mock_sleep = MagicMock()
        with patch("mwlib.network.sapi.gevent.sleep", mock_sleep):
            result = mw_api.do_request(action="query", meta="siteinfo")

        assert result == {"pages": {}}
        assert mock_sleep.called
        assert len(httpx_mock.get_requests()) == 2

    def test_fetch_http_500_retry_success(self, mw_api, httpx_mock):
        """Test retry on HTTP 500 error with eventual success."""
        # Create a response for the 500 error
        httpx_mock.add_response(500, content="Internal Server Error")
        httpx_mock.add_response(200, content="test data")

        # Mock gevent.sleep to avoid waiting during tests
        mock_sleep = MagicMock()

        with patch("mwlib.network.sapi.gevent.sleep", mock_sleep):
            # Call _fetch with a URL
            result = mw_api._fetch(
                "https://test.wikipedia.org/w/api.php?action=query", max_retries=2
            )

            # Verify the result
            assert result == b"test data"
            assert len(httpx_mock.get_requests()) == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_fetch_url_error_retry_success(self, mw_api, httpx_mock):
        """Test retry on RequestError with eventual success."""
        # Create a success response
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        httpx_mock.add_response(200, content="test data")

        # Mock gevent.sleep to avoid waiting during tests
        mock_sleep = MagicMock()

        with patch("mwlib.network.sapi.gevent.sleep", mock_sleep):
            # Call _fetch with a URL
            result = mw_api._fetch(
                "https://test.wikipedia.org/w/api.php?action=query", max_retries=2
            )

            # Verify the result
            assert result == b"test data"
            assert len(httpx_mock.get_requests()) == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_fetch_http_429_max_retries_exceeded(self, mw_api, httpx_mock):
        """Test HTTP 429 error with max retries exceeded."""
        # Create a response for the 429 error
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(429, content="Too Many Requests")

        # Mock gevent.sleep to avoid waiting during tests
        mock_sleep = MagicMock()

        with patch("mwlib.network.sapi.gevent.sleep", mock_sleep):
            # Call _fetch with a URL and expect HTTPStatusError
            with pytest.raises(httpx.HTTPStatusError) as excinfo:
                mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)

            # Verify the error
            assert excinfo.value.response.status_code == 429
            # Verify that get was called max_retries + 1 times (initial + retries)
            assert len(httpx_mock.get_requests()) == 3
            # Verify that sleep was called max_retries times
            assert mock_sleep.call_count == 2
            # Verify that sleep was called with increasing delays (exponential backoff)
            mock_sleep.assert_any_call(1)  # First retry
            mock_sleep.assert_any_call(2)  # Second retry (1 * 2)

    def test_fetch_http_404_no_retry(self, mw_api, httpx_mock):
        """Test HTTP 404 error with no retry (non-retryable error)."""
        # Create a response for the 404 error
        httpx_mock.add_response(404, content=b"Not Found")

        # Mock gevent.sleep to verify it's not called
        mock_sleep = MagicMock()

        with patch("mwlib.network.sapi.gevent.sleep", mock_sleep):
            # Call _fetch with a URL and expect HTTPStatusError
            with pytest.raises(httpx.HTTPStatusError) as excinfo:
                mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)

            # Verify the error
            assert excinfo.value.response.status_code == 404
            # Verify that get was called only once (no retries)
            assert len(httpx_mock.get_requests()) == 1
            # Verify that sleep was not called
            assert not mock_sleep.called

    def test_fetch_other_exception_no_retry(self, mw_api, httpx_mock):
        """Test other exception with no retry."""
        # Set up the mock to raise a general exception
        httpx_mock.add_exception(Exception("Test Exception"))

        # Mock gevent.sleep to verify it's not called
        mock_sleep = MagicMock()

        with patch("mwlib.network.sapi.gevent.sleep", mock_sleep):
            # Call _fetch with a URL and expect Exception
            with pytest.raises(Exception) as excinfo:
                mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)

            # Verify the error
            assert str(excinfo.value) == "Test Exception"
            # Verify that get was called only once (no retries)
            assert len(httpx_mock.get_requests()) == 1
            # Verify that sleep was not called
            assert not mock_sleep.called

    def test_fetch_exponential_backoff(self, mw_api, httpx_mock):
        """Test exponential backoff with multiple retries."""
        # Create responses for the errors and success
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(200, content="test data")

        # Mock gevent.sleep to verify exponential backoff
        mock_sleep = MagicMock()

        with patch("mwlib.network.sapi.gevent.sleep", mock_sleep):
            # Call _fetch with a URL
            result = mw_api._fetch(
                "https://test.wikipedia.org/w/api.php?action=query",
                max_retries=3,
                initial_delay=2,
                backoff_factor=3,
            )

            # Verify the result
            assert result == b"test data"
            assert len(httpx_mock.get_requests()) == 3
            # Verify that sleep was called with increasing delays (exponential backoff)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(2)  # First retry (initial_delay)
            mock_sleep.assert_any_call(6)  # Second retry (initial_delay * backoff_factor)

    def test_fetch_with_request_object(self, mw_api, httpx_mock):
        """Test fetch with a URL string that is not a simple string."""
        # Set up the mock to return a successful response
        httpx_mock.add_response(200, content="test data")

        # Create a URL with special characters
        url = "https://test.wikipedia.org/w/api.php?action=query&titles=Test%20Page"

        # Call _fetch with the URL
        result = mw_api._fetch(url)

        # Verify the result
        assert result == b"test data"
        # Verify that get was called with the correct URL

        requests = httpx_mock.get_requests()
        assert requests[0].headers["Referer"] == "https://pediapress.com"

    def test_fetch_jitter_and_max_delay_are_applied(self, mw_api, httpx_mock):
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(200, content="ok")

        mock_sleep = MagicMock()

        with (
            patch("mwlib.network.sapi.gevent.sleep", mock_sleep),
            patch("mwlib.network.sapi.random.uniform", return_value=2.0),
        ):
            mw_api._fetch(
                "https://test.wikipedia.org/w/api.php?action=query",
                max_retries=1,
                initial_delay=10,
                backoff_factor=2,
                jitter=0.1,
                max_delay=5,
            )

        # First computed delay: 10 * uniform(2.0) => 20, then capped to 5
        mock_sleep.assert_called_once_with(5)

    def test_oauth2_token_fetch_backoff_on_failure(self, mw_api):
        """Token fetch failures should not be retried on every request (backoff)."""
        mw_api.use_oauth2 = True
        mw_api.http_client.fetch_token = MagicMock(side_effect=httpx.ConnectError("token failed"))

        with (
            patch.object(mw_api, "_do_request", return_value={}),
            patch("mwlib.network.sapi.time.time", side_effect=[1000, 1000, 1005, 1005]),
        ):
            with pytest.raises(RuntimeError):
                mw_api.do_request(action="query", meta="siteinfo")
            mw_api.do_request(action="query", meta="siteinfo")

        assert mw_api.http_client.fetch_token.call_count == 1
        # Token state is keyed by the OAuth identity, not just domain, so
        # two configurations against the same wiki don't share tokens.
        token_key = mw_api._oauth_token_cache_key()
        assert mw_api._token_info[token_key]["next_retry_at"] > 1005

    def test_rate_limiter_is_scoped_per_domain(self, mw_api):
        with (
            patch("mwlib.network.sapi.conf.get", return_value=2),
            patch("mwlib.network.sapi.RateLimiter") as mock_limiter_cls,
        ):
            limiter_a = MagicMock()
            limiter_b = MagicMock()
            mock_limiter_cls.side_effect = [limiter_a, limiter_b]

            mw_api._acquire_rate_limit("https://en.wikipedia.org/w/api.php?action=query")
            mw_api._acquire_rate_limit("https://en.wikipedia.org/w/api.php?action=parse")
            mw_api._acquire_rate_limit("https://commons.wikimedia.org/w/api.php?action=query")

            assert mock_limiter_cls.call_count == 2
            limiter_a.acquire.assert_called()
            limiter_b.acquire.assert_called_once_with()

    def test_rate_limiter_uses_gevent_sleep(self, mw_api):
        """``RateLimiter.acquire`` must yield to the gevent hub when throttling.

        ``time.sleep`` would block the entire event loop and starve every
        other greenlet sharing the worker; ``gevent.sleep`` cooperates with
        the scheduler.
        """
        from mwlib.network.sapi import RateLimiter

        rl = RateLimiter(max_calls=1, period=1.0)
        # Burn the only slot so the next acquire has to wait.
        rl.acquire()

        with (
            patch("mwlib.network.sapi.gevent.sleep") as mock_gevent_sleep,
            patch("mwlib.network.sapi.time.sleep") as mock_time_sleep,
        ):
            # Make gevent.sleep advance the clock so the second iteration
            # of acquire's loop sees an empty window and returns.
            def advance_clock(_):
                rl._timestamps.clear()

            mock_gevent_sleep.side_effect = advance_clock

            rl.acquire()

            assert mock_gevent_sleep.called
            mock_time_sleep.assert_not_called()

    def test_request_counter_is_per_instance(self, reset_http_client_manager):
        """Two MwApis must not share a request counter.

        ``self.request_counter`` used to read the class-level default
        until first incremented, then silently shadow it on the
        instance. Two MwApis would race on the class attribute up to
        their first request and then diverge. Now it's plainly
        per-instance from construction.
        """
        a = MwApi("https://a.wikipedia.org/w/api.php", use_oauth2=False, use_http2=False)
        b = MwApi("https://b.wikipedia.org/w/api.php", use_oauth2=False, use_http2=False)

        # Both start at 0, both as instance attributes (no class-level shadowing).
        assert a.request_counter == 0
        assert b.request_counter == 0
        assert "request_counter" in a.__dict__
        assert "request_counter" in b.__dict__

        # Mimic what _handle_request does — bump the counter — without
        # actually firing HTTP. This is what the regression is about: the
        # increment used to write to a class attribute on first call.
        a.request_counter += 1

        assert a.request_counter == 1
        assert b.request_counter == 0

    def test_basic_auth_is_per_instance_not_on_shared_client(self, reset_http_client_manager):
        """Two MwApi instances for the same origin must not share Basic Auth.

        The previous implementation set ``self.http_client.auth = ...`` on
        the cached httpx client. Since the client is shared between every
        MwApi for the origin, the second caller would inherit (or
        overwrite) the first's credentials — a real security issue. Now
        each MwApi keeps its own ``basic_auth`` and passes it per request.
        """
        a = MwApi(
            "https://en.wikipedia.org/w/api.php",
            username="alice",
            password="secret-a",
            use_oauth2=False,
        )
        b = MwApi(
            "https://en.wikipedia.org/w/api.php",
            username="bob",
            password="secret-b",
            use_oauth2=False,
        )
        c = MwApi(
            "https://en.wikipedia.org/w/api.php",
            use_oauth2=False,
        )

        # Same shared client (same origin)…
        assert a.http_client is b.http_client is c.http_client
        # …and the shared client was never given an auth attribute.
        assert getattr(a.http_client, "auth", None) is None
        # Each MwApi carries its own credentials.
        assert a.basic_auth is not None
        assert b.basic_auth is not None
        assert c.basic_auth is None
        assert a.basic_auth is not b.basic_auth

    def test_retry_backoff_uses_gevent_sleep(self, mw_api, httpx_mock):
        """Retry backoff must yield to gevent, not block the hub.

        ``RateLimiter.acquire`` already uses ``gevent.sleep``; retries
        used to still go through ``time.sleep``, which would starve
        every other greenlet during a 429 storm.
        """
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(200, content="ok")

        with (
            patch("mwlib.network.sapi.gevent.sleep") as mock_gevent_sleep,
            patch("mwlib.network.sapi.time.sleep") as mock_time_sleep,
        ):
            mw_api._fetch(
                "https://test.wikipedia.org/w/api.php?action=query",
                max_retries=2,
            )

            assert mock_gevent_sleep.called
            mock_time_sleep.assert_not_called()

    def test_oauth_token_cache_key_includes_client_identity(self, mw_api):
        """Different OAuth identities yield different token cache keys.

        Token state used to be keyed by domain alone — credential
        rotation or multi-tenant runs would silently reuse each other's
        access tokens. The new key folds in the full OAuth config
        fingerprint (client_id + secret + token_url, hashed).
        """

        def conf_with(client_id, secret):
            return lambda section, name, default=None, convert=None: {
                ("oauth2", "client_id"): client_id,
                ("oauth2", "client_secret"): secret,
                ("oauth2", "token_url"): "https://wiki/oauth",
            }.get((section, name), default)

        with patch("mwlib.network.http_client.conf") as mock_conf:
            mock_conf.get.side_effect = conf_with("tenant-a", "secret-a")
            key_a = mw_api._oauth_token_cache_key()

            # Same client_id + token_url, different secret → still distinct.
            mock_conf.get.side_effect = conf_with("tenant-a", "secret-b")
            key_secret_rotated = mw_api._oauth_token_cache_key()

            mock_conf.get.side_effect = conf_with("tenant-b", "secret-a")
            key_b = mw_api._oauth_token_cache_key()

        assert key_a != key_b
        # Secret rotation alone is enough to flip the key (this is the
        # round-5 fix — the previous key only used client_id).
        assert key_a != key_secret_rotated
        # Plaintext credentials never end up in the key.
        assert "tenant-a" not in key_a
        assert "secret-a" not in key_a

    def test_oauth2_fallback_to_standard_disables_use_oauth2(self, reset_http_client_manager):
        """OAuth2 → standard fallback flips MwApi.use_oauth2 to False.

        When OAuth2 is requested but credentials are missing, the
        manager hands back a standard httpx.Client. MwApi must recognise
        that and stop trying to fetch OAuth tokens against it — calling
        ``fetch_token`` on a non-OAuth2 client crashes with AttributeError.
        """
        with patch("mwlib.network.http_client.conf") as mock_conf:
            mock_conf.get.side_effect = lambda section, name, default=None, convert=None: {
                ("oauth2", "client_id"): "",
                ("oauth2", "client_secret"): "",
                ("http2", "enabled"): False,
                ("http2", "auto_detect"): False,
                ("fetch", "max_connections"): 20,
            }.get((section, name), default)
            mock_conf.user_agent = "mwlib test"

            api = MwApi("https://example.com/w/api.php", use_oauth2=True)

        # Even though we asked for OAuth2, the manager fell back to a
        # standard client — and MwApi reflects that.
        from authlib.integrations.httpx_client import OAuth2Client

        assert api.use_oauth2 is False
        assert not isinstance(api.http_client, OAuth2Client)

        # do_request → _ensure_oauth2_token → no-op when use_oauth2 is
        # False. The standard client doesn't even have a fetch_token
        # method, so the previous behaviour (use_oauth2=True against a
        # standard client) would have crashed on first request.
