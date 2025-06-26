"""Tests for the fetch_siteinfo module."""

import json
import os
from unittest.mock import MagicMock, mock_open, patch

import httpx
import pytest
from httpx import Response

from mwlib.network.fetch_siteinfo import detect_http2_support, fetch


@pytest.fixture
def mock_http_client_manager():
    """Fixture that mocks the HttpClientManager."""
    with patch("mwlib.network.fetch_siteinfo.HttpClientManager") as mock_manager:
        # Create a mock instance
        mock_instance = MagicMock()
        mock_manager.get_instance.return_value = mock_instance

        # Mock the detect_http2_support method
        mock_instance.detect_http2_support.return_value = True

        # Mock the get_client method
        mock_client = MagicMock()
        mock_instance.get_client.return_value = mock_client

        # Mock the client's get method
        mock_response = MagicMock()
        mock_client.get.return_value = mock_response
        mock_response.json.return_value = {"query": {"general": {"sitename": "Test Wiki"}}}

        yield mock_manager, mock_instance, mock_client, mock_response


@pytest.fixture
def mock_conf():
    """Fixture that mocks the conf module."""
    with patch("mwlib.network.fetch_siteinfo.conf") as mock_conf:
        # Set default configuration values
        mock_conf.get.side_effect = lambda section, name, default, bool: {
            ("http2", "enabled"): True,
            ("http2", "auto_detect"): True,
        }.get((section, name), default)
        yield mock_conf


@pytest.fixture
def mock_open_file():
    """Fixture that mocks the open function."""
    mock = mock_open()
    with patch("builtins.open", mock):
        yield mock


class TestFetchSiteinfo:
    """Tests for the fetch_siteinfo module."""

    def test_detect_http2_support(self, mock_http_client_manager):
        """Test the detect_http2_support function."""
        mock_manager, mock_instance, _, _ = mock_http_client_manager

        # Call the function
        result = detect_http2_support("https://example.com")

        # Verify that HttpClientManager.get_instance() was called
        mock_manager.get_instance.assert_called_once()

        # Verify that detect_http2_support was called with the correct URL
        mock_instance.detect_http2_support.assert_called_once_with("https://example.com")

        # Verify that the function returns the result from HttpClientManager.detect_http2_support
        assert result is True

    def test_fetch_with_http2_support(self, mock_http_client_manager, mock_conf, mock_open_file):
        """Test the fetch function when HTTP/2 is supported."""
        mock_manager, mock_instance, mock_client, mock_response = mock_http_client_manager

        # Configure the mock response
        mock_response.json.return_value = {"query": {"general": {"sitename": "Test Wiki"}}}

        # Call the function
        fetch("en")

        # Verify that HttpClientManager.get_instance() was called at least once
        assert mock_manager.get_instance.call_count >= 1

        # Verify that detect_http2_support was called with the correct URL
        mock_instance.detect_http2_support.assert_called_once_with("https://en.wikipedia.org")

        # Verify that get_client was called with the correct parameters
        mock_instance.get_client.assert_called_once_with(
            base_url="https://en.wikipedia.org", use_http2=True
        )

        # Verify that the client's get method was called with the correct parameters
        mock_client.get.assert_called_once()
        args, kwargs = mock_client.get.call_args
        assert args[0] == "https://en.wikipedia.org/w/api.php"
        assert kwargs["params"] == {
            "action": "query",
            "meta": "siteinfo",
            "siprop": "general|namespaces|namespacealiases|magicwords|interwikimap",
            "format": "json",
        }

        # Verify that the response was processed correctly
        mock_response.json.assert_called_once()

        # Verify that the file was written with the correct data
        # Instead of checking the number of write calls, check that write was called
        assert mock_open_file().write.call_count > 0

        # Get all the write calls and combine them to reconstruct the JSON
        write_calls = [call[0][0] for call in mock_open_file().write.call_args_list]
        combined_json = "".join(write_calls)

        # Parse the combined JSON and check its content
        parsed_json = json.loads(combined_json)
        assert parsed_json["general"]["sitename"] == "Test Wiki"
        assert parsed_json["http2_supported"] is True

    def test_fetch_without_http2_support(
        self, mock_http_client_manager, mock_conf, mock_open_file
    ):
        """Test the fetch function when HTTP/2 is not supported."""
        mock_manager, mock_instance, mock_client, mock_response = mock_http_client_manager

        # Configure the mock to indicate that HTTP/2 is not supported
        mock_instance.detect_http2_support.return_value = False

        # Configure the mock response
        mock_response.json.return_value = {"query": {"general": {"sitename": "Test Wiki"}}}

        # Call the function
        fetch("en")

        # Verify that HttpClientManager.get_instance() was called at least once
        assert mock_manager.get_instance.call_count >= 1

        # Verify that detect_http2_support was called with the correct URL
        mock_instance.detect_http2_support.assert_called_once_with("https://en.wikipedia.org")

        # Verify that get_client was called with the correct parameters
        mock_instance.get_client.assert_called_once_with(
            base_url="https://en.wikipedia.org", use_http2=False
        )

        # Verify that the client's get method was called with the correct parameters
        mock_client.get.assert_called_once()

        # Verify that the response was processed correctly
        mock_response.json.assert_called_once()

        # Verify that the file was written with the correct data
        # Instead of checking the number of write calls, check that write was called
        assert mock_open_file().write.call_count > 0

        # Get all the write calls and combine them to reconstruct the JSON
        write_calls = [call[0][0] for call in mock_open_file().write.call_args_list]
        combined_json = "".join(write_calls)

        # Parse the combined JSON and check its content
        parsed_json = json.loads(combined_json)
        assert parsed_json["general"]["sitename"] == "Test Wiki"
        assert parsed_json["http2_supported"] is False

    def test_fetch_with_http2_disabled(self, mock_http_client_manager, mock_conf, mock_open_file):
        """Test the fetch function when HTTP/2 is disabled in configuration."""
        _, mock_instance, _, _ = mock_http_client_manager

        # Configure the mock to indicate that HTTP/2 is disabled in configuration
        mock_conf.get.side_effect = lambda section, name, default, bool: {
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): True,
        }.get((section, name), default)

        # Call the function
        fetch("en")

        # Verify that detect_http2_support was not called
        mock_instance.detect_http2_support.assert_not_called()

        # Verify that get_client was called with HTTP/2 disabled
        mock_instance.get_client.assert_called_once_with(
            base_url="https://en.wikipedia.org", use_http2=False
        )

    def test_fetch_with_auto_detect_disabled(
        self, mock_http_client_manager, mock_conf, mock_open_file
    ):
        """Test the fetch function when auto-detect is disabled in configuration."""
        _, mock_instance, _, _ = mock_http_client_manager

        # Configure the mock to indicate that auto-detect is disabled in configuration
        mock_conf.get.side_effect = lambda section, name, default, bool: {
            ("http2", "enabled"): True,
            ("http2", "auto_detect"): False,
        }.get((section, name), default)

        # Call the function
        fetch("en")

        # Verify that detect_http2_support was not called
        mock_instance.detect_http2_support.assert_not_called()

        # Verify that get_client was called with HTTP/2 enabled
        mock_instance.get_client.assert_called_once_with(
            base_url="https://en.wikipedia.org", use_http2=True
        )

    def test_fetch_with_httpx_error(self, mock_http_client_manager, mock_conf, mock_open_file):
        """Test the fetch function when httpx raises an error."""
        _, _, mock_client, _ = mock_http_client_manager

        # Configure the mock to raise an exception
        mock_client.get.side_effect = httpx.RequestError("Test error")

        # Mock urlopen for the fallback
        with patch("mwlib.network.fetch_siteinfo.urlopen") as mock_urlopen:
            # Configure the mock response for urlopen
            mock_urlopen_response = MagicMock()
            mock_urlopen.return_value.__enter__.return_value = mock_urlopen_response
            mock_urlopen_response.read.return_value = json.dumps(
                {"query": {"general": {"sitename": "Test Wiki"}}}
            ).encode()

            # Call the function
            fetch("en")

            # Verify that urlopen was called with the correct URL
            mock_urlopen.assert_called_once()

            # Verify that the file was written with the correct data
            # Instead of checking the number of write calls, check that write was called
            assert mock_open_file().write.call_count > 0

            # Get all the write calls and combine them to reconstruct the JSON
            write_calls = [call[0][0] for call in mock_open_file().write.call_args_list]
            combined_json = "".join(write_calls)

            # Parse the combined JSON and check its content
            parsed_json = json.loads(combined_json)
            assert parsed_json["general"]["sitename"] == "Test Wiki"
            assert parsed_json["http2_supported"] is False
