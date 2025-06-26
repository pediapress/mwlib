"""Tests for the fetch module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mwlib.network.fetch import download_to_file


@pytest.fixture
def mock_http_client_manager():
    """Fixture that mocks the HttpClientManager."""
    with patch("mwlib.network.fetch.HttpClientManager") as mock_manager:
        # Create a mock instance
        mock_instance = MagicMock()
        mock_manager.get_instance.return_value = mock_instance

        # Mock the detect_http2_support method
        mock_instance.detect_http2_support.return_value = True

        # Mock the get_client method
        mock_client = MagicMock()
        mock_instance.get_client.return_value = mock_client

        # Mock the client's stream method
        mock_response = MagicMock()
        mock_client.stream.return_value.__enter__.return_value = mock_response
        mock_response.iter_bytes.return_value = [b"test data"]

        yield mock_manager, mock_instance, mock_client, mock_response


@pytest.fixture
def mock_conf():
    """Fixture that mocks the conf module."""
    with patch("mwlib.network.fetch.conf") as mock_conf:
        # Set default configuration values
        mock_conf.get.side_effect = lambda section, name, default, bool: {
            ("http2", "enabled"): True,
            ("http2", "auto_detect"): True,
        }.get((section, name), default)
        yield mock_conf


@pytest.fixture
def temp_files():
    """Fixture that creates temporary files for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        path = temp_file.name
        temp_path = path + "temp"
        yield path, temp_path
        # Clean up
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(temp_path):
            os.remove(temp_path)


class TestFetch:
    """Tests for the fetch module."""

    def test_download_to_file_success(self, mock_http_client_manager, mock_conf, temp_files):
        """Test successful download of a file."""
        _, mock_instance, mock_client, mock_response = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock response
        mock_response.iter_bytes.return_value = [b"test data"]

        # Call the function
        download_to_file("https://example.com/file.txt", path, temp_path)

        # Verify that HttpClientManager.get_instance() was called
        mock_instance.detect_http2_support.assert_called_once_with("https://example.com")

        # Verify that get_client was called with the correct parameters
        mock_instance.get_client.assert_called_once_with(
            base_url="https://example.com",
            use_http2=True
        )

        # Verify that the client's stream method was called with the correct parameters
        mock_client.stream.assert_called_once_with("GET", "https://example.com/file.txt")

        # Verify that the response's iter_bytes method was called
        mock_response.iter_bytes.assert_called_once_with(chunk_size=16384)

        # Verify that the file was created and contains the expected data
        with open(path, "rb") as f:
            assert f.read() == b"test data"

    def test_download_to_file_http2_disabled(self, mock_http_client_manager, mock_conf, temp_files):
        """Test download when HTTP/2 is disabled in configuration."""
        _, mock_instance, _, _ = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock to indicate that HTTP/2 is disabled in configuration
        mock_conf.get.side_effect = lambda section, name, default, bool: {
            ("http2", "enabled"): False,
            ("http2", "auto_detect"): True,
        }.get((section, name), default)

        # Call the function
        download_to_file("https://example.com/file.txt", path, temp_path)

        # Verify that detect_http2_support was not called
        mock_instance.detect_http2_support.assert_not_called()

        # Verify that get_client was called with HTTP/2 disabled
        mock_instance.get_client.assert_called_once_with(
            base_url="https://example.com",
            use_http2=False
        )

    def test_download_to_file_http2_not_supported(self, mock_http_client_manager, mock_conf, temp_files):
        """Test download when HTTP/2 is not supported by the server."""
        _, mock_instance, _, _ = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock to indicate that HTTP/2 is not supported
        mock_instance.detect_http2_support.return_value = False

        # Call the function
        download_to_file("https://example.com/file.txt", path, temp_path)

        # Verify that detect_http2_support was called
        mock_instance.detect_http2_support.assert_called_once_with("https://example.com")

        # Verify that get_client was called with HTTP/2 disabled
        mock_instance.get_client.assert_called_once_with(
            base_url="https://example.com",
            use_http2=False
        )

    def test_download_to_file_auto_detect_disabled(self, mock_http_client_manager, mock_conf, temp_files):
        """Test download when auto-detect is disabled in configuration."""
        _, mock_instance, _, _ = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock to indicate that auto-detect is disabled in configuration
        mock_conf.get.side_effect = lambda section, name, default, bool: {
            ("http2", "enabled"): True,
            ("http2", "auto_detect"): False,
        }.get((section, name), default)

        # Call the function
        download_to_file("https://example.com/file.txt", path, temp_path)

        # Verify that detect_http2_support was not called
        mock_instance.detect_http2_support.assert_not_called()

        # Verify that get_client was called with HTTP/2 enabled
        mock_instance.get_client.assert_called_once_with(
            base_url="https://example.com",
            use_http2=True
        )

    def test_download_to_file_http_429_retry(self, mock_http_client_manager, mock_conf, temp_files):
        """Test retry mechanism for HTTP 429 errors."""
        _, _, mock_client, mock_response = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock to raise a 429 error on first call, then succeed
        http_error = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=MagicMock(status_code=429)
        )
        
        # Create a side effect that raises an error on first call, then succeeds
        mock_client.stream.side_effect = [
            MagicMock(__enter__=MagicMock(side_effect=http_error)),
            MagicMock(__enter__=MagicMock(return_value=mock_response))
        ]

        # Call the function with retry parameters
        download_to_file("https://example.com/file.txt", path, temp_path, max_retries=1, initial_delay=0.01)

        # Verify that the client's stream method was called twice
        assert mock_client.stream.call_count == 2

    def test_download_to_file_http_error(self, mock_http_client_manager, mock_conf, temp_files):
        """Test handling of HTTP errors."""
        _, _, mock_client, _ = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock to raise an HTTP error
        http_error = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404)
        )
        mock_client.stream.return_value.__enter__.side_effect = http_error

        # Call the function and expect an exception
        with pytest.raises(httpx.HTTPStatusError):
            download_to_file("https://example.com/file.txt", path, temp_path)

    def test_download_to_file_general_error(self, mock_http_client_manager, mock_conf, temp_files):
        """Test handling of general errors."""
        _, _, mock_client, _ = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock to raise a general error
        mock_client.stream.return_value.__enter__.side_effect = Exception("Test error")

        # Call the function and expect an exception
        with pytest.raises(Exception):
            download_to_file("https://example.com/file.txt", path, temp_path)
