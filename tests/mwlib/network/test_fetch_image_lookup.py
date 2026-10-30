"""Fetcher integration with the file store image lookup."""

import json as stdlib_json
from unittest.mock import MagicMock

import pytest
from sqlitedict import SqliteDict

from mwlib.core.nuwiki import Adapt
from mwlib.network.fetch import Fetcher, TemplatesError
from mwlib.rendering.licensechecker import LicenseChecker

WIDTH = 800
HEIGHT = 600


class TestFetcherFileStoreIntegration:
    """Test file store integration points in the Fetcher class."""

    def _make_fetcher_stub(self, filter_type="blacklist"):
        """Create a minimal object with the Fetcher methods under test."""
        stub = object.__new__(Fetcher)
        stub.fetch_license_checker = LicenseChecker(image_db=None, filter_type=filter_type)
        stub.fetch_license_checker.read_licenses_csv()
        stub.scheduled = set()
        stub._deferred_downloads = {}
        stub._lookup_pending = []
        stub._lookup_batch_size = 50
        stub.image_lookup = MagicMock()
        stub.image_lookup.is_available = True
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

    def test_filter_type_for_apiurl_uses_exact_hostname(self):
        """``de.wikipedia.org`` → whitelist, anything else → blacklist.

        Done with ``urlparse(...).hostname`` comparison so a lookalike
        URL can't flip the policy by containing the substring.
        """
        assert Fetcher._filter_type_for_apiurl("https://de.wikipedia.org/w/api.php") == "whitelist"
        assert Fetcher._filter_type_for_apiurl("https://en.wikipedia.org/w/api.php") == "blacklist"
        # Lookalike: substring of the netloc but NOT the hostname.
        assert (
            Fetcher._filter_type_for_apiurl("https://de.wikipedia.org.evil.example/w/api.php")
            == "blacklist"
        )
        assert (
            Fetcher._filter_type_for_apiurl("https://evil-de.wikipedia.org/w/api.php")
            == "blacklist"
        )
        # Configured hostname appearing only in the path.
        assert (
            Fetcher._filter_type_for_apiurl("https://other.example/de.wikipedia.org/api.php")
            == "blacklist"
        )

    def test_license_checker_public_helper_matches_render_policy(self):
        """Public helper produces the same answers as fetch-time wrapper.

        ``decide_from_template_names`` is the public seam — fetch-time
        callers go through it instead of poking ``_get_licenses`` from
        outside the class.
        """
        checker = LicenseChecker(image_db=None, filter_type="blacklist")
        checker.read_licenses_csv()

        assert checker.decide_from_template_names(["cc-by-sa"]) is True
        assert checker.decide_from_template_names(["non-free logo"]) is False
        assert checker.decide_from_template_names(["never-heard-of-this"]) is True

        whitelist = LicenseChecker(image_db=None, filter_type="whitelist")
        whitelist.read_licenses_csv()
        assert whitelist.decide_from_template_names(["never-heard-of-this"]) is False

    def test_store_lookup_result_writes_templates(self):
        """_store_lookup_result should write templates to templates.db."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")

        row = {
            "name": "File:X.jpg",
            "templates": ["cc-by-sa", "information"],
            "image_content_url": "https://upload.wikimedia.org/X.jpg",
            "image_width": WIDTH,
            "image_height": HEIGHT,
            "url": "https://en.wikipedia.org/wiki/File:X.jpg",
        }
        result = stub._store_lookup_result(row)

        assert result is True  # cc-by-sa is free
        stub.fsout.set_db_key.assert_any_call(
            "templates", "File:X.jpg", ["cc-by-sa", "information"]
        )

    def test_store_lookup_result_supplements_imageinfo(self):
        """_store_lookup_result should supplement imageinfo with store data."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")

        row = {
            "name": "File:X.jpg",
            "templates": [],
            "image_content_url": "https://upload.wikimedia.org/X.jpg",
            "image_width": WIDTH,
            "image_height": HEIGHT,
            "url": "https://en.wikipedia.org/wiki/File:X.jpg",
        }
        stub._store_lookup_result(row)

        # Check that imageinfo was written with supplemented data
        calls = stub.fsout.set_db_key.call_args_list
        imageinfo_calls = [c for c in calls if c[0][0] == "imageinfo"]
        assert len(imageinfo_calls) == 1
        written = imageinfo_calls[0][0][2]
        assert written["url"] == "https://upload.wikimedia.org/X.jpg"
        assert written["width"] == WIDTH
        assert written["height"] == HEIGHT
        assert written["descriptionurl"] == "https://en.wikipedia.org/wiki/File:X.jpg"

    def test_store_lookup_result_nonfree_returns_false(self):
        """_store_lookup_result should return False for nonfree images."""
        stub = self._make_fetcher_stub(filter_type="blacklist")
        stub.fsout.get_db_key.side_effect = KeyError("not found")

        row = {"name": "File:X.jpg", "templates": ["non-free logo"]}
        assert stub._store_lookup_result(row) is False

    # ---- Round 6: malformed store templates fail closed ----

    def test_store_lookup_result_raises_on_malformed_templates_json(self):
        """Unparsable templates JSON must NOT be treated as 'no templates'.

        An empty templates list passes ``blacklist`` mode, so silently
        treating corrupt data as empty would fail open and let through
        images the remote description-page parser may have rejected.
        Instead the row raises ``TemplatesError`` and the flush loop
        reroutes the title to the remote-API fallback.
        """
        stub = self._make_fetcher_stub()
        row = {"name": "File:X.jpg", "templates": "not-valid-json{"}

        with pytest.raises(TemplatesError):
            stub._store_lookup_result(row)

        # Nothing was persisted — the title will be redriven via the
        # remote API by ``_flush_lookup_batch``.
        stub.fsout.set_db_key.assert_not_called()

    def test_store_lookup_result_raises_on_unexpected_templates_shape(self):
        """A non-list, non-string templates value also fails closed."""
        stub = self._make_fetcher_stub()
        row = {"name": "File:X.jpg", "templates": {"unexpected": "shape"}}

        with pytest.raises(TemplatesError):
            stub._store_lookup_result(row)
        stub.fsout.set_db_key.assert_not_called()

    # ---- Round 7: stricter element validation ----

    def test_extract_template_names_rejects_dict_without_name(self):
        with pytest.raises(TemplatesError):
            Fetcher._extract_template_names("File:X.jpg", [{"url": "x"}])

    def test_extract_template_names_rejects_dict_with_empty_name(self):
        with pytest.raises(TemplatesError):
            Fetcher._extract_template_names("File:X.jpg", [{"name": ""}])

    def test_extract_template_names_rejects_non_dict_non_str_element(self):
        with pytest.raises(TemplatesError):
            Fetcher._extract_template_names("File:X.jpg", [["nested-list"]])

    def test_extract_template_names_rejects_empty_string_element(self):
        with pytest.raises(TemplatesError):
            Fetcher._extract_template_names("File:X.jpg", [""])

    # ---- Round 7: missing-without-api fails closed ----

    def test_flush_lookup_batch_skips_download_when_no_api_for_missing(self):
        """No API + store miss → drop the deferred download.

        Otherwise we'd ship an image with no license/attribution data
        at all — a fail-open path.
        """
        stub = self._make_fetcher_stub()
        stub.schedule_download_image = MagicMock()
        stub._refcall = MagicMock()

        # No API attached to the pending entry — the store-eligible path
        # in handle_new_basepath fell through to store-only after a failed
        # remote-API discovery.
        stub._lookup_pending = [("File:X.jpg", None, "File:X.jpg")]
        stub._deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        # file store misses this title.
        stub.image_lookup.fetch_batch.return_value = ([], ["File:X.jpg"])

        stub._flush_lookup_batch()

        # No image download was scheduled.
        stub.schedule_download_image.assert_not_called()
        # No fetch_image_page was scheduled either (no api).
        stub._refcall.assert_not_called()
        # And the deferred entry was dropped.
        assert "File:X.jpg" not in stub._deferred_downloads

    def test_flush_lookup_batch_skips_download_when_no_api_for_store_hit(self):
        """No API + store hit → drop the deferred download too.

        We have license-template data from file store, but
        ``handle_new_basepath`` skipped ``get_image_edits`` because
        remote-API discovery failed. Downloading the image would
        produce a rendered book with no contributor attribution, so
        we fail closed even though the license check would have
        passed.
        """
        stub = self._make_fetcher_stub()
        stub.schedule_download_image = MagicMock()

        stub._lookup_pending = [("File:X.jpg", None, "File:X.jpg")]
        stub._deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        # file store has the row with a free license — license check
        # would pass, but we should still refuse to download.
        stub.image_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": [{"name": "Template:Cc-by-sa"}]}],
            [],
        )

        stub._flush_lookup_batch()

        stub.schedule_download_image.assert_not_called()
        assert "File:X.jpg" not in stub._deferred_downloads

    def test_flush_lookup_batch_reroutes_corrupt_row_to_fallback(self, monkeypatch):
        """Corrupt store rows are added to ``missing`` so the remote API runs."""
        stub = self._make_fetcher_stub()
        stub.schedule_download_image = MagicMock()
        stub._refcall = MagicMock()

        api = MagicMock()
        api.api_request_limit = 50
        stub._lookup_pending = [("File:X.jpg", api, "File:X.jpg")]
        stub.image_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": "not-valid-json{"}],
            [],
        )

        stub._flush_lookup_batch()

        # Corrupt row routed to fetch_image_page via the missing-fallback path.
        called_funcs = {call.args[0] for call in stub._refcall.call_args_list}
        assert stub.fetch_image_page in called_funcs

    def test_store_lookup_result_writes_empty_list_as_negative_cache(self):
        """An empty templates list is stored, not skipped.

        Without this, render-time ``get_image_templates_and_args`` would
        fall through to wikitext parsing for an image we deliberately
        decided not to fetch — which is exactly what the file store cache
        is supposed to avoid.
        """
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")

        row = {"name": "File:NoTemplates.jpg", "templates": []}
        stub._store_lookup_result(row)

        stub.fsout.set_db_key.assert_any_call("templates", "File:NoTemplates.jpg", [])

    def test_extract_template_names_strips_template_prefix(self):
        names = Fetcher._extract_template_names(
            "File:X.jpg",
            [
                {"name": "Template:Cc-by-sa", "url": "..."},
                {"name": "Information"},
                "raw-string-name",
            ],
        )
        assert names == ["Cc-by-sa", "Information", "raw-string-name"]

    def test_extract_template_names_handles_none(self):
        assert Fetcher._extract_template_names("File:X.jpg", None) == []

    def test_flush_lookup_batch_schedules_free_downloads(self):
        """_flush_lookup_batch should schedule downloads for free-licensed images."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()

        stub._deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        stub._lookup_pending = [("File:X.jpg", MagicMock(), "File:X.jpg")]

        stub.image_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": ["cc-by-sa"]}],
            [],
        )
        stub._flush_lookup_batch()

        stub.schedule_download_image.assert_called_once_with("https://thumb/X.jpg", "File:X.jpg")

    def test_flush_lookup_batch_skips_nonfree_downloads(self):
        """_flush_lookup_batch should skip downloads for nonfree images."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()

        stub._deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        stub._lookup_pending = [("File:X.jpg", MagicMock(), "File:X.jpg")]

        stub.image_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": ["non-free logo"]}],
            [],
        )
        stub._flush_lookup_batch()

        stub.schedule_download_image.assert_not_called()
        assert "File:X.jpg" not in stub._deferred_downloads

    def test_flush_lookup_batch_fallback_for_missing(self):
        """_flush_lookup_batch should fall back to remote API for missing titles."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()
        stub._refcall = MagicMock()

        mock_api = MagicMock()
        mock_api.api_request_limit = 50
        stub._deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        stub._lookup_pending = [("File:X.jpg", mock_api, "File:X.jpg")]

        stub.image_lookup.fetch_batch.return_value = ([], ["File:X.jpg"])
        stub._flush_lookup_batch()

        # Should call fetch_image_page via _refcall for missing titles
        stub._refcall.assert_called()
        # Should schedule deferred download for fallback title
        stub.schedule_download_image.assert_called_once_with("https://thumb/X.jpg", "File:X.jpg")

    def test_flush_lookup_batch_title_mapping(self):
        """_flush_lookup_batch maps local names back to original titles for deferred downloads."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()

        # Simulate namespace conversion: original "File:X.jpg" → local "Datei:X.jpg"
        stub._deferred_downloads = {"File:X.jpg": "https://thumb/X.jpg"}
        stub._lookup_pending = [("Datei:X.jpg", MagicMock(), "File:X.jpg")]

        stub.image_lookup.fetch_batch.return_value = (
            [{"name": "Datei:X.jpg", "templates": ["cc-by-sa"]}],
            [],
        )
        stub._flush_lookup_batch()

        # Download should be scheduled using original title
        stub.schedule_download_image.assert_called_once_with("https://thumb/X.jpg", "File:X.jpg")

    def test_flush_lookup_batch_deduplicates_titles(self):
        """_flush_lookup_batch should deduplicate titles before querying file store."""
        stub = self._make_fetcher_stub()
        stub.fsout.get_db_key.side_effect = KeyError("not found")
        stub.schedule_download_image = MagicMock()

        mock_api = MagicMock()
        # Same title appears twice
        stub._lookup_pending = [
            ("File:X.jpg", mock_api, "File:X.jpg"),
            ("File:X.jpg", mock_api, "File:X.jpg"),
        ]

        stub.image_lookup.fetch_batch.return_value = (
            [{"name": "File:X.jpg", "templates": ["cc-by-sa"]}],
            [],
        )
        stub._flush_lookup_batch()

        # Should only query once for the deduplicated title
        call_args = stub.image_lookup.fetch_batch.call_args[0][0]
        assert call_args == ["File:X.jpg"]


class TestNuWikiTemplatesDb:
    """Test templates.db shortcircuit in NuWiki."""

    def _make_nuwiki_dir(self, tmp_path, with_templates_db=True, templates_data=None):
        """Create a minimal nuwiki directory for testing."""
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
        path = self._make_nuwiki_dir(
            tmp_path,
            templates_data={"File:Test.jpg": ["cc-by-sa", "information"]},
        )
        adapt = Adapt(path)

        result = adapt.get_image_templates_and_args("File:Test.jpg")
        assert result == {"cc-by-sa", "information"}

    def test_get_image_templates_and_args_falls_back_without_entry(self, tmp_path):
        """Should fall back to wikitext parsing when templates.db has no entry."""
        path = self._make_nuwiki_dir(tmp_path, with_templates_db=True)
        adapt = Adapt(path)

        # No templates.db entry, no description page → should return empty
        result = adapt.get_image_templates_and_args("File:Missing.jpg")
        assert result == []

    def test_get_image_templates_and_args_no_templates_db(self, tmp_path):
        """Should fall back to wikitext parsing when templates.db doesn't exist."""
        path = self._make_nuwiki_dir(tmp_path, with_templates_db=False)
        adapt = Adapt(path)

        result = adapt.get_image_templates_and_args("File:Missing.jpg")
        assert result == []

    def test_get_contributors_falls_back_to_authors_db_for_store_images(self, tmp_path):
        """file store-backed images read attribution from authors.db.

        These images have no description page on disk because the
        file store shortcut skips ``fetch_image_page``. ``get_image_edits``
        still populates ``authors.db`` via the remote contributor lookup;
        this fallback wires the two together so the rendered book isn't
        attribution-empty.
        """
        path = self._make_nuwiki_dir(tmp_path)
        # Seed authors.db as if Fetcher.get_image_edits had run.
        authors_db = SqliteDict(str(tmp_path / "nuwiki" / "authors.db"), autocommit=True)
        authors_db["File:BQOnly.jpg"] = stdlib_json.dumps(["Alice", "Bob"])
        authors_db.close()

        adapt = Adapt(path)
        # No description page exists for this image (store shortcircuit)…
        assert adapt.get_image_description_page("File:BQOnly.jpg") is None
        # …but contributors are read from authors.db rather than [] returned.
        assert adapt.get_contributors("File:BQOnly.jpg") == ["Alice", "Bob"]

    def test_get_contributors_returns_empty_when_no_authors_either(self, tmp_path):
        """Empty list when neither description page nor authors.db has data.

        Belt-and-braces — the fallback returns ``[]`` instead of raising
        for images we genuinely have no attribution for.
        """
        path = self._make_nuwiki_dir(tmp_path)
        adapt = Adapt(path)

        assert adapt.get_contributors("File:Missing.jpg") == []
