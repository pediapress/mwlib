"""Tests for the HTTP client manager."""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
from authlib.integrations.httpx_client import OAuth2Client

from mwlib.network.http_client import HttpClientManager


@pytest.fixture
def http_client_manager():
    """Fixture that returns a fresh HttpClientManager instance."""
    # Reset the singleton instance before each test
    HttpClientManager._instance = None
    HttpClientManager._clients = {}
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
def mock_httpx_client():
    """Fixture that mocks httpx.Client."""
    with patch("httpx.Client") as mock_client:
        # Return a new mock instance for each call to httpx.Client
        mock_client.side_effect = lambda **kwargs: MagicMock()
        yield mock_client, mock_client.side_effect


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

    def test_get_client_with_oauth2(
        self, http_client_manager, mock_conf, mock_oauth2_client, monkeypatch
    ):
        """Test that OAuth2 clients are created when use_oauth2 is True."""
        mock_client_class, mock_instance = mock_oauth2_client

        # Configure mock to return OAuth2 settings
        mock_conf.get.side_effect = lambda section, name, default=None, convert=None: {
            ("oauth2", "client_id"): "test_client_id",
            ("oauth2", "client_secret"): "test_client_secret",
            ("oauth2", "token_url"): "https://example.com/token",
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): False,
        }.get((section, name), default)

        # Set the user_agent attribute on the mock_conf
        mock_conf.user_agent = "mwlib test"

        # Store the original isinstance function
        original_isinstance = isinstance

        # Create a custom isinstance function that handles our mock
        def mock_isinstance(obj, class_or_tuple):
            # If checking our mock instance against OAuth2Client, return True
            if obj is mock_instance and "OAuth2Client" in str(class_or_tuple):
                return True
            # For all other cases, use the original isinstance
            return original_isinstance(obj, class_or_tuple)

        # Get a client with OAuth2 explicitly enabled
        with patch("builtins.isinstance", mock_isinstance):
            client = http_client_manager.get_client(
                "https://example.com", use_oauth2=True, use_http2=False
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
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

        # Verify the headers were set correctly
        mock_instance.headers.__setitem__.assert_called_with("User-Agent", "mwlib test")

    def test_get_client_with_http2(self, http_client_manager, mock_conf):
        """Test that HTTP/2 is enabled when use_http2 is True."""
        # Configure mock to return HTTP/2 settings
        mock_conf.get.side_effect = lambda section, name, default, convert=None: {
            ("oauth2", "enabled"): False,
            ("http2", "enabled"): True,
            ("http2", "auto_detect"): False,
        }.get((section, name), default)

        # Get a client with HTTP/2 enabled
        client = http_client_manager.get_client("https://example.com")

        # The client should have been created with HTTP/2 enabled
        assert isinstance(client, httpx.Client)
        client_list = list(http_client_manager._clients.keys())
        assert len(client_list) == 1
        assert "http2=True" in client_list[0]

    def test_detect_http2_support_success(self, http_client_manager, httpx_mock):
        """Test HTTP/2 detection when the server supports it."""
        httpx_mock.add_response(method="HEAD", http_version="HTTP/2")

        http_client_manager.get_client("https://example.com")

        assert "http2=True" in list(http_client_manager._clients.keys())[0]

    def test_detect_http2_support_failure(self, http_client_manager, httpx_mock):
        """Test HTTP/2 detection when the server doesn't support it."""
        httpx_mock.add_response(method="HEAD", http_version="HTTP/1.1")

        http_client_manager.get_client("https://example.com")

        assert "http2=False" in list(http_client_manager._clients.keys())[0]

    def test_detect_http2_support_exception(self, http_client_manager, httpx_mock):
        """Test HTTP/2 detection when an exception occurs."""
        httpx_mock.add_exception(Exception("Test Exception"))

        http_client_manager.get_client("https://example.com")

        assert "http2=False" in list(http_client_manager._clients.keys())[0]

    def test_create_oauth2_client_missing_credentials(
        self, http_client_manager, mock_conf, httpx_mock
    ):
        """Test that a standard client is created when OAuth2 credentials are missing."""
        httpx_mock.add_response(method="HEAD", http_version="HTTP/1.1")

        # Configure mock to return empty OAuth2 credentials
        mock_conf.get.side_effect = lambda section, name, default, convert=None: {
            ("oauth2", "client_id"): "",
            ("oauth2", "client_secret"): "",
        }.get((section, name), default)

        # Create an OAuth2 client with missing credentials
        http_client_manager.get_client("https://example.com")

        # A standard client should have been created instead
        assert "oauth2=False" in list(http_client_manager._clients.keys())[0]

    def test_create_oauth2_client_with_credentials(
        self, http_client_manager, mock_conf, httpx_mock
    ):
        """Test that a standard client is created when OAuth2 credentials are missing."""
        httpx_mock.add_response(method="HEAD", http_version="HTTP/1.1")

        # Configure mock to return empty OAuth2 credentials
        mock_conf.get.side_effect = lambda section, name, default, convert=None: {
            ("oauth2", "client_id"): "client_id",
            ("oauth2", "client_secret"): "client_secret",
            ("oauth2", "enabled"): "True",
        }.get((section, name), default)

        # Create an OAuth2 client with missing credentials
        http_client_manager.get_client("https://example.com")

        # A standard client should have been created instead
        assert "oauth2=True" in list(http_client_manager._clients.keys())[0]
