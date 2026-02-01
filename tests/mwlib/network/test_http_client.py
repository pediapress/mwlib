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

    def test_create_oauth2_client_with_credentials(self, http_client_manager, mock_conf):
        """Test that a standard client is created with OAuth2 credentials."""
        mock_conf.get.side_effect = lambda section, name, default, convert=None: {
            ("oauth2", "client_id"): "client_id",
            ("oauth2", "client_secret"): "client_secret",
            ("oauth2", "enabled"): "True",
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
            ("fetch", "max_connections"): 20,
        }.get((section, name), default)

        # Create an OAuth2 client with missing credentials
        http_client_manager.get_client("https://example.com")

        # A standard client should have been created instead
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
