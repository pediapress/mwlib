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

        assert row == {
            "name": "Mainz",
            "identifier": 99,
            "date_modified": "2025-01-01T00:00:00Z",
            "article_body_html": "<p>Mainz is a city.</p>",
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
        client = MagicMock()
        client.get_table.side_effect = Exception("404 Not found: Table p.d.article_pages")
        ns = snap.NAMESPACES[0]

        with pytest.raises(RuntimeError, match="externally managed"):
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
