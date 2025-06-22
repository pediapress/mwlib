#!/usr/bin/env pytest

"""Unit tests for mwlib.network.sapi module"""

import pytest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

from mwlib.network.sapi import MwApi


class TestMwApi:
    """Tests for the MwApi class"""

    @pytest.fixture
    def mw_api(self):
        """Create a MwApi instance for testing"""
        return MwApi("https://test.wikipedia.org/w/api.php")

    @pytest.fixture
    def mock_response(self):
        """Create a mock response object"""
        mock = MagicMock()
        mock.read.return_value = b"test data"
        mock.close.return_value = None
        return mock

    def test_fetch_success(self, mw_api, mock_response, monkeypatch):
        """Test successful fetch"""
        # Mock the opener.open method to return a successful response
        monkeypatch.setattr(mw_api.opener, "open", lambda url: mock_response)
        
        # Call _fetch with a URL
        result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query")
        
        # Verify the result
        assert result == b"test data"
        assert mock_response.read.called
        assert mock_response.close.called

    def test_fetch_http_429_retry_success(self, mw_api, mock_response, monkeypatch):
        """Test retry on HTTP 429 error with eventual success"""
        # Create a side effect that raises HTTPError on first call, then succeeds
        mock_open = MagicMock()
        http_error = HTTPError("url", 429, "Too Many Requests", {}, None)
        mock_open.side_effect = [http_error, mock_response]
        
        # Mock time.sleep to avoid waiting during tests
        mock_sleep = MagicMock()
        
        with patch("time.sleep", mock_sleep):
            monkeypatch.setattr(mw_api.opener, "open", mock_open)
            
            # Call _fetch with a URL
            result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)
            
            # Verify the result
            assert result == b"test data"
            assert mock_open.call_count == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_fetch_http_500_retry_success(self, mw_api, mock_response, monkeypatch):
        """Test retry on HTTP 500 error with eventual success"""
        # Create a side effect that raises HTTPError on first call, then succeeds
        mock_open = MagicMock()
        http_error = HTTPError("url", 500, "Internal Server Error", {}, None)
        mock_open.side_effect = [http_error, mock_response]
        
        # Mock time.sleep to avoid waiting during tests
        mock_sleep = MagicMock()
        
        with patch("time.sleep", mock_sleep):
            monkeypatch.setattr(mw_api.opener, "open", mock_open)
            
            # Call _fetch with a URL
            result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)
            
            # Verify the result
            assert result == b"test data"
            assert mock_open.call_count == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_fetch_url_error_retry_success(self, mw_api, mock_response, monkeypatch):
        """Test retry on URLError with eventual success"""
        # Create a side effect that raises URLError on first call, then succeeds
        mock_open = MagicMock()
        url_error = URLError("Connection refused")
        mock_open.side_effect = [url_error, mock_response]
        
        # Mock time.sleep to avoid waiting during tests
        mock_sleep = MagicMock()
        
        with patch("time.sleep", mock_sleep):
            monkeypatch.setattr(mw_api.opener, "open", mock_open)
            
            # Call _fetch with a URL
            result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)
            
            # Verify the result
            assert result == b"test data"
            assert mock_open.call_count == 2
            assert mock_sleep.called
            # Verify that sleep was called with the initial delay
            mock_sleep.assert_called_with(1)

    def test_fetch_http_429_max_retries_exceeded(self, mw_api, monkeypatch):
        """Test HTTP 429 error with max retries exceeded"""
        # Create a side effect that always raises HTTPError
        mock_open = MagicMock()
        http_error = HTTPError("url", 429, "Too Many Requests", {}, None)
        mock_open.side_effect = http_error
        
        # Mock time.sleep to avoid waiting during tests
        mock_sleep = MagicMock()
        
        with patch("time.sleep", mock_sleep):
            monkeypatch.setattr(mw_api.opener, "open", mock_open)
            
            # Call _fetch with a URL and expect HTTPError
            with pytest.raises(HTTPError) as excinfo:
                mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)
            
            # Verify the error
            assert excinfo.value.code == 429
            # Verify that open was called max_retries + 1 times (initial + retries)
            assert mock_open.call_count == 3
            # Verify that sleep was called max_retries times
            assert mock_sleep.call_count == 2
            # Verify that sleep was called with increasing delays (exponential backoff)
            mock_sleep.assert_any_call(1)  # First retry
            mock_sleep.assert_any_call(2)  # Second retry (1 * 2)

    def test_fetch_http_404_no_retry(self, mw_api, monkeypatch):
        """Test HTTP 404 error with no retry (non-retryable error)"""
        # Create a side effect that raises HTTPError
        mock_open = MagicMock()
        http_error = HTTPError("url", 404, "Not Found", {}, None)
        mock_open.side_effect = http_error
        
        # Mock time.sleep to verify it's not called
        mock_sleep = MagicMock()
        
        with patch("time.sleep", mock_sleep):
            monkeypatch.setattr(mw_api.opener, "open", mock_open)
            
            # Call _fetch with a URL and expect HTTPError
            with pytest.raises(HTTPError) as excinfo:
                mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)
            
            # Verify the error
            assert excinfo.value.code == 404
            # Verify that open was called only once (no retries)
            assert mock_open.call_count == 1
            # Verify that sleep was not called
            assert not mock_sleep.called

    def test_fetch_other_exception_no_retry(self, mw_api, monkeypatch):
        """Test other exception with no retry"""
        # Create a side effect that raises a general exception
        mock_open = MagicMock()
        mock_open.side_effect = Exception("Test exception")
        
        # Mock time.sleep to verify it's not called
        mock_sleep = MagicMock()
        
        with patch("time.sleep", mock_sleep):
            monkeypatch.setattr(mw_api.opener, "open", mock_open)
            
            # Call _fetch with a URL and expect Exception
            with pytest.raises(Exception) as excinfo:
                mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", max_retries=2)
            
            # Verify the error
            assert str(excinfo.value) == "Test exception"
            # Verify that open was called only once (no retries)
            assert mock_open.call_count == 1
            # Verify that sleep was not called
            assert not mock_sleep.called

    def test_fetch_exponential_backoff(self, mw_api, mock_response, monkeypatch):
        """Test exponential backoff with multiple retries"""
        # Create a side effect that raises HTTPError twice, then succeeds
        mock_open = MagicMock()
        http_error = HTTPError("url", 429, "Too Many Requests", {}, None)
        mock_open.side_effect = [http_error, http_error, mock_response]
        
        # Mock time.sleep to verify exponential backoff
        mock_sleep = MagicMock()
        
        with patch("time.sleep", mock_sleep):
            monkeypatch.setattr(mw_api.opener, "open", mock_open)
            
            # Call _fetch with a URL
            result = mw_api._fetch("https://test.wikipedia.org/w/api.php?action=query", 
                                  max_retries=3, initial_delay=2, backoff_factor=3)
            
            # Verify the result
            assert result == b"test data"
            assert mock_open.call_count == 3
            # Verify that sleep was called with increasing delays (exponential backoff)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(2)  # First retry (initial_delay)
            mock_sleep.assert_any_call(6)  # Second retry (initial_delay * backoff_factor)

    def test_fetch_with_request_object(self, mw_api, mock_response, monkeypatch):
        """Test fetch with a Request object instead of a URL string"""
        # Mock the opener.open method to return a successful response
        monkeypatch.setattr(mw_api.opener, "open", lambda url: mock_response)
        
        # Create a Request object
        req = Request("https://test.wikipedia.org/w/api.php?action=query")
        
        # Call _fetch with the Request object
        result = mw_api._fetch(req)
        
        # Verify the result
        assert result == b"test data"
        assert mock_response.read.called
        assert mock_response.close.called
