"""Unit tests for the WME snapshot ingestion script.

These tests cover the pure-functional parts (per-namespace row parsers,
namespace dispatch, CLI argument handling) and the table-prep / disk-usage
behaviour that matters for NS0's larger volume.

They never touch BigQuery, the WME API, or the network — load-job and
streaming-insert paths use a mocked BigQuery client.
"""

from __future__ import annotations

import io
import json
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mwlib.apps import fetch_wikimedia_snapshot as snap

# ---------------------------------------------------------------------------
# NS6 row parser
# ---------------------------------------------------------------------------


class TestParseNs6Row:
    def test_extracts_image_metadata(self):
        line = json.dumps(
            {
                "name": "File:Example.jpg",
                "identifier": 42,
                "url": "https://en.wikipedia.org/wiki/File:Example.jpg",
                "date_modified": "2025-01-01T00:00:00Z",
                "license": [{"name": "CC-BY-SA-4.0"}],
                "templates": [{"name": "Template:Information"}],
                "categories": [{"name": "Category:Photos"}],
                "abstract": "Sample image",
                "image": {
                    "content_url": "https://upload.wikimedia.org/Example.jpg",
                    "width": 1200,
                    "height": 800,
                },
            }
        )

        row = snap.parse_ns6_row(line)

        assert row["name"] == "File:Example.jpg"
        assert row["identifier"] == 42
        assert row["image_width"] == 1200
        assert row["image_height"] == 800
        assert row["image_content_url"] == "https://upload.wikimedia.org/Example.jpg"
        assert json.loads(row["license"]) == [{"name": "CC-BY-SA-4.0"}]
        assert json.loads(row["templates"]) == [{"name": "Template:Information"}]
        assert json.loads(row["categories"]) == [{"name": "Category:Photos"}]

    def test_handles_missing_image_block(self):
        # Non-image file pages (e.g. MP3) have no image dict — width/height
        # must come back unset rather than crashing.
        line = json.dumps({"name": "File:Audio.mp3", "identifier": 1})
        row = snap.parse_ns6_row(line)
        assert row["name"] == "File:Audio.mp3"
        assert "image_width" not in row
        assert "image_height" not in row

    def test_skips_missing_name(self):
        line = json.dumps({"identifier": 1})
        assert snap.parse_ns6_row(line) is None

    def test_skips_malformed_json(self):
        assert snap.parse_ns6_row("not json") is None


# ---------------------------------------------------------------------------
# NS0 row parser
# ---------------------------------------------------------------------------


class TestExtractVersionIdentifier:
    """Edge cases for the staging-only ``version_identifier`` extractor.

    The helper is now load-bearing: a wrong return value either drops
    the dedup signal (NULL) or, worse, ranks a malformed row ahead of
    a real one. Cover the cases that aren't exercised by the parser
    tests' happy path.
    """

    @pytest.mark.parametrize(
        ("doc", "expected"),
        [
            # Happy path — typed int.
            ({"version": {"identifier": 12345}}, 12345),
            # Missing version field altogether.
            ({}, None),
            # ``version`` present but not a dict.
            ({"version": None}, None),
            ({"version": "v1"}, None),
            ({"version": [1, 2, 3]}, None),
            # ``version`` is a dict but missing ``identifier``.
            ({"version": {"comment": "edit"}}, None),
            # Wrong type for ``identifier``.
            ({"version": {"identifier": "12345"}}, None),
            ({"version": {"identifier": 12345.0}}, None),
            ({"version": {"identifier": None}}, None),
            # ``bool`` is a subclass of int — must NOT slip through as 0/1.
            ({"version": {"identifier": True}}, None),
            ({"version": {"identifier": False}}, None),
        ],
    )
    def test_returns_int_or_none(self, doc, expected):
        assert snap._extract_version_identifier(doc) == expected


class TestParseNs0Row:
    def test_keeps_only_lean_schema_fields(self):
        # WME NS0 records carry many fields we explicitly do not want to
        # store. The parser must keep just (name, identifier, date_modified,
        # article_body_html) and drop everything else, regardless of how big
        # the input record is.
        line = json.dumps(
            {
                "name": "Mainz",
                "identifier": 99,
                "url": "https://en.wikipedia.org/wiki/Mainz",
                "date_modified": "2025-01-01T00:00:00Z",
                "abstract": "Mainz is a city in Germany.",
                "version": {"identifier": 12345, "comment": "edit"},
                "in_language": {"identifier": "en"},
                "main_entity": {"identifier": "Q1726"},
                "license": [{"name": "CC-BY-SA-4.0"}],
                "templates": [{"name": "Template:Infobox"}],
                "categories": [{"name": "Category:Cities"}],
                "redirects": [{"name": "Mayence"}],
                "article_body": {
                    "html": "<p>Mainz is a city.</p>",
                    "wikitext": "Mainz is a city.",
                },
            }
        )

        row = snap.parse_ns0_row(line)

        # ``version_identifier`` is the staging-only dedup field — picked
        # up from the source's nested ``version.identifier``. The full
        # ``version`` object itself must still be dropped (storage cost
        # reasons, see ``forbidden`` below).
        assert row == {
            "name": "Mainz",
            "identifier": 99,
            "date_modified": "2025-01-01T00:00:00Z",
            "article_body_html": "<p>Mainz is a city.</p>",
            "version_identifier": 12345,
        }
        # Critical for storage cost — none of these may leak into the row
        for forbidden in (
            "abstract",
            "version",
            "in_language",
            "main_entity",
            "license",
            "templates",
            "categories",
            "redirects",
            "url",
            "wikitext",
        ):
            assert forbidden not in row

    def test_skips_row_without_html(self):
        # Without HTML there is nothing the page-count estimator can do —
        # storing the row would just bloat the table with empty placeholders.
        line = json.dumps({"name": "Empty", "identifier": 1, "article_body": {"wikitext": "x"}})
        assert snap.parse_ns0_row(line) is None

    def test_skips_row_with_empty_html(self):
        line = json.dumps({"name": "Empty", "article_body": {"html": ""}})
        assert snap.parse_ns0_row(line) is None

    def test_skips_row_without_article_body(self):
        line = json.dumps({"name": "NoBody", "identifier": 7})
        assert snap.parse_ns0_row(line) is None

    def test_skips_missing_name(self):
        line = json.dumps({"identifier": 1, "article_body": {"html": "<p>x</p>"}})
        assert snap.parse_ns0_row(line) is None

    def test_skips_malformed_json(self):
        assert snap.parse_ns0_row("not json") is None


# ---------------------------------------------------------------------------
# Namespace dispatch
# ---------------------------------------------------------------------------


class TestNamespaceConfig:
    def test_ns6_targets_file_pages_and_recreates_table(self):
        ns = snap.NAMESPACES[6]
        assert ns.table_id == "file_pages"
        assert ns.snapshot_id == "enwiki_namespace_6"
        assert ns.parser is snap.parse_ns6_row
        assert ns.script_manages_table is True

    def test_ns0_targets_article_pages_and_defers_to_pulumi(self):
        ns = snap.NAMESPACES[0]
        assert ns.table_id == "article_pages"
        assert ns.snapshot_id == "enwiki_namespace_0"
        assert ns.parser is snap.parse_ns0_row
        # Pulumi owns the table layout; the script must not drop it.
        assert ns.script_manages_table is False

    def test_ns0_schema_is_minimal(self):
        ns = snap.NAMESPACES[0]
        field_names = {f["name"] for f in ns.schema}
        assert field_names == {
            "name",
            "identifier",
            "date_modified",
            "article_body_html",
        }
        # name is the lookup key — must be REQUIRED so BigQuery rejects bad
        # rows up front rather than silently storing them.
        assert next(f for f in ns.schema if f["name"] == "name")["mode"] == "REQUIRED"


# ---------------------------------------------------------------------------
# Table preparation strategy
# ---------------------------------------------------------------------------


class TestPrepareTable:
    def test_ns6_recreates_the_table(self):
        client = MagicMock()
        ns = snap.NAMESPACES[6]
        snap._prepare_table(client, "p.d.file_pages", ns)
        client.delete_table.assert_called_once_with("p.d.file_pages", not_found_ok=True)
        client.create_table.assert_called_once()
        _, kwargs = client.create_table.call_args
        assert "exists_ok" not in kwargs

    def test_ns0_does_not_drop_or_create_the_table(self):
        """NS0 is externally managed (Pulumi). Script must NOT touch it.

        Bootstrapping the table here would silently drop clustering /
        deletion-protection settings that Pulumi owns; the next Pulumi
        run would then see drift. Read-only verification only.
        """
        client = MagicMock()
        ns = snap.NAMESPACES[0]
        snap._prepare_table(client, "p.d.article_pages", ns)
        client.delete_table.assert_not_called()
        client.create_table.assert_not_called()
        # ``get_table`` is the existence probe — must be called.
        client.get_table.assert_called_once_with("p.d.article_pages")

    def test_ns0_raises_when_table_missing(self):
        """Missing externally-managed table fails loudly.

        Operator gets a clear pointer to provision the table via Pulumi
        instead of the script silently bootstrapping a stripped-down
        version without clustering / deletion-protection.
        """
        from google.api_core.exceptions import NotFound

        client = MagicMock()
        client.get_table.side_effect = NotFound("Table p.d.article_pages")
        ns = snap.NAMESPACES[0]

        with pytest.raises(RuntimeError, match="not found"):
            snap._prepare_table(client, "p.d.article_pages", ns)
        client.create_table.assert_not_called()

    def test_ns0_raises_with_iam_pointer_on_403(self):
        """A 403 ``Forbidden`` reads as a permission gap, not a missing table.

        BigQuery returns ``Permission bigquery.tables.get denied (or it may
        not exist)`` ambiguously for both 403 and 404 at the message level.
        We distinguish at the exception class level so the operator gets
        steered to ``roles/bigquery.dataEditor`` instead of being told to
        re-provision via Pulumi (which would fail with a "table already
        exists" error and leave them more confused).
        """
        from google.api_core.exceptions import Forbidden

        client = MagicMock()
        client.get_table.side_effect = Forbidden("Permission denied")
        ns = snap.NAMESPACES[0]

        with pytest.raises(RuntimeError, match="dataEditor"):
            snap._prepare_table(client, "p.d.article_pages", ns)
        client.create_table.assert_not_called()


# ---------------------------------------------------------------------------
# CLI argument handling
# ---------------------------------------------------------------------------


class TestArgParser:
    def test_default_namespace_is_six(self):
        args = snap._build_arg_parser().parse_args([])
        assert args.namespace == 6

    def test_namespace_can_select_zero(self):
        args = snap._build_arg_parser().parse_args(["--namespace", "0"])
        assert args.namespace == 0

    def test_invalid_namespace_rejected(self):
        with pytest.raises(SystemExit):
            snap._build_arg_parser().parse_args(["--namespace", "1"])

    def test_snapshot_id_defaults_per_namespace(self):
        args0 = snap._build_arg_parser().parse_args(["--namespace", "0"])
        ns0 = snap.NAMESPACES[args0.namespace]
        assert (args0.snapshot_id or ns0.snapshot_id) == "enwiki_namespace_0"

        args6 = snap._build_arg_parser().parse_args([])
        ns6 = snap.NAMESPACES[args6.namespace]
        assert (args6.snapshot_id or ns6.snapshot_id) == "enwiki_namespace_6"


# ---------------------------------------------------------------------------
# Tarball iteration: just-in-time extract + delete
# ---------------------------------------------------------------------------


def _make_tarball(tmp_path, files: dict[str, str]):
    """Write a .tar.gz containing the given filename → content map."""
    tarball = tmp_path / "snapshot.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return tarball


class TestIterExtractNdjson:
    """The iterator must cap peak disk usage at one extracted NDJSON.

    Concretely: extract one NDJSON, yield it, then delete it before extracting
    the next. The output is "tarball + at most one extracted NDJSON" on disk
    at any moment.
    """

    def test_yields_each_ndjson_in_order(self, tmp_path):
        tarball = _make_tarball(
            tmp_path,
            {
                "chunk_0.ndjson": '{"a": 1}\n',
                "chunk_1.ndjson": '{"a": 2}\n',
                "chunk_2.ndjson": '{"a": 3}\n',
            },
        )

        seen = []
        for path in snap.iter_extract_ndjson(tarball):
            seen.append((path.name, path.read_text()))

        assert [n for n, _ in seen] == [
            "chunk_0.ndjson",
            "chunk_1.ndjson",
            "chunk_2.ndjson",
        ]

    def test_deletes_extracted_file_after_each_iteration(self, tmp_path):
        # Only one extracted NDJSON is on disk at a time. Capture each
        # extracted path, advance the iterator, and assert the previous
        # extracted file no longer exists.
        tarball = _make_tarball(
            tmp_path,
            {
                "a.ndjson": "x\n",
                "b.ndjson": "y\n",
                "c.ndjson": "z\n",
            },
        )

        it = snap.iter_extract_ndjson(tarball)
        first = next(it)
        assert first.exists()

        second = next(it)
        assert second.exists()
        assert not first.exists(), (
            "first NDJSON should have been deleted before the second was yielded"
        )

        third = next(it)
        assert third.exists()
        assert not second.exists()

        with pytest.raises(StopIteration):
            next(it)
        assert not third.exists(), "last NDJSON should be deleted when iteration completes"

    def test_skips_non_ndjson_members(self, tmp_path):
        tarball = _make_tarball(
            tmp_path,
            {
                "README.txt": "ignore me",
                "data.ndjson": '{"a": 1}\n',
            },
        )
        names = [p.name for p in snap.iter_extract_ndjson(tarball)]
        assert names == ["data.ndjson"]

    def test_rejects_path_traversal(self, tmp_path):
        tarball = _make_tarball(tmp_path, {"../escape.ndjson": "evil\n"})
        it = snap.iter_extract_ndjson(tarball)
        with pytest.raises(ValueError, match="Suspicious tar member path"):
            next(it)

    def test_rejects_absolute_path(self, tmp_path):
        tarball = _make_tarball(tmp_path, {"/etc/passwd.ndjson": "evil\n"})
        it = snap.iter_extract_ndjson(tarball)
        with pytest.raises(ValueError, match="Suspicious tar member path"):
            next(it)

    def test_rejects_symlink_member(self, tmp_path):
        """A crafted symlink ending in .ndjson must not be extracted.

        Without the regular-file check, ``tar.extract`` would happily
        create the symlink and a follow-up extracted file written to
        that name would land outside the target directory.
        """
        tarball = tmp_path / "snap.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            for name, content in {"good.ndjson": '{"x": 1}\n'}.items():
                data = content.encode("utf-8")
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            # …and append a symlink alongside the legit file.
            link = tarfile.TarInfo(name="evil.ndjson")
            link.type = tarfile.SYMTYPE
            link.linkname = "/tmp/evil-target"
            tar.addfile(link)

        it = snap.iter_extract_ndjson(tarball)
        with pytest.raises(ValueError, match="non-regular tar member"):
            next(it)

    def test_rejects_hardlink_member(self, tmp_path):
        tarball = tmp_path / "snap.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            for name, content in {"good.ndjson": '{"x": 1}\n'}.items():
                data = content.encode("utf-8")
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            link = tarfile.TarInfo(name="evil.ndjson")
            link.type = tarfile.LNKTYPE
            link.linkname = "../something"
            tar.addfile(link)

        it = snap.iter_extract_ndjson(tarball)
        with pytest.raises(ValueError, match="non-regular tar member"):
            next(it)

    def test_rejects_tarball_with_no_ndjson(self, tmp_path):
        tarball = _make_tarball(tmp_path, {"only_a_txt.txt": "no ndjson here"})
        it = snap.iter_extract_ndjson(tarball)
        with pytest.raises(ValueError, match="No .ndjson files found"):
            next(it)

    def test_extracts_into_private_tempdir_not_parent(self, tmp_path):
        """Tar members extract under a private temp dir, never the parent.

        Without an isolated extract dir, ``existing.ndjson`` in the
        tarball would land at ``tmp_path/existing.ndjson`` (which we
        seeded ourselves) and our cleanup ``unlink`` would then delete
        the operator's pre-existing file.
        """
        sibling = tmp_path / "existing.ndjson"
        sibling.write_text("DO NOT TOUCH\n")

        tarball = _make_tarball(tmp_path, {"existing.ndjson": '{"x": 1}\n'})

        # Drain the iterator — the .ndjson member is yielded, then the
        # iterator's finally block cleans it up.
        list(snap.iter_extract_ndjson(tarball))

        # The seeded sibling is untouched.
        assert sibling.exists()
        assert sibling.read_text() == "DO NOT TOUCH\n"

        # And the temp dir is gone after iteration finishes.
        leftover_dirs = [
            p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("wme-ndjson-")
        ]
        assert leftover_dirs == []


# ---------------------------------------------------------------------------
# load_tarball_to_bigquery: end-to-end load-job dispatch
# ---------------------------------------------------------------------------


class TestLoadTarballLoadJob:
    """Full path: tarball → iter-extract → per-file load job.

    Verifies the disposition sequence (truncate then append) and the
    just-in-time disk cleanup.
    """

    def _setup_client(self, monkeypatch):
        from google.cloud import bigquery  # noqa: F401  (used by SUT)

        client = MagicMock()
        load_job = MagicMock()
        load_job.errors = None
        load_job.output_rows = 1
        load_job.job_id = "job-1"
        client.load_table_from_file.return_value = load_job
        monkeypatch.setattr(snap, "_make_bq_client", lambda *a, **kw: client)
        return client

    def test_first_file_truncates_subsequent_files_append(self, monkeypatch, tmp_path):
        from google.cloud import bigquery

        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]

        tarball = _make_tarball(
            tmp_path,
            {
                "a.ndjson": json.dumps(
                    {
                        "name": "Mainz",
                        "identifier": 1,
                        "article_body": {"html": "<p>x</p>"},
                    }
                )
                + "\n",
                "b.ndjson": json.dumps(
                    {
                        "name": "Berlin",
                        "identifier": 2,
                        "article_body": {"html": "<p>y</p>"},
                    }
                )
                + "\n",
                "c.ndjson": json.dumps(
                    {
                        "name": "Hamburg",
                        "identifier": 3,
                        "article_body": {"html": "<p>z</p>"},
                    }
                )
                + "\n",
            },
        )

        snap.load_tarball_to_bigquery(
            tarball,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
        )

        assert client.load_table_from_file.call_count == 3
        dispositions = [
            call.kwargs["job_config"].write_disposition
            for call in client.load_table_from_file.call_args_list
        ]
        assert dispositions == [
            bigquery.WriteDisposition.WRITE_TRUNCATE,
            bigquery.WriteDisposition.WRITE_APPEND,
            bigquery.WriteDisposition.WRITE_APPEND,
        ]

    def test_rejects_malicious_project_identifier(self, monkeypatch, tmp_path):
        """Bad project identifiers raise before any SQL is built.

        ``project`` / ``dataset`` get interpolated into the raw SQL
        ``TRUNCATE TABLE`` statement on the streaming-insert path —
        a backtick or whitespace there would close ``table_ref`` early.
        """
        self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        tarball = _make_tarball(
            tmp_path,
            {
                "a.ndjson": json.dumps({"name": "Mainz", "article_body": {"html": "<p>x</p>"}})
                + "\n"
            },
        )

        with pytest.raises(ValueError, match="Invalid BigQuery project"):
            snap.load_tarball_to_bigquery(
                tarball,
                project="evil`; DROP TABLE x; --",
                dataset="ds",
                ns=ns,
                credentials_path=None,
            )

    def test_rejects_malicious_dataset_identifier(self, monkeypatch, tmp_path):
        self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        tarball = _make_tarball(
            tmp_path,
            {
                "a.ndjson": json.dumps({"name": "Mainz", "article_body": {"html": "<p>x</p>"}})
                + "\n"
            },
        )

        with pytest.raises(ValueError, match="Invalid BigQuery dataset"):
            snap.load_tarball_to_bigquery(
                tarball,
                project="proj",
                dataset="ds with space",
                ns=ns,
                credentials_path=None,
            )

    def test_extracted_files_are_gone_after_load(self, monkeypatch, tmp_path):
        # The whole point of the iter-extract design: at the end of the run
        # there must be no extracted NDJSON files lingering on disk.
        self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]

        tarball = _make_tarball(
            tmp_path,
            {
                "a.ndjson": json.dumps({"name": "X", "article_body": {"html": "<p>x</p>"}}) + "\n",
                "b.ndjson": json.dumps({"name": "Y", "article_body": {"html": "<p>y</p>"}}) + "\n",
            },
        )

        snap.load_tarball_to_bigquery(
            tarball,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
        )

        # Tarball stays (caller decides whether to keep it); extracted
        # NDJSON files should all be gone.
        assert tarball.exists()
        leftover = list(tmp_path.glob("*.ndjson"))
        assert leftover == [], f"Expected no leftover NDJSON, got {leftover}"


# ---------------------------------------------------------------------------
# load_tarball_to_bigquery: streaming-insert dispatch
# ---------------------------------------------------------------------------


class TestLoadTarballStreaming:
    def test_truncates_externally_managed_table_before_streaming(self, monkeypatch, tmp_path):
        # Streaming inserts append; without a TRUNCATE we'd silently double
        # the table on each run for Pulumi-managed tables.
        client = MagicMock()
        client.insert_rows_json.return_value = []
        monkeypatch.setattr(snap, "_make_bq_client", lambda *a, **kw: client)

        ns = snap.NAMESPACES[0]
        tarball = _make_tarball(
            tmp_path,
            {
                "a.ndjson": json.dumps(
                    {
                        "name": "Mainz",
                        "identifier": 1,
                        "article_body": {"html": "<p>x</p>"},
                    }
                )
                + "\n"
            },
        )

        snap.load_tarball_to_bigquery(
            tarball,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            use_streaming_insert=True,
        )

        truncate_calls = [
            call for call in client.query.call_args_list if "TRUNCATE TABLE" in call.args[0]
        ]
        assert len(truncate_calls) == 1

    def test_does_not_truncate_when_script_recreates_table(self, monkeypatch, tmp_path):
        # NS6 path drops + recreates the table, so an explicit TRUNCATE
        # would be redundant work.
        client = MagicMock()
        client.insert_rows_json.return_value = []
        monkeypatch.setattr(snap, "_make_bq_client", lambda *a, **kw: client)

        ns = snap.NAMESPACES[6]
        tarball = _make_tarball(
            tmp_path,
            {"a.ndjson": json.dumps({"name": "File:x.jpg", "identifier": 1}) + "\n"},
        )

        snap.load_tarball_to_bigquery(
            tarball,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            use_streaming_insert=True,
        )

        truncate_calls = [
            call for call in client.query.call_args_list if "TRUNCATE TABLE" in call.args[0]
        ]
        assert truncate_calls == []


# ---------------------------------------------------------------------------
# Chunked ingest: WME /chunks API + per-chunk download/load/checkpoint
# ---------------------------------------------------------------------------


import gzip  # noqa: E402


def _make_chunk_tarball(path, ndjson_name, ndjson_content):
    """Write a tar.gz containing a single NDJSON, mirroring a WME chunk."""
    with tarfile.open(path, "w:gz") as tar:
        data = ndjson_content.encode("utf-8")
        info = tarfile.TarInfo(name=ndjson_name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))


def _make_gz_ndjson(path, ndjson_content):
    """Write a plain gzipped NDJSON (the alternative chunk shape)."""
    with gzip.open(path, "wb") as f:
        f.write(ndjson_content.encode("utf-8"))


class TestListChunks:
    """``list_chunks`` is the dispatch decision: ≥1 chunk → chunked path."""

    def test_returns_list_on_success(self, monkeypatch):
        resp = MagicMock(status_code=200)
        resp.json.return_value = [
            {"identifier": "c0", "version": "v0"},
            {"identifier": "c1", "version": "v1"},
        ]
        monkeypatch.setattr(snap.requests, "get", lambda *a, **kw: resp)

        chunks = snap.list_chunks("token", "snap")
        assert [c["identifier"] for c in chunks] == ["c0", "c1"]

    def test_empty_list_on_404(self, monkeypatch):
        # Snapshots without chunked support return 404 — caller falls back
        # to the legacy single-tarball path.
        resp = MagicMock(status_code=404)
        monkeypatch.setattr(snap.requests, "get", lambda *a, **kw: resp)

        assert snap.list_chunks("token", "snap") == []

    def test_non_list_payload_treated_as_empty(self, monkeypatch):
        # Defensive: if WME ever returns ``{}`` or an error envelope, we
        # don't want to crash — fall back to the legacy path instead.
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"error": "not chunked"}
        monkeypatch.setattr(snap.requests, "get", lambda *a, **kw: resp)

        assert snap.list_chunks("token", "snap") == []


class TestDownloadChunk:
    """Per-chunk download with whole-file retry."""

    def _make_resp(self, body: bytes, etag: str = "abc123"):
        resp = MagicMock()
        resp.headers = {"content-length": str(len(body)), "etag": f'"{etag}"'}
        resp.iter_content.return_value = [body]
        resp.__enter__ = lambda self: resp
        resp.__exit__ = lambda *a: None
        resp.raise_for_status = MagicMock()
        return resp

    def test_writes_file_and_returns_etag(self, monkeypatch, tmp_path):
        resp = self._make_resp(b"hello chunk")
        monkeypatch.setattr(snap.requests, "get", lambda *a, **kw: resp)

        out = tmp_path / "c0"
        etag = snap.download_chunk("token", "snap", "c0", out, retries=1)
        assert etag == "abc123"
        assert out.read_bytes() == b"hello chunk"

    def test_retries_on_short_read(self, monkeypatch, tmp_path):
        # First attempt advertises 100 bytes but yields 5 — that's a
        # partial transfer (network drop); we should retry rather than
        # silently load a truncated chunk.
        bad_resp = MagicMock()
        bad_resp.headers = {"content-length": "100", "etag": '"x"'}
        bad_resp.iter_content.return_value = [b"short"]
        bad_resp.__enter__ = lambda self: bad_resp
        bad_resp.__exit__ = lambda *a: None
        bad_resp.raise_for_status = MagicMock()

        good_resp = self._make_resp(b"complete payload", etag="finalEtag")

        responses = iter([bad_resp, good_resp])
        monkeypatch.setattr(snap.requests, "get", lambda *a, **kw: next(responses))
        monkeypatch.setattr(snap.time, "sleep", lambda s: None)  # don't actually wait

        out = tmp_path / "c0"
        etag = snap.download_chunk("token", "snap", "c0", out, retries=2)
        assert etag == "finalEtag"
        assert out.read_bytes() == b"complete payload"

    def test_raises_after_exhausted_retries(self, monkeypatch, tmp_path):
        bad_resp = MagicMock()
        bad_resp.headers = {"content-length": "10", "etag": '"x"'}
        bad_resp.iter_content.return_value = [b"x"]
        bad_resp.__enter__ = lambda self: bad_resp
        bad_resp.__exit__ = lambda *a: None
        bad_resp.raise_for_status = MagicMock()
        monkeypatch.setattr(snap.requests, "get", lambda *a, **kw: bad_resp)
        monkeypatch.setattr(snap.time, "sleep", lambda s: None)

        with pytest.raises(OSError, match="short read"):
            snap.download_chunk("token", "snap", "c0", tmp_path / "c0", retries=2)
        # Failed downloads are unlinked so a subsequent run doesn't try to
        # use the partial file.
        assert not (tmp_path / "c0").exists()


class TestChunkLoadState:
    def test_round_trip(self, tmp_path):
        state = snap.ChunkLoadState.new("snap_x")
        state.chunks_loaded["c0"] = "v0"
        state.chunks_loaded["c1"] = "v1"
        path = tmp_path / "state.json"
        state.save(path)

        roundtrip = snap.ChunkLoadState.load(path)
        assert roundtrip.run_id == state.run_id
        assert roundtrip.snapshot == "snap_x"
        assert roundtrip.chunks_loaded == {"c0": "v0", "c1": "v1"}

    def test_save_is_atomic(self, tmp_path):
        # The temp file must not survive a successful save — otherwise
        # accumulating ``.tmp`` files across runs is a leak.
        state = snap.ChunkLoadState.new("snap")
        path = tmp_path / "state.json"
        state.save(path)

        assert path.exists()
        leftover = list(tmp_path.glob("*.tmp"))
        assert leftover == []


class TestIterChunkNdjson:
    def test_handles_targz_chunk(self, tmp_path):
        chunk = tmp_path / "c0"
        _make_chunk_tarball(chunk, "a.ndjson", '{"name": "Mainz"}\n')
        seen = []
        for path in snap._iter_chunk_ndjson(chunk):
            seen.append(path.read_text())
        assert seen == ['{"name": "Mainz"}\n']

    def test_handles_gzipped_ndjson_chunk(self, tmp_path):
        chunk = tmp_path / "c0"
        _make_gz_ndjson(chunk, '{"name": "Berlin"}\n')
        seen = []
        for path in snap._iter_chunk_ndjson(chunk):
            seen.append(path.read_text())
        assert seen == ['{"name": "Berlin"}\n']


class TestLoadChunkedToBigquery:
    """The chunked orchestrator: dispatch, dispositions, resume, drift."""

    def _setup_client(self, monkeypatch):
        client = MagicMock()
        load_job = MagicMock()
        load_job.errors = None
        load_job.output_rows = 1
        load_job.job_id = "job-1"
        client.load_table_from_file.return_value = load_job
        # The MERGE swap at the end of a chunked run goes through
        # ``client.query()``. Mock it the same way as load jobs so tests
        # don't trip the "MERGE job completed with errors" path.
        merge_job = MagicMock()
        merge_job.errors = None
        merge_job.num_dml_affected_rows = 1
        client.query.return_value = merge_job
        # The swap pre-flight (``_require_dedup_column``) probes staging
        # schema via ``client.get_table().schema``. Mock it to include
        # the dedup column so the swap proceeds; an upgrade-resume test
        # constructs its own client with the column missing.
        staging_table = MagicMock()
        staging_table.schema = [MagicMock(name=f["name"]) for f in snap._make_staging_schema([])]
        # ``MagicMock(name=...)`` doesn't actually set ``.name`` (it
        # names the mock instead); set it explicitly.
        for f, sf in zip(staging_table.schema, snap._make_staging_schema([]), strict=True):
            f.name = sf["name"]
        client.get_table.return_value = staging_table
        monkeypatch.setattr(snap, "_make_bq_client", lambda *a, **kw: client)
        return client

    def _stub_download_chunk(self, monkeypatch, tmp_path, content_for):
        """Fake ``download_chunk``.

        Writes a tar.gz with the given NDJSON content into the requested
        output_path. Returns the input map.
        """

        def fake_download(token, snapshot_id, chunk_id, output_path, retries=3):
            _make_chunk_tarball(output_path, f"{chunk_id}.ndjson", content_for[chunk_id])
            return f"etag-{chunk_id}"

        monkeypatch.setattr(snap, "download_chunk", fake_download)

    def test_first_chunk_truncates_rest_append(self, monkeypatch, tmp_path):
        from google.cloud import bigquery

        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        chunks = [
            {"identifier": "c0", "version": "etag-c0"},
            {"identifier": "c1", "version": "etag-c1"},
            {"identifier": "c2", "version": "etag-c2"},
        ]
        rows = {
            cid: json.dumps({"name": cid, "identifier": i, "article_body": {"html": "<p>x</p>"}})
            + "\n"
            for i, cid in enumerate([c["identifier"] for c in chunks])
        }
        self._stub_download_chunk(monkeypatch, tmp_path, rows)

        snap.load_chunked_to_bigquery(
            token="token",
            chunks=chunks,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            state_path=tmp_path / "state.json",
            fresh=False,
        )

        assert client.load_table_from_file.call_count == 3
        dispositions = [
            call.kwargs["job_config"].write_disposition
            for call in client.load_table_from_file.call_args_list
        ]
        assert dispositions == [
            bigquery.WriteDisposition.WRITE_TRUNCATE,
            bigquery.WriteDisposition.WRITE_APPEND,
            bigquery.WriteDisposition.WRITE_APPEND,
        ]

    def test_resume_skips_already_loaded_and_appends_rest(self, monkeypatch, tmp_path):
        # Pre-populate state as if a previous run loaded c0 and c1; this
        # invocation should fetch only c2 and use WRITE_APPEND (NEVER
        # WRITE_TRUNCATE on a resume — that would erase the previous
        # run's work).
        from google.cloud import bigquery

        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        chunks = [
            {"identifier": "c0", "version": "etag-c0"},
            {"identifier": "c1", "version": "etag-c1"},
            {"identifier": "c2", "version": "etag-c2"},
        ]
        rows = {
            "c2": json.dumps({"name": "c2", "article_body": {"html": "<p>x</p>"}}) + "\n",
        }
        self._stub_download_chunk(monkeypatch, tmp_path, rows)

        prev_state = snap.ChunkLoadState.new(ns.snapshot_id)
        prev_state.chunks_loaded = {"c0": "etag-c0", "c1": "etag-c1"}
        state_path = tmp_path / "state.json"
        prev_state.save(state_path)

        snap.load_chunked_to_bigquery(
            token="token",
            chunks=chunks,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            state_path=state_path,
            fresh=False,
        )

        # Only c2 was loaded.
        assert client.load_table_from_file.call_count == 1
        # And it was an APPEND — resumes never truncate.
        disp = client.load_table_from_file.call_args.kwargs["job_config"].write_disposition
        assert disp == bigquery.WriteDisposition.WRITE_APPEND

    def test_version_drift_raises(self, monkeypatch, tmp_path):
        # If WME re-issues a snapshot, every chunk gets a new version
        # hash. We must refuse rather than mix old and new data.
        self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]

        prev_state = snap.ChunkLoadState.new(ns.snapshot_id)
        prev_state.chunks_loaded = {"c0": "OLD-version-hash"}
        state_path = tmp_path / "state.json"
        prev_state.save(state_path)

        chunks_now = [{"identifier": "c0", "version": "NEW-version-hash"}]
        with pytest.raises(RuntimeError, match="re-issued"):
            snap.load_chunked_to_bigquery(
                token="token",
                chunks=chunks_now,
                project="proj",
                dataset="ds",
                ns=ns,
                credentials_path=None,
                state_path=state_path,
                fresh=False,
            )

    def test_fresh_flag_clears_state_and_truncates(self, monkeypatch, tmp_path):
        from google.cloud import bigquery

        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]

        # Pre-existing state pointing at a previous run.
        prev_state = snap.ChunkLoadState.new(ns.snapshot_id)
        prev_state.chunks_loaded = {"c0": "old", "c1": "old"}
        state_path = tmp_path / "state.json"
        prev_state.save(state_path)

        chunks = [{"identifier": "c0", "version": "new"}]
        rows = {
            "c0": json.dumps({"name": "c0", "article_body": {"html": "<p>x</p>"}}) + "\n",
        }
        self._stub_download_chunk(monkeypatch, tmp_path, rows)

        snap.load_chunked_to_bigquery(
            token="token",
            chunks=chunks,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            state_path=state_path,
            fresh=True,
        )

        # --fresh ignores the saved state, so c0 loads with WRITE_TRUNCATE
        # even though the saved state listed it as previously-loaded.
        disp = client.load_table_from_file.call_args.kwargs["job_config"].write_disposition
        assert disp == bigquery.WriteDisposition.WRITE_TRUNCATE

    def test_state_cleared_on_full_success(self, monkeypatch, tmp_path):
        # Once every chunk has loaded, the state file should be deleted
        # so the next invocation starts fresh by default.
        self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        chunks = [{"identifier": "c0", "version": "v0"}]
        rows = {
            "c0": json.dumps({"name": "c0", "article_body": {"html": "<p>x</p>"}}) + "\n",
        }
        self._stub_download_chunk(monkeypatch, tmp_path, rows)

        state_path = tmp_path / "state.json"
        snap.load_chunked_to_bigquery(
            token="token",
            chunks=chunks,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            state_path=state_path,
            fresh=False,
        )
        assert not state_path.exists()

    def test_state_persisted_after_each_chunk(self, monkeypatch, tmp_path):
        # The crash-safety property: after a chunk's BQ load returns, the
        # state file must already record it before the next chunk starts
        # downloading. We verify by patching ``download_chunk`` to read
        # the saved state at call time — the *N+1*-th call must see
        # ``c_N`` already in chunks_loaded.
        self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        chunks = [
            {"identifier": "c0", "version": "v0"},
            {"identifier": "c1", "version": "v1"},
            {"identifier": "c2", "version": "v2"},
        ]
        rows = {
            cid: json.dumps({"name": cid, "article_body": {"html": "<p>x</p>"}}) + "\n"
            for cid in [c["identifier"] for c in chunks]
        }
        state_path = tmp_path / "state.json"
        seen_state_at_call: list[dict[str, str]] = []

        def fake_download(token, snapshot_id, chunk_id, output_path, retries=3):
            if state_path.exists():
                seen_state_at_call.append(dict(snap.ChunkLoadState.load(state_path).chunks_loaded))
            else:
                seen_state_at_call.append({})
            _make_chunk_tarball(output_path, f"{chunk_id}.ndjson", rows[chunk_id])
            return f"etag-{chunk_id}"

        monkeypatch.setattr(snap, "download_chunk", fake_download)

        snap.load_chunked_to_bigquery(
            token="token",
            chunks=chunks,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            state_path=state_path,
            fresh=False,
        )

        # When c1 starts downloading, c0 must already be checkpointed.
        # When c2 starts, c0 and c1 must both be checkpointed.
        assert seen_state_at_call[0] == {}
        assert "c0" in seen_state_at_call[1]
        assert "c0" in seen_state_at_call[2]
        assert "c1" in seen_state_at_call[2]

    def test_loads_go_to_staging_table_not_destination(self, monkeypatch, tmp_path):
        # The whole point of staging+swap is that the destination table
        # is never written to during chunk loads — readers see the
        # previous snapshot throughout the refresh window. Verify by
        # checking every load_table_from_file call's table_ref argument.
        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        chunks = [{"identifier": "c0", "version": "v0"}]
        rows = {
            "c0": json.dumps({"name": "c0", "article_body": {"html": "<p>x</p>"}}) + "\n",
        }
        self._stub_download_chunk(monkeypatch, tmp_path, rows)

        snap.load_chunked_to_bigquery(
            token="token",
            chunks=chunks,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            state_path=tmp_path / "state.json",
            fresh=False,
        )

        # Every load_table_from_file call's second positional arg is the
        # table_ref. They should *all* point at the staging table, never
        # at the destination ``article_pages``.
        for call in client.load_table_from_file.call_args_list:
            table_ref = call.args[1] if len(call.args) > 1 else call.kwargs.get("destination")
            assert table_ref == "proj.ds.article_pages_staging", (
                f"chunk load went to {table_ref!r}, expected staging"
            )

    def test_merge_swap_runs_after_all_chunks_loaded(self, monkeypatch, tmp_path):
        # The MERGE swap should fire exactly once at the end, with both
        # the source (staging) and target (destination) tables in the
        # SQL. ``client.query()`` is the entry point for the MERGE.
        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        chunks = [
            {"identifier": "c0", "version": "v0"},
            {"identifier": "c1", "version": "v1"},
        ]
        rows = {
            cid: json.dumps({"name": cid, "article_body": {"html": "<p>x</p>"}}) + "\n"
            for cid in [c["identifier"] for c in chunks]
        }
        self._stub_download_chunk(monkeypatch, tmp_path, rows)

        snap.load_chunked_to_bigquery(
            token="token",
            chunks=chunks,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            state_path=tmp_path / "state.json",
            fresh=False,
        )

        # Exactly one query (the MERGE) should have run. Streaming-insert
        # path would TRUNCATE via query() but we're not on that path.
        assert client.query.call_count == 1
        merge_sql = client.query.call_args.args[0]
        assert "MERGE" in merge_sql
        assert "proj.ds.article_pages" in merge_sql  # target
        assert "proj.ds.article_pages_staging" in merge_sql  # source
        assert "WHEN NOT MATCHED BY SOURCE THEN DELETE" in merge_sql
        # Snapshots may legitimately carry duplicate articles; staging
        # gets deduped by ``version_identifier`` inside the USING clause
        # so the MERGE doesn't trip "must match at most one source row".
        assert "ROW_NUMBER" in merge_sql
        assert "PARTITION BY name" in merge_sql
        assert "version_identifier DESC NULLS LAST" in merge_sql

    def test_swap_skipped_when_already_done_on_resume(self, monkeypatch, tmp_path):
        # State.swap_done == True means a previous run completed the
        # MERGE but died before clearing the state file. Re-running
        # must not redo the MERGE (cheap but unnecessary, and would log
        # confusing "0 rows affected" output).
        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        chunks = [{"identifier": "c0", "version": "v0"}]

        prev_state = snap.ChunkLoadState.new(ns.snapshot_id)
        prev_state.chunks_loaded = {"c0": "v0"}
        prev_state.swap_done = True
        state_path = tmp_path / "state.json"
        prev_state.save(state_path)

        snap.load_chunked_to_bigquery(
            token="token",
            chunks=chunks,
            project="proj",
            dataset="ds",
            ns=ns,
            credentials_path=None,
            state_path=state_path,
            fresh=False,
        )

        client.query.assert_not_called()
        # State file cleared because run is fully complete.
        assert not state_path.exists()


class TestLoadOneFileBatching:
    """A multi-GB NDJSON should split into several smaller load jobs.

    The source files in EN NS0 are ~2 GB each — submitting that as a
    single load job blocks the operator on a silent multi-minute
    ``job.result()`` poll. ``_load_one_file`` now slices the input at
    ``batch_max_bytes`` so the operator sees one log line per batch.
    """

    def _setup_client(self, monkeypatch):
        client = MagicMock()

        # Each fake load job claims to have loaded the rows it was given.
        # The test asserts on call_count and per-call dispositions.
        def _make_job(*a, **kw):
            job = MagicMock()
            job.errors = None
            # We can't know rows-per-call from inside _make_job without
            # opening the temp file, so just return 1 — totals aren't
            # what's being tested here.
            job.output_rows = 1
            job.job_id = "job"
            return job

        client.load_table_from_file.side_effect = _make_job
        monkeypatch.setattr(snap, "_make_bq_client", lambda *a, **kw: client)
        return client

    def _ndjson_with_rows(self, tmp_path, n: int):
        """Write an NS0-shaped NDJSON with ``n`` rows.

        Each row's HTML body is padded so a small ``batch_max_bytes``
        reliably splits into multiple batches.
        """
        path = tmp_path / "input.ndjson"
        # ~10 KB per row of HTML so 100 rows ≈ 1 MB of source.
        padding = "x" * 10_000
        with open(path, "w") as f:
            for i in range(n):
                f.write(
                    json.dumps(
                        {
                            "name": f"Article-{i}",
                            "identifier": i,
                            "article_body": {"html": f"<p>{padding}</p>"},
                        }
                    )
                    + "\n"
                )
        return path

    def test_large_input_splits_into_multiple_load_jobs(self, monkeypatch, tmp_path):
        from google.cloud import bigquery

        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        path = self._ndjson_with_rows(tmp_path, 500)  # ~5 MB transformed

        snap._load_one_file(
            client=client,
            ndjson_path=path,
            file_idx=1,
            table_ref="proj.ds.t",
            schema=snap._make_bq_schema(ns.schema),
            parser=ns.parser,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            batch_max_bytes=1 * 1024 * 1024,  # 1 MB cap → expect ≥3 batches
        )

        # ≥3 load jobs (5 MB / 1 MB), first one TRUNCATE, rest APPEND.
        # The first batch carries the operator's disposition; subsequent
        # batches must NEVER WRITE_TRUNCATE — that would erase rows the
        # earlier batch in the same source just loaded.
        assert client.load_table_from_file.call_count >= 3
        dispositions = [
            call.kwargs["job_config"].write_disposition
            for call in client.load_table_from_file.call_args_list
        ]
        assert dispositions[0] == bigquery.WriteDisposition.WRITE_TRUNCATE
        assert all(d == bigquery.WriteDisposition.WRITE_APPEND for d in dispositions[1:]), (
            dispositions
        )

    def test_small_input_stays_single_batch(self, monkeypatch, tmp_path):
        # Sanity: an input that fits inside batch_max_bytes still produces
        # exactly one load job — the existing single-NDJSON test cases
        # rely on this.
        from google.cloud import bigquery

        client = self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        path = self._ndjson_with_rows(tmp_path, 5)  # tiny

        snap._load_one_file(
            client=client,
            ndjson_path=path,
            file_idx=1,
            table_ref="proj.ds.t",
            schema=snap._make_bq_schema(ns.schema),
            parser=ns.parser,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )

        assert client.load_table_from_file.call_count == 1
        disp = client.load_table_from_file.call_args.kwargs["job_config"].write_disposition
        assert disp == bigquery.WriteDisposition.WRITE_TRUNCATE

    def test_batch_files_unlinked_after_load(self, monkeypatch, tmp_path):
        # Each transformed batch lands in tempfile.NamedTemporaryFile;
        # the function must unlink them after each batch's load returns,
        # not at the end. Otherwise peak disk grows linearly with input.
        self._setup_client(monkeypatch)
        ns = snap.NAMESPACES[0]
        path = self._ndjson_with_rows(tmp_path, 200)

        before = set(Path(tempfile.gettempdir()).glob("*.ndjson"))
        snap._load_one_file(
            client=MagicMock(
                load_table_from_file=MagicMock(
                    return_value=MagicMock(errors=None, output_rows=1, job_id="j")
                )
            ),
            ndjson_path=path,
            file_idx=1,
            table_ref="proj.ds.t",
            schema=None,
            parser=ns.parser,
            write_disposition="WRITE_TRUNCATE",
            batch_max_bytes=512 * 1024,  # tiny cap → many batches
        )
        after = set(Path(tempfile.gettempdir()).glob("*.ndjson"))
        # The set may have unrelated entries from other tests, but no NEW
        # .ndjson should have been left behind by this run.
        leaked = after - before
        assert leaked == set(), f"leaked batch files: {leaked}"


class TestSwapStagingIntoTarget:
    """The MERGE swap must survive duplicate articles in staging.

    Wikimedia Enterprise snapshots can ship a small number (<1%) of
    duplicate articles. Until the dedup-in-USING change, the MERGE
    raised ``UPDATE/MERGE must match at most one source row for each
    target row`` and aborted the entire ingest at the very last step.
    """

    def _make_client(self, staging_has_dedup_column: bool = True):
        client = MagicMock()
        merge_job = MagicMock()
        merge_job.errors = None
        merge_job.num_dml_affected_rows = 7
        client.query.return_value = merge_job
        # ``_require_dedup_column`` probes staging schema before the
        # MERGE; default to "modern" staging (with version_identifier).
        # Tests that simulate a 0.18.7 in-flight resume flip the flag.
        staging_table = MagicMock()
        cols = [f["name"] for f in snap.NS0_SCHEMA]
        if staging_has_dedup_column:
            cols.append(snap._VERSION_IDENT_FIELD["name"])
        fields = []
        for col in cols:
            fld = MagicMock()
            fld.name = col
            fields.append(fld)
        staging_table.schema = fields
        client.get_table.return_value = staging_table
        return client

    def test_dedupes_staging_by_version_identifier(self):
        client = self._make_client()
        snap._swap_staging_into_target(
            client,
            target_ref="p.d.article_pages",
            staging_ref="p.d.article_pages_staging",
            schema=snap.NS0_SCHEMA,
        )

        sql = client.query.call_args.args[0]
        # Pick latest revision per primary key inside the USING clause.
        assert "ROW_NUMBER()" in sql
        assert "PARTITION BY name" in sql
        # Primary sort: highest version wins.
        assert "version_identifier DESC NULLS LAST" in sql
        # Stable tiebreakers: when version_identifier is NULL or tied
        # across duplicate rows, fall back to date_modified then
        # identifier so re-running the swap is deterministic.
        assert "date_modified DESC NULLS LAST" in sql
        assert "identifier DESC NULLS LAST" in sql
        # ``version_identifier`` must NOT appear in the destination
        # column list — it's staging-only.
        insert_section = sql[sql.index("INSERT (") :]
        assert "version_identifier" not in insert_section

    def test_omits_tiebreaker_when_destination_lacks_the_column(self):
        # A future namespace whose destination schema doesn't carry
        # ``date_modified`` (or ``identifier``) must not have those
        # column names interpolated into the ORDER BY — that would
        # silently produce SQL that BigQuery rejects.
        client = self._make_client()
        minimal_schema = [{"name": "name", "type": "STRING", "mode": "REQUIRED"}]
        # Mock staging schema for a minimal-namespace case.
        staging_table = MagicMock()
        fields = []
        for col in ("name", snap._VERSION_IDENT_FIELD["name"]):
            fld = MagicMock()
            fld.name = col
            fields.append(fld)
        staging_table.schema = fields
        client.get_table.return_value = staging_table

        snap._swap_staging_into_target(
            client,
            target_ref="p.d.minimal",
            staging_ref="p.d.minimal_staging",
            schema=minimal_schema,
        )
        sql = client.query.call_args.args[0]
        assert "version_identifier DESC NULLS LAST" in sql
        assert "date_modified" not in sql
        # ``identifier`` is the page id column, not the dedup column.
        # The minimal schema has no ``identifier`` column, so the
        # ORDER BY should only contain the dedup column. Comma-split
        # to avoid a false positive on the ``identifier`` substring of
        # ``version_identifier``.
        order_section = sql[sql.index("ORDER BY") : sql.index(") = 1")]
        order_terms = [t.strip() for t in order_section.removeprefix("ORDER BY").split(",")]
        assert order_terms == ["version_identifier DESC NULLS LAST"]

    def test_targets_the_destination_via_merge(self):
        # Sanity: still a MERGE with the right target / source / DELETE
        # semantics. Guards against an accidental rewrite to a
        # non-atomic TRUNCATE+INSERT, which would expose readers to an
        # empty article_pages mid-swap.
        client = self._make_client()
        snap._swap_staging_into_target(
            client,
            target_ref="p.d.article_pages",
            staging_ref="p.d.article_pages_staging",
            schema=snap.NS0_SCHEMA,
        )

        sql = client.query.call_args.args[0]
        assert "MERGE `p.d.article_pages` T" in sql
        assert "`p.d.article_pages_staging`" in sql
        assert "WHEN NOT MATCHED BY SOURCE THEN DELETE" in sql

    def test_rejects_unknown_primary_key(self):
        client = self._make_client()
        with pytest.raises(ValueError, match="primary_key"):
            snap._swap_staging_into_target(
                client,
                target_ref="p.d.article_pages",
                staging_ref="p.d.article_pages_staging",
                schema=snap.NS0_SCHEMA,
                primary_key="nope",
            )

    def test_aborts_with_directive_when_staging_predates_dedup_column(self):
        # A 0.18.7 in-flight resume has a staging table without
        # ``version_identifier``. The QUALIFY/ORDER BY would otherwise
        # error with a vague "Unrecognized name" — we want a clear
        # message pointing at ``--fresh``.
        client = self._make_client(staging_has_dedup_column=False)
        with pytest.raises(RuntimeError, match="--fresh"):
            snap._swap_staging_into_target(
                client,
                target_ref="p.d.article_pages",
                staging_ref="p.d.article_pages_staging",
                schema=snap.NS0_SCHEMA,
            )
        # Pre-flight must short-circuit before the MERGE is submitted.
        client.query.assert_not_called()


class TestStagingSchema:
    def test_staging_schema_appends_version_identifier(self):
        # Destination schema (NS0) must stay minimal — Pulumi owns it
        # and adding columns there is a separate, deliberate operation.
        # The dedup column lives only on staging.
        dest_cols = {f["name"] for f in snap.NS0_SCHEMA}
        assert "version_identifier" not in dest_cols

        staging_cols = {f["name"] for f in snap._make_staging_schema(snap.NS0_SCHEMA)}
        assert staging_cols == dest_cols | {"version_identifier"}

        staging_schema = snap._make_staging_schema(snap.NS0_SCHEMA)
        ver_field = next(f for f in staging_schema if f["name"] == "version_identifier")
        assert ver_field["type"] == "INTEGER"
        assert ver_field["mode"] == "NULLABLE"


class TestArgParserChunkedFlags:
    def test_fresh_flag(self):
        args = snap._build_arg_parser().parse_args(["--fresh"])
        assert args.fresh is True

    def test_no_chunked_flag(self):
        args = snap._build_arg_parser().parse_args(["--no-chunked"])
        assert args.no_chunked is True

    def test_state_file_flag(self):
        args = snap._build_arg_parser().parse_args(["--state-file", "/tmp/my-state.json"])
        assert args.state_file == "/tmp/my-state.json"

    def test_default_state_file_is_per_snapshot(self):
        # Two namespaces resolve to two distinct default state-file paths
        # so concurrent NS6 + NS0 runs don't clobber each other.
        p6 = snap._default_state_path("enwiki_namespace_6")
        p0 = snap._default_state_path("enwiki_namespace_0")
        assert p6 != p0
        assert "enwiki_namespace_6" in str(p6)
        assert "enwiki_namespace_0" in str(p0)
