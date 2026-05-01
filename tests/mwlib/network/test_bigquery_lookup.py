"""Unit tests for mwlib.network.bigquery_lookup module."""

from unittest.mock import MagicMock, patch

import pytest


class FakeConf:
    """Minimal conf stub for testing BigQueryImageLookup."""

    def __init__(self, overrides=None):
        self._data = {
            ("bigquery", "project"): "test-project",
            ("bigquery", "dataset"): "wme_snapshots",
            ("bigquery", "table"): "file_pages",
            ("bigquery", "timeout"): "30",
            ("bigquery", "domains"): "en.wikipedia.org",
        }
        if overrides:
            self._data.update(overrides)

    def get(self, section, option, fallback=None, type_=str):
        val = self._data.get((section, option), fallback)
        if type_ is int and val is not None:
            return int(val)
        return val


class TestBigQueryImageLookup:
    """Tests for the BigQueryImageLookup class."""

    @patch("mwlib.network.bigquery_lookup.BigQueryImageLookup._init_client")
    def _make_lookup(self, mock_init, conf=None, client=None):
        from mwlib.network.bigquery_lookup import BigQueryImageLookup

        mock_init.return_value = None
        lookup = BigQueryImageLookup(conf=conf or FakeConf())
        lookup._client = client
        return lookup

    def test_is_available_with_client(self):
        lookup = self._make_lookup(client=MagicMock())
        assert lookup.is_available is True

    def test_is_available_without_client(self):
        lookup = self._make_lookup(client=None)
        assert lookup.is_available is False

    def test_handles_domain_match(self):
        lookup = self._make_lookup(client=MagicMock())
        assert lookup.handles_domain("https://en.wikipedia.org/wiki/File:Test.jpg") is True

    def test_handles_domain_no_match(self):
        lookup = self._make_lookup(client=MagicMock())
        assert lookup.handles_domain("https://commons.wikimedia.org/wiki/File:Test.jpg") is False

    def test_handles_domain_multiple_domains(self):
        conf = FakeConf({("bigquery", "domains"): "en.wikipedia.org, de.wikipedia.org"})
        lookup = self._make_lookup(conf=conf, client=MagicMock())
        assert lookup.handles_domain("https://de.wikipedia.org/wiki/File:Test.jpg") is True
        assert lookup.handles_domain("https://fr.wikipedia.org/wiki/File:Test.jpg") is False

    def test_handles_domain_rejects_substring_lookalikes(self):
        """Lookalike hostnames containing the configured domain must not match.

        A naive ``domain in path`` check would accept attacker-controlled
        hostnames that contain the configured one as a substring, leaking
        fetches for unrelated wikis through the BigQuery path.
        """
        lookup = self._make_lookup(client=MagicMock())
        # Attacker-controlled subdomain that contains the configured one
        assert lookup.handles_domain("https://en.wikipedia.org.example.com/path") is False
        # Hyphen prefix
        assert lookup.handles_domain("https://evil-en.wikipedia.org/path") is False
        # Configured host appearing in the path component of an unrelated host
        assert lookup.handles_domain("https://other.example.com/en.wikipedia.org/x") is False

    def test_handles_domain_accepts_bare_hostname(self):
        """Callers sometimes pass just a hostname (no scheme); still match."""
        lookup = self._make_lookup(client=MagicMock())
        assert lookup.handles_domain("en.wikipedia.org") is True
        assert lookup.handles_domain("commons.wikimedia.org") is False

    def test_handles_domain_normalizes_uppercase_config(self):
        """Hostnames are case-insensitive — uppercase config must still match."""
        conf = FakeConf({("bigquery", "domains"): "EN.Wikipedia.ORG"})
        lookup = self._make_lookup(conf=conf, client=MagicMock())
        assert lookup.handles_domain("https://en.wikipedia.org/wiki/File:X.jpg") is True
        assert lookup.handles_domain("https://EN.WIKIPEDIA.ORG/wiki/File:X.jpg") is True

    def test_handles_domain_strips_port_from_url(self):
        """``urlparse(...).netloc`` includes the port; ``.hostname`` doesn't.

        Without this fix, the perfectly normal ``https://en.wikipedia.org:443/x``
        would miss the configured ``en.wikipedia.org`` set.
        """
        lookup = self._make_lookup(client=MagicMock())
        assert lookup.handles_domain("https://en.wikipedia.org:443/wiki/File:X.jpg") is True
        # Userinfo + port shouldn't fool it either.
        assert lookup.handles_domain("https://user:pass@en.wikipedia.org:8080/x") is True

    def test_fetch_batch_empty_titles(self):
        lookup = self._make_lookup(client=MagicMock())
        rows, missing = lookup.fetch_batch([])
        assert rows == []
        assert missing == []

    def test_fetch_batch_no_client(self):
        lookup = self._make_lookup(client=None)
        titles = ["File:A.jpg", "File:B.jpg"]
        rows, missing = lookup.fetch_batch(titles)
        assert rows == []
        assert missing == titles

    def test_fetch_batch_all_found(self):
        lookup = self._make_lookup(client=MagicMock())

        mock_rows = [
            {
                "name": "File:A.jpg",
                "templates": ["cc-by-sa"],
                "image_width": 800,
                "image_height": 600,
            },
            {
                "name": "File:B.jpg",
                "templates": ["pd-old"],
                "image_width": 1024,
                "image_height": 768,
            },
        ]
        with patch.object(lookup, "_execute_query", return_value=(mock_rows, [])):
            rows, missing = lookup.fetch_batch(["File:A.jpg", "File:B.jpg"])
        assert len(rows) == 2
        assert missing == []
        assert rows[0]["name"] == "File:A.jpg"
        assert rows[1]["name"] == "File:B.jpg"

    def test_fetch_batch_partial_results(self):
        lookup = self._make_lookup(client=MagicMock())

        mock_rows = [{"name": "File:A.jpg", "templates": ["cc-by-sa"]}]
        with patch.object(lookup, "_execute_query", return_value=(mock_rows, ["File:B.jpg"])):
            rows, missing = lookup.fetch_batch(["File:A.jpg", "File:B.jpg"])
        assert len(rows) == 1
        assert missing == ["File:B.jpg"]

    def test_fetch_batch_none_found(self):
        lookup = self._make_lookup(client=MagicMock())

        with patch.object(
            lookup, "_execute_query", return_value=([], ["File:A.jpg", "File:B.jpg"])
        ):
            rows, missing = lookup.fetch_batch(["File:A.jpg", "File:B.jpg"])
        assert rows == []
        assert missing == ["File:A.jpg", "File:B.jpg"]

    def test_fetch_batch_error_graceful_fallback(self):
        lookup = self._make_lookup(client=MagicMock())

        with patch.object(lookup, "_execute_query", side_effect=Exception("BigQuery timeout")):
            rows, missing = lookup.fetch_batch(["File:A.jpg", "File:B.jpg"])
        assert rows == []
        assert missing == ["File:A.jpg", "File:B.jpg"]

    def test_config_values(self):
        conf = FakeConf(
            {
                ("bigquery", "project"): "my-project",
                ("bigquery", "dataset"): "my_dataset",
                ("bigquery", "table"): "my_table",
                ("bigquery", "timeout"): "60",
                ("bigquery", "domains"): "en.wikipedia.org,de.wikipedia.org",
            }
        )
        lookup = self._make_lookup(conf=conf, client=MagicMock())
        assert lookup.project == "my-project"
        assert lookup.dataset == "my_dataset"
        assert lookup.table == "my_table"
        assert lookup.timeout == 60
        assert lookup.domains == {"en.wikipedia.org", "de.wikipedia.org"}

    def test_execute_query_called_with_titles(self):
        lookup = self._make_lookup(client=MagicMock())

        with patch.object(
            lookup, "_execute_query", return_value=([], ["File:Test.jpg"])
        ) as mock_eq:
            lookup.fetch_batch(["File:Test.jpg"])
        mock_eq.assert_called_once_with(["File:Test.jpg"])

    # ---- Identifier validation (Major: SQL identifier injection) ----

    def test_validate_bigquery_identifier_accepts_normal_names(self):
        from mwlib.network.bigquery_lookup import _validate_bigquery_identifier

        assert _validate_bigquery_identifier("my_dataset", "dataset") == "my_dataset"
        assert _validate_bigquery_identifier("project-123", "project") == "project-123"
        assert _validate_bigquery_identifier("file_pages", "table") == "file_pages"

    def test_validate_bigquery_identifier_rejects_injection_attempts(self):
        from mwlib.network.bigquery_lookup import _validate_bigquery_identifier

        # Backticks would close ``table_ref`` early.
        with pytest.raises(ValueError):
            _validate_bigquery_identifier("foo`; DROP TABLE x; --", "table")
        # Whitespace and SQL keywords mustn't slip through.
        for bad in (
            "",
            " ",
            "1leading_digit",
            "with space",
            "with;semicolon",
            "with.dot",
            "back`tick",
            "quote'inject",
        ):
            with pytest.raises(ValueError):
                _validate_bigquery_identifier(bad, "table")

    def test_execute_query_rejects_invalid_project(self):
        """A misconfigured project shouldn't be silently interpolated into SQL."""
        conf = FakeConf({("bigquery", "project"): "evil`; DROP TABLE x; --"})
        lookup = self._make_lookup(conf=conf, client=MagicMock())
        with pytest.raises(ValueError):
            lookup._execute_query(["File:X.jpg"])

    # ---- Row-mismatch handling (Major: deferred-download leak) ----

    def test_execute_query_drops_rows_not_in_request(self):
        """Rows whose ``name`` wasn't requested are discarded.

        If BigQuery ever returns a normalized name (different casing,
        different namespace) the requested title is left in ``missing``
        so the caller falls back to the remote API and any state keyed
        on the original title stays reachable.
        """
        lookup = self._make_lookup(conf=FakeConf(), client=MagicMock())

        # BigQuery returns a row with a normalized (lower-case) name; the
        # caller asked for the title-cased version.
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = [{"name": "File:example.jpg", "templates": []}]
        lookup._client.query.return_value = mock_query_job

        rows, missing = lookup._execute_query(["File:Example.JPG"])

        assert rows == []  # the normalized row is discarded
        assert missing == ["File:Example.JPG"]  # original title is missing

    def test_execute_query_returns_only_exact_matches(self):
        """Exact-match rows pass through; mismatches don't poison the result.

        Mixed input must still surface the legitimate rows while routing
        the mismatch to the remote-API fallback.
        """
        lookup = self._make_lookup(conf=FakeConf(), client=MagicMock())

        mock_query_job = MagicMock()
        mock_query_job.result.return_value = [
            {"name": "File:A.jpg", "templates": []},
            {"name": "File:b.jpg", "templates": []},  # mismatched casing — drop
            {"name": "File:C.jpg", "templates": []},
        ]
        lookup._client.query.return_value = mock_query_job

        requested = ["File:A.jpg", "File:B.jpg", "File:C.jpg"]
        rows, missing = lookup._execute_query(requested)

        assert {r["name"] for r in rows} == {"File:A.jpg", "File:C.jpg"}
        assert missing == ["File:B.jpg"]


class TestFetcherBigQueryIntegration:
    """Test BigQuery integration points in the Fetcher class."""

    def _make_fetcher_stub(self, filter_type="blacklist"):
        """Create a minimal object with the Fetcher methods under test."""
        from mwlib.network.fetch import Fetcher
        from mwlib.rendering.licensechecker import LicenseChecker

        stub = object.__new__(Fetcher)
        stub.fetch_license_checker = LicenseChecker(image_db=None, filter_type=filter_type)
        stub.fetch_license_checker.read_licenses_csv()
        stub.scheduled = set()
        stub._bq_deferred_downloads = {}
        stub._bq_pending = []
        stub._bq_batch_size = 50
        stub.bq_lookup = MagicMock()
        stub.bq_lookup.is_available = True
        stub.fsout = MagicMock()
        return stub

    def test_check_license_free_passes(self):
        """Free license templates should pass the blacklist filter."""
        stub = self._make_fetcher_stub(filter_type="blacklist")
        assert stub._check_license_from_templates(["cc-by-sa"]) is True

    def test_check_license_nonfree_blocked_by_blacklist(self):
        """Nonfree templates should be blocked by blacklist filter."""
        stub = self._make_fetcher_stub(filter_type="blacklist")
        assert stub._check_license_from_templates(["non-free logo"]) is False

    def test_check_license_unknown_passes_blacklist(self):
        """Unknown templates should pass blacklist filter."""
        stub = self._make_fetcher_stub(filter_type="blacklist")
        assert stub._check_license_from_templates(["some-unknown-xyz"]) is True

    def test_check_license_unknown_blocked_by_whitelist(self):
        """Unknown templates should be blocked by whitelist filter."""
        stub = self._make_fetcher_stub(filter_type="whitelist")
        assert stub._check_license_from_templates(["some-unknown-xyz"]) is False

    def test_check_license_no_checker(self):
        """Without a license checker, all images pass."""
        stub = self._make_fetcher_stub()
        stub.fetch_license_checker = None
        assert stub._check_license_from_templates(["non-free logo"]) is True

    def test_store_bq_result_writes_templates(self):
        """_store_bq_result should write templates to templates.db."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")

        row = {
            "name": "File:X.jpg",
            "templates": ["cc-by-sa", "information"],
            "image_content_url": "https://upload.wikimedia.org/X.jpg",
            "image_width": 800,
            "image_height": 600,
            "url": "https://en.wikipedia.org/wiki/File:X.jpg",
        }
        result = stub._store_bq_result(row)

        assert result is True  # cc-by-sa is free
        stub.fsout.set_db_key.assert_any_call(
            "templates", "File:X.jpg", ["cc-by-sa", "information"]
        )

    def test_store_bq_result_supplements_imageinfo(self):
        """_store_bq_result should supplement imageinfo with BQ data."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")

        row = {
            "name": "File:X.jpg",
            "templates": [],
            "image_content_url": "https://upload.wikimedia.org/X.jpg",
            "image_width": 800,
            "image_height": 600,
            "url": "https://en.wikipedia.org/wiki/File:X.jpg",
        }
        stub._store_bq_result(row)

        # Check that imageinfo was written with supplemented data
        calls = stub.fsout.set_db_key.call_args_list
        imageinfo_calls = [c for c in calls if c[0][0] == "imageinfo"]
        assert len(imageinfo_calls) == 1
        written = imageinfo_calls[0][0][2]
        assert written["url"] == "https://upload.wikimedia.org/X.jpg"
        assert written["width"] == 800
        assert written["height"] == 600
        assert written["descriptionurl"] == "https://en.wikipedia.org/wiki/File:X.jpg"

    def test_store_bq_result_nonfree_returns_false(self):
        """_store_bq_result should return False for nonfree images."""
        stub = self._make_fetcher_stub(filter_type="blacklist")
        stub.fsout.get_db_key.side_effect = KeyError("not found")

        row = {"name": "File:X.jpg", "templates": ["non-free logo"]}
        assert stub._store_bq_result(row) is False

    # ---- Round 6: malformed BQ templates fail closed ----

    def test_store_bq_result_raises_on_malformed_templates_json(self):
        """Unparsable templates JSON must NOT be treated as 'no templates'.

        An empty templates list passes ``blacklist`` mode, so silently
        treating corrupt data as empty would fail open and let through
        images the remote description-page parser may have rejected.
        Instead the row raises ``BqTemplatesError`` and the flush loop
        reroutes the title to the remote-API fallback.
        """
        from mwlib.network.fetch import BqTemplatesError

        stub = self._make_fetcher_stub()
        row = {"name": "File:X.jpg", "templates": "not-valid-json{"}

        with pytest.raises(BqTemplatesError):
            stub._store_bq_result(row)

        # Nothing was persisted — the title will be redriven via the
        # remote API by ``_flush_bq_batch``.
        stub.fsout.set_db_key.assert_not_called()

    def test_store_bq_result_raises_on_unexpected_templates_shape(self):
        """A non-list, non-string templates value also fails closed."""
        from mwlib.network.fetch import BqTemplatesError

        stub = self._make_fetcher_stub()
        row = {"name": "File:X.jpg", "templates": {"unexpected": "shape"}}

        with pytest.raises(BqTemplatesError):
            stub._store_bq_result(row)
        stub.fsout.set_db_key.assert_not_called()

    def test_flush_bq_batch_reroutes_corrupt_row_to_fallback(self, monkeypatch):
        """Corrupt BQ rows are added to ``missing`` so the remote API runs."""
        stub = self._make_fetcher_stub()
        stub.schedule_download_image = MagicMock()
        stub._refcall = MagicMock()

        api = MagicMock()
        api.api_request_limit = 50
        stub._bq_pending = [("File:X.jpg", api, "File:X.jpg")]
        stub.bq_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": "not-valid-json{"}],
            [],
        )

        stub._flush_bq_batch()

        # Corrupt row routed to fetch_image_page via the missing-fallback path.
        called_funcs = {call.args[0] for call in stub._refcall.call_args_list}
        assert stub.fetch_image_page in called_funcs

    def test_store_bq_result_writes_empty_list_as_negative_cache(self):
        """An empty templates list is stored, not skipped.

        Without this, render-time ``get_image_templates_and_args`` would
        fall through to wikitext parsing for an image we deliberately
        decided not to fetch — which is exactly what the BigQuery cache
        is supposed to avoid.
        """
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")

        row = {"name": "File:NoTemplates.jpg", "templates": []}
        stub._store_bq_result(row)

        stub.fsout.set_db_key.assert_any_call("templates", "File:NoTemplates.jpg", [])

    def test_extract_bq_template_names_strips_template_prefix(self):
        from mwlib.network.fetch import Fetcher

        names = Fetcher._extract_bq_template_names(
            "File:X.jpg",
            [
                {"name": "Template:Cc-by-sa", "url": "..."},
                {"name": "Information"},
                "raw-string-name",
            ],
        )
        assert names == ["Cc-by-sa", "Information", "raw-string-name"]

    def test_extract_bq_template_names_handles_none(self):
        from mwlib.network.fetch import Fetcher

        assert Fetcher._extract_bq_template_names("File:X.jpg", None) == []

    def test_flush_bq_batch_schedules_free_downloads(self):
        """_flush_bq_batch should schedule downloads for free-licensed images."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()

        stub._bq_deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        stub._bq_pending = [("File:X.jpg", MagicMock(), "File:X.jpg")]

        stub.bq_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": ["cc-by-sa"]}],
            [],
        )
        stub._flush_bq_batch()

        stub.schedule_download_image.assert_called_once_with("https://thumb/X.jpg", "File:X.jpg")

    def test_flush_bq_batch_skips_nonfree_downloads(self):
        """_flush_bq_batch should skip downloads for nonfree images."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()

        stub._bq_deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        stub._bq_pending = [("File:X.jpg", MagicMock(), "File:X.jpg")]

        stub.bq_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": ["non-free logo"]}],
            [],
        )
        stub._flush_bq_batch()

        stub.schedule_download_image.assert_not_called()
        assert "File:X.jpg" not in stub._bq_deferred_downloads

    def test_flush_bq_batch_fallback_for_missing(self):
        """_flush_bq_batch should fall back to remote API for missing titles."""
        from mwlib.network.fetch import Fetcher

        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()
        stub._refcall = MagicMock()

        mock_api = MagicMock()
        mock_api.api_request_limit = 50
        stub._bq_deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        stub._bq_pending = [("File:X.jpg", mock_api, "File:X.jpg")]

        stub.bq_lookup.fetch_batch.return_value = ([], ["File:X.jpg"])
        stub._flush_bq_batch()

        # Should call fetch_image_page via _refcall for missing titles
        stub._refcall.assert_called()
        # Should schedule deferred download for fallback title
        stub.schedule_download_image.assert_called_once_with("https://thumb/X.jpg", "File:X.jpg")

    def test_flush_bq_batch_title_mapping(self):
        """_flush_bq_batch should map local names back to original titles for deferred downloads."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()

        # Simulate namespace conversion: original "File:X.jpg" → local "Datei:X.jpg"
        stub._bq_deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        stub._bq_pending = [("Datei:X.jpg", MagicMock(), "File:X.jpg")]

        stub.bq_lookup.fetch_batch.return_value = (
            [{"name": "Datei:X.jpg", "templates": ["cc-by-sa"]}],
            [],
        )
        stub._flush_bq_batch()

        # Download should be scheduled using original title
        stub.schedule_download_image.assert_called_once_with("https://thumb/X.jpg", "File:X.jpg")

    def test_flush_bq_batch_deduplicates_titles(self):
        """_flush_bq_batch should deduplicate titles before querying BigQuery."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()

        mock_api = MagicMock()
        # Same title appears twice
        stub._bq_pending = [
            ("File:X.jpg", mock_api, "File:X.jpg"),
            ("File:X.jpg", mock_api, "File:X.jpg"),
        ]

        stub.bq_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": ["cc-by-sa"]}],
            [],
        )
        stub._flush_bq_batch()

        # Should only query once for the deduplicated title
        call_args = stub.bq_lookup.fetch_batch.call_args[0][0]
        assert call_args == ["File:X.jpg"]


class TestNuWikiTemplatesDb:
    """Test templates.db shortcircuit in NuWiki."""

    def _make_nuwiki_dir(self, tmp_path, with_templates_db=True, templates_data=None):
        """Create a minimal nuwiki directory for testing."""
        import json as stdlib_json

        from sqlitedict import SqliteDict

        nuwiki_path = tmp_path / "nuwiki"
        nuwiki_path.mkdir()
        (nuwiki_path / "revisions-1.txt").write_text("")
        siteinfo = {
            "namespaces": {
                "6": {"id": 6, "*": "File", "canonical": "File"},
                "0": {"id": 0, "*": "", "content": ""},
            },
            "general": {"lang": "en"},
        }
        (nuwiki_path / "siteinfo.json").write_text(stdlib_json.dumps(siteinfo))
        (nuwiki_path / "imageinfo.db").touch()

        if with_templates_db:
            db = SqliteDict(str(nuwiki_path / "templates.db"), autocommit=True)
            if templates_data:
                for title, templates in templates_data.items():
                    db[title] = stdlib_json.dumps(templates)
            db.close()

        return str(nuwiki_path)

    def test_get_image_templates_and_args_from_templates_db(self, tmp_path):
        """Should return templates from templates.db when available."""
        from mwlib.core.nuwiki import Adapt

        path = self._make_nuwiki_dir(
            tmp_path,
            templates_data={"File:Test.jpg": ["cc-by-sa", "information"]},
        )
        adapt = Adapt(path)

        result = adapt.get_image_templates_and_args("File:Test.jpg")
        assert result == {"cc-by-sa", "information"}

    def test_get_image_templates_and_args_falls_back_without_entry(self, tmp_path):
        """Should fall back to wikitext parsing when templates.db has no entry."""
        from mwlib.core.nuwiki import Adapt

        path = self._make_nuwiki_dir(tmp_path, with_templates_db=True)
        adapt = Adapt(path)

        # No templates.db entry, no description page → should return empty
        result = adapt.get_image_templates_and_args("File:Missing.jpg")
        assert result == []

    def test_get_image_templates_and_args_no_templates_db(self, tmp_path):
        """Should fall back to wikitext parsing when templates.db doesn't exist."""
        from mwlib.core.nuwiki import Adapt

        path = self._make_nuwiki_dir(tmp_path, with_templates_db=False)
        adapt = Adapt(path)

        result = adapt.get_image_templates_and_args("File:Missing.jpg")
        assert result == []

    def test_get_contributors_falls_back_to_authors_db_for_bq_images(self, tmp_path):
        """BigQuery-backed images read attribution from authors.db.

        These images have no description page on disk because the
        BigQuery shortcut skips ``fetch_image_page``. ``get_image_edits``
        still populates ``authors.db`` via the remote contributor lookup;
        this fallback wires the two together so the rendered book isn't
        attribution-empty.
        """
        import json as stdlib_json

        from sqlitedict import SqliteDict

        from mwlib.core.nuwiki import Adapt

        path = self._make_nuwiki_dir(tmp_path)
        # Seed authors.db as if Fetcher.get_image_edits had run.
        authors_db = SqliteDict(str(tmp_path / "nuwiki" / "authors.db"), autocommit=True)
        authors_db["File:BQOnly.jpg"] = stdlib_json.dumps(["Alice", "Bob"])
        authors_db.close()

        adapt = Adapt(path)
        # No description page exists for this image (BQ shortcircuit)…
        assert adapt.get_image_description_page("File:BQOnly.jpg") is None
        # …but contributors are read from authors.db rather than [] returned.
        assert adapt.get_contributors("File:BQOnly.jpg") == ["Alice", "Bob"]

    def test_get_contributors_returns_empty_when_no_authors_either(self, tmp_path):
        """Empty list when neither description page nor authors.db has data.

        Belt-and-braces — the fallback returns ``[]`` instead of raising
        for images we genuinely have no attribution for.
        """
        from mwlib.core.nuwiki import Adapt

        path = self._make_nuwiki_dir(tmp_path)
        adapt = Adapt(path)

        assert adapt.get_contributors("File:Missing.jpg") == []
