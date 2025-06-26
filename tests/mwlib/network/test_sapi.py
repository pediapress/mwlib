#!/usr/bin/env pytest

"""Unit tests for mwlib.network.sapi module"""

import pytest
from unittest.mock import MagicMock, patch
import httpx
from pytest_httpx import HTTPXMock

from mwlib.network.sapi import MwApi
from mwlib.network.http_client import HttpClientManager


class TestMwApi:
    """Tests for the MwApi class"""

    @pytest.fixture
    def reset_http_client_manager(self):
        """Reset the HttpClientManager singleton before each test"""
        HttpClientManager._instance = None
        HttpClientManager._clients = {}
        yield
        HttpClientManager._instance = None
        HttpClientManager._clients = {}

    @pytest.fixture
    def mw_api(self, reset_http_client_manager):
        """Create a MwApi instance for testing"""
        return MwApi("https://test.wikipedia.org/w/api.php", use_oauth2=False)

    def test_fetch_success(self, mw_api, httpx_mock):
        """Test successful fetch"""
        httpx_mock.add_response(text="test data")
        # Call _fetch with a URL
        result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query")

        # Verify the result
        assert result == b"test data"
        # Verify that get was called with the correct URL
        requests = httpx_mock.get_requests()
        assert requests[0].url == "https://test.wikipedia.org/w/api.php?action=query"


    def test_fetch_http_429_retry_success(self, mw_api, httpx_mock):
        """Test retry on HTTP 429 error with eventual success"""
        # Create a response for the 429 error
        httpx_mock.add_response(status_code=429, content="Too Many Requests")
        httpx_mock.add_response(status_code=200, content="test data")

        # Mock time.sleep to avoid waiting during tests
        mock_sleep = MagicMock()

        with patch("time.sleep", mock_sleep):
            # Call _fetch with a URL
            result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)

            # Verify the result
            assert result == b"test data"
            assert len(httpx_mock.get_requests()) == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_fetch_http_500_retry_success(self, mw_api, httpx_mock):
        """Test retry on HTTP 500 error with eventual success"""
        # Create a response for the 500 error
        httpx_mock.add_response(500, content="Internal Server Error")
        httpx_mock.add_response(200, content="test data")

        # Mock time.sleep to avoid waiting during tests
        mock_sleep = MagicMock()

        with patch("time.sleep", mock_sleep):
            # Call _fetch with a URL
            result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)

            # Verify the result
            assert result == b"test data"
            assert len(httpx_mock.get_requests()) == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_fetch_url_error_retry_success(self, mw_api, httpx_mock):
        """Test retry on RequestError with eventual success"""
        # Create a success response
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
        httpx_mock.add_response(200, content="test data")

        # Mock time.sleep to avoid waiting during tests
        mock_sleep = MagicMock()

        with patch("time.sleep", mock_sleep):
            # Call _fetch with a URL
            result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)

            # Verify the result
            assert result == b"test data"
            assert len(httpx_mock.get_requests()) == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_fetch_http_429_max_retries_exceeded(self, mw_api, httpx_mock):
        """Test HTTP 429 error with max retries exceeded"""
        # Create a response for the 429 error
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(429, content="Too Many Requests")

        # Mock time.sleep to avoid waiting during tests
        mock_sleep = MagicMock()

        with patch("time.sleep", mock_sleep):
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
        """Test HTTP 404 error with no retry (non-retryable error)"""
        # Create a response for the 404 error
        httpx_mock.add_response(404, content=b"Not Found")

        # Mock time.sleep to verify it's not called
        mock_sleep = MagicMock()

        with patch("time.sleep", mock_sleep):
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
        """Test other exception with no retry"""
        # Set up the mock to raise a general exception
        httpx_mock.add_exception(Exception("Test Exception"))

        # Mock time.sleep to verify it's not called
        mock_sleep = MagicMock()

        with patch("time.sleep", mock_sleep):
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
        """Test exponential backoff with multiple retries"""
        # Create responses for the errors and success
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(429, content="Too Many Requests")
        httpx_mock.add_response(200, content="test data")

        # Mock time.sleep to verify exponential backoff
        mock_sleep = MagicMock()

        with patch("time.sleep", mock_sleep):
            # Call _fetch with a URL
            result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", 
                                  max_retries=3, initial_delay=2, backoff_factor=3)

            # Verify the result
            assert result == b"test data"
            assert len(httpx_mock.get_requests()) == 3
            # Verify that sleep was called with increasing delays (exponential backoff)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(2)  # First retry (initial_delay)
            mock_sleep.assert_any_call(6)  # Second retry (initial_delay * backoff_factor)

    def test_fetch_with_request_object(self, mw_api, httpx_mock):
        """Test fetch with a URL string that is not a simple string"""
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
