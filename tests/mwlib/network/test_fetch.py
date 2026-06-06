"""Tests for the fetch module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mwlib.network import fetch
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
            base_url="https://example.com", use_http2=True
        )

        # Verify that the client's stream method was called with the correct parameters
        mock_client.stream.assert_called_once_with("GET", "https://example.com/file.txt")

        # Verify that the response's iter_bytes method was called
        mock_response.iter_bytes.assert_called_once_with(chunk_size=16384)

        # Verify that the file was created and contains the expected data
        with open(path, "rb") as f:
            assert f.read() == b"test data"

    def test_download_to_file_http2_disabled(
        self, mock_http_client_manager, mock_conf, temp_files
    ):
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
            base_url="https://example.com", use_http2=False
        )

    def test_download_to_file_http2_not_supported(
        self, mock_http_client_manager, mock_conf, temp_files
    ):
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
            base_url="https://example.com", use_http2=False
        )

    def test_download_to_file_auto_detect_disabled(
        self, mock_http_client_manager, mock_conf, temp_files
    ):
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
            base_url="https://example.com", use_http2=True
        )

    def test_download_to_file_http_429_retry(
        self, mock_http_client_manager, mock_conf, temp_files
    ):
        """Test retry mechanism for HTTP 429 errors."""
        _, _, mock_client, mock_response = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock to raise a 429 error on first call, then succeed
        http_error = httpx.HTTPStatusError(
            "429 Too Many Requests", request=MagicMock(), response=MagicMock(status_code=429)
        )

        # Create a side effect that raises an error on first call, then succeeds
        mock_client.stream.side_effect = [
            MagicMock(__enter__=MagicMock(side_effect=http_error)),
            MagicMock(__enter__=MagicMock(return_value=mock_response)),
        ]

        # Call the function with retry parameters
        download_to_file(
            "https://example.com/file.txt", path, temp_path, max_retries=1, initial_delay=0.01
        )

        # Verify that the client's stream method was called twice
        assert mock_client.stream.call_count == 2

    def test_download_to_file_http_error(self, mock_http_client_manager, mock_conf, temp_files):
        """Test handling of HTTP errors."""
        _, _, mock_client, _ = mock_http_client_manager
        path, temp_path = temp_files

        # Configure the mock to raise an HTTP error
        http_error = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock(status_code=404)
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

    def test_download_to_file_applies_rate_limit(
        self, mock_http_client_manager, mock_conf, temp_files
    ):
        """Download requests should respect configured max_requests_per_second."""
        path, temp_path = temp_files

        with patch("mwlib.network.fetch._acquire_download_rate_limit") as mock_rate_limit:
            download_to_file("https://example.com/file.txt", path, temp_path)
            mock_rate_limit.assert_called_once_with("https://example.com/file.txt")

    def test_acquire_download_rate_limit_uses_conf_value(self, mock_conf):
        """Rate limiter should be built from conf.get(fetch, max_requests_per_second)."""
        fetch._download_rate_limiter = {}
        fetch._download_rate_limiter_rps = {}
        mock_conf.get.side_effect = lambda section, name, default, bool: {
            ("fetch", "max_requests_per_second"): 3,
        }.get((section, name), default)

        with patch("mwlib.network.fetch.mwapi.RateLimiter") as mock_rate_limiter_cls:
            mock_rate_limiter = MagicMock()
            mock_rate_limiter_cls.return_value = mock_rate_limiter
            fetch._acquire_download_rate_limit("https://example.com/file.txt")

            mock_rate_limiter_cls.assert_called_once_with(max_calls=3, period=1.0)
            mock_rate_limiter.acquire.assert_called_once_with()


class TestLookupContributors:
    """Regression tests for the contributor-attribution flow.

    The previous implementation accepted ``title`` but iterated the
    pending batch instead — combined with the single-title path no
    longer appending to that batch, every author was silently dropped.
    """

    def _make_stub(self):
        from collections import defaultdict

        from mwlib.network.fetch import Fetcher

        stub = object.__new__(Fetcher)
        stub.titles_pending_contributor_lookup = defaultdict(list)
        stub.title_mapping = {}
        stub.fsout = MagicMock()
        return stub

    def test_single_title_writes_authors(self):
        stub = self._make_stub()
        api = MagicMock()
        inspect = MagicMock()
        inspect.get_authors.return_value = ["Alice", "Bob"]
        api.get_contributors.return_value = {"File:X.jpg": inspect}

        stub._lookup_contributors(api, "File:X.jpg")

        api.get_contributors.assert_called_once_with(["File:X.jpg"])
        stub.fsout.set_db_key.assert_called_once_with("authors", "File:X.jpg", ["Alice", "Bob"])
        # Single-title path must NOT touch the pending batch.
        assert stub.titles_pending_contributor_lookup[api] == []

    def test_single_title_uses_title_mapping(self):
        """Authors are stored under the mapped (local-namespace) title.

        Image titles get rewritten to the local namespace via
        ``title_mapping``; the contributor lookup must honour that.
        """
        stub = self._make_stub()
        stub.title_mapping["File:X.jpg"] = "Datei:X.jpg"
        api = MagicMock()
        inspect = MagicMock()
        inspect.get_authors.return_value = ["Alice"]
        api.get_contributors.return_value = {"File:X.jpg": inspect}

        stub._lookup_contributors(api, "File:X.jpg")

        stub.fsout.set_db_key.assert_called_once_with("authors", "Datei:X.jpg", ["Alice"])

    def test_batch_mode_consumes_pending(self):
        from mwlib.network.fetch import Fetcher  # noqa: F401  (used in stub)

        stub = self._make_stub()
        api = MagicMock()
        stub.titles_pending_contributor_lookup[api] = ["File:A.jpg", "File:B.jpg"]
        inspect_a = MagicMock()
        inspect_a.get_authors.return_value = ["Alice"]
        inspect_b = MagicMock()
        inspect_b.get_authors.return_value = ["Bob"]
        api.get_contributors.return_value = {
            "File:A.jpg": inspect_a,
            "File:B.jpg": inspect_b,
        }

        stub._lookup_contributors(api)

        api.get_contributors.assert_called_once_with(["File:A.jpg", "File:B.jpg"])
        # Both titles' authors written
        keys_written = {
            (call.args[1], tuple(call.args[2])) for call in stub.fsout.set_db_key.call_args_list
        }
        assert ("File:A.jpg", ("Alice",)) in keys_written
        assert ("File:B.jpg", ("Bob",)) in keys_written
        # Batch must be cleared so the next call doesn't re-fetch.
        assert stub.titles_pending_contributor_lookup[api] == []

    def test_redirected_titles_are_skipped(self):
        """Titles missing from the API response are skipped silently.

        E.g. when the page got redirected away — we don't want to raise
        or write a partial entry.
        """
        stub = self._make_stub()
        api = MagicMock()
        api.get_contributors.return_value = {}  # no entry for "File:X.jpg"

        stub._lookup_contributors(api, "File:X.jpg")

        stub.fsout.set_db_key.assert_not_called()

    def test_empty_batch_is_a_noop(self):
        stub = self._make_stub()
        api = MagicMock()

        stub._lookup_contributors(api)

        api.get_contributors.assert_not_called()
        stub.fsout.set_db_key.assert_not_called()


class TestFinishDoesNotFlushBQ:
    """``finish()`` must not run the BigQuery batch flush.

    The flush has been moved into ``run()`` so that the pool can be
    joined a second time and drain greenlets the flush spawns. If
    ``finish()`` were still flushing, those greenlets would be scheduled
    after the last ``pool.join()`` — the original blocker we're
    guarding against.
    """

    def test_finish_does_not_call_flush_bq_batch(self):
        from unittest.mock import MagicMock

        from mwlib.network.fetch import Fetcher

        stub = object.__new__(Fetcher)
        # Pretend there's a pending batch and a working bq_lookup; if
        # finish() were still flushing, this would be the trigger.
        stub.bq_lookup = MagicMock()
        stub._bq_pending = [("File:X.jpg", MagicMock(), "File:X.jpg")]
        stub._flush_bq_batch = MagicMock()
        stub._sanity_check = MagicMock()
        stub.lookup_contributors_for_remaining_titles = MagicMock()
        stub.titles_pending_contributor_lookup = {}
        stub.fsout = MagicMock()
        stub.redirects = {}
        stub.licenses = {}

        stub.finish()

        stub._flush_bq_batch.assert_not_called()
        # The closing side effects we DO expect.
        stub._sanity_check.assert_called_once()
        stub.lookup_contributors_for_remaining_titles.assert_called_once()
        stub.fsout.close.assert_called_once()


class TestGetImageEditsOrdering:
    """``get_image_edits`` must populate ``title_mapping`` before lookup.

    Otherwise authors land under the remote namespace title rather than
    the local one. The previous round only fixed ``_lookup_contributors``
    to use the passed title; ``get_image_edits`` still ordered the
    mapping update *after* the (immediate) contributor lookup.
    """

    def _make_stub(self):
        from collections import defaultdict
        from unittest.mock import MagicMock

        from mwlib.network.fetch import Fetcher

        stub = object.__new__(Fetcher)
        stub.titles_pending_contributor_lookup = defaultdict(list)
        stub.title_mapping = {}
        stub.fsout = MagicMock()
        # Minimal nshandler that returns the local file namespace name.
        stub.nshandler = MagicMock()
        stub.nshandler.get_nsname_by_number.return_value = "Datei"
        return stub

    def test_authors_stored_under_local_title(self):
        from unittest.mock import MagicMock

        stub = self._make_stub()
        api = MagicMock()
        inspect = MagicMock()
        inspect.get_authors.return_value = ["Alice"]
        api.get_contributors.return_value = {"File:X.jpg": inspect}

        stub.get_image_edits("File:X.jpg", api)

        # Mapping must be set; authors written under the local title.
        assert stub.title_mapping["File:X.jpg"] == "Datei:X.jpg"
        stub.fsout.set_db_key.assert_called_once_with("authors", "Datei:X.jpg", ["Alice"])


class TestFetcherInstanceState:
    """Per-instance state mustn't leak across Fetcher instances."""

    def test_pending_lookup_is_per_instance(self):
        from collections import defaultdict

        from mwlib.network.fetch import Fetcher

        a = object.__new__(Fetcher)
        a.titles_pending_contributor_lookup = defaultdict(list)
        a.title_mapping = {}
        b = object.__new__(Fetcher)
        b.titles_pending_contributor_lookup = defaultdict(list)
        b.title_mapping = {}

        api = MagicMock()
        a.titles_pending_contributor_lookup[api].append("only-on-a")
        a.title_mapping["only-on-a"] = "mapped-a"

        # Instance b must NOT see anything from a.
        assert b.titles_pending_contributor_lookup[api] == []
        assert b.title_mapping == {}


class TestFsOutputResume:
    """Resumable fetch reopen behaviour.

    An interrupted attempt must be able to reopen its output directory and skip
    work already on disk (images, dbs, revisions) instead of restarting.
    """

    def test_fresh_output_refuses_existing_dir(self, tmp_path):
        base = str(tmp_path / "nuwiki")
        fetch.FsOutput(base).close()
        # A second fresh FsOutput on the same path is an error.
        with pytest.raises(ValueError, match="output path exists"):
            fetch.FsOutput(base)

    def test_resume_reopens_existing_dir(self, tmp_path):
        base = str(tmp_path / "nuwiki")
        first = fetch.FsOutput(base)
        first.set_db_key("html", "Page", {"a": 1})
        first.close()

        # Resume must not raise and must preserve the existing db contents.
        resumed = fetch.FsOutput(base, resume=True)
        assert resumed.resume is True
        assert resumed.get_db_key("html", "Page") == {"a": 1}
        resumed.close()

    def test_resume_on_missing_path_is_fresh(self, tmp_path):
        base = str(tmp_path / "does-not-exist-yet")
        out = fetch.FsOutput(base, resume=True)
        # No existing dir → behaves as a fresh fetch, not a resume.
        assert out.resume is False
        assert os.path.isdir(os.path.join(base, "images"))
        out.close()

    def test_resume_keeps_downloaded_images(self, tmp_path):
        base = str(tmp_path / "nuwiki")
        out = fetch.FsOutput(base)
        out.close()
        img = os.path.join(base, "images", "File-existing.jpg")
        with open(img, "wb") as fh:
            fh.write(b"JPEGDATA")
        # Reopening with resume must leave the image untouched.
        fetch.FsOutput(base, resume=True).close()
        assert os.path.exists(img)
        with open(img, "rb") as fh:
            assert fh.read() == b"JPEGDATA"

    def test_resume_loads_seen_from_revfile(self, tmp_path):
        base = str(tmp_path / "nuwiki")
        out = fetch.FsOutput(base)
        # Write a revision block in the same format _extract_revisions uses.
        import mwlib.utils.myjson as mwjson

        rev = {"title": "Mainz", "ns": 0, "revid": 12345}
        out.revfile.write("\n --page-- %s\n" % mwjson.dumps(rev, sort_keys=True))
        out.revfile.write("body text")
        out.close()

        resumed = fetch.FsOutput(base, resume=True)
        # Both the revid and the title must be marked seen so the revision
        # isn't appended a second time on resume.
        assert 12345 in resumed.seen
        assert "Mainz" in resumed.seen
        resumed.close()


class TestImageAlreadyDownloaded:
    def test_true_for_nonempty_file(self, tmp_path):
        p = str(tmp_path / "img.jpg")
        with open(p, "wb") as fh:
            fh.write(b"x")
        assert fetch.FsOutput.image_already_downloaded(p) is True

    def test_false_for_missing_file(self, tmp_path):
        assert fetch.FsOutput.image_already_downloaded(str(tmp_path / "nope.jpg")) is False

    def test_false_for_empty_file(self, tmp_path):
        p = str(tmp_path / "empty.jpg")
        open(p, "wb").close()
        assert fetch.FsOutput.image_already_downloaded(p) is False


class TestDownloadImageSkipsExisting:
    """Resume skips re-downloading images already on disk.

    ``_download_image`` must not re-spawn a download for an image a prior
    attempt already fetched — this is what makes a resumed fetch fast.
    """

    def _stub_with_fsout(self, base, resume=False):
        from mwlib.network.fetch import Fetcher

        stub = object.__new__(Fetcher)
        stub.fsout = fetch.FsOutput(base, resume=resume)
        stub.image_download_pool = MagicMock()
        stub.pool = MagicMock()
        return stub

    def test_skips_existing_image(self, tmp_path):
        base = str(tmp_path / "nuwiki")
        stub = self._stub_with_fsout(base)
        title = "File:Existing.jpg"
        path = stub.fsout.get_imagepath(title)
        with open(path, "wb") as fh:
            fh.write(b"already-here")

        stub._download_image("http://example/img.jpg", title)

        stub.image_download_pool.spawn.assert_not_called()
        stub.pool.add.assert_not_called()
        stub.fsout.close()

    def test_downloads_missing_image(self, tmp_path):
        base = str(tmp_path / "nuwiki")
        stub = self._stub_with_fsout(base)

        stub._download_image("http://example/img.jpg", "File:Missing.jpg")

        stub.image_download_pool.spawn.assert_called_once()
        stub.pool.add.assert_called_once()
        stub.fsout.close()
