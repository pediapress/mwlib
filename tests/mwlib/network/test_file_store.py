"""Unit tests for mwlib.network.file_store and the NS6 parser."""

import json
import sqlite3

import pytest

from mwlib.network.file_store import (
    COLUMNS,
    SCHEMA_SQL,
    SCHEMA_VERSION,
    FileStore,
    FileStoreImageLookup,
)
from mwlib.network.wme import parse_ns6_line


def make_store(path, rows, version=SCHEMA_VERSION):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (version.encode(),))
    for row in rows:
        full = dict.fromkeys(COLUMNS) | row
        conn.execute(
            f"INSERT INTO files ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
            [full[c] for c in COLUMNS],
        )
    conn.commit()
    conn.close()


class FakeConf:
    def __init__(self, **values):
        self._data = {("filestore", k): v for k, v in values.items()}

    def get(self, section, option, fallback=None, type_=str):
        return self._data.get((section, option), fallback)


@pytest.fixture
def store_path(tmp_path):
    path = tmp_path / "file_pages.sqlite"
    make_store(
        path,
        [
            {"name": "File:A b.jpg", "image_width": 800, "templates": "[]"},
            {"name": "File:C.png", "image_height": 600},
        ],
    )
    return path


class TestFileStore:
    def test_lookup_returns_rows_keyed_by_requested_title(self, store_path):
        found = FileStore(store_path).lookup(["File:A_b.jpg", "File:C.png", "File:Nope.png"])
        assert set(found) == {"File:A_b.jpg", "File:C.png"}
        # name is the title as requested so callers can match rows to requests
        assert found["File:A_b.jpg"]["name"] == "File:A_b.jpg"
        assert found["File:A_b.jpg"]["image_width"] == 800  # noqa: PLR2004

    def test_lookup_empty_names(self, tmp_path):
        assert FileStore(tmp_path / "missing.sqlite").lookup([]) == {}

    def test_lookup_missing_file_is_unavailable(self, tmp_path):
        store = FileStore(tmp_path / "missing.sqlite")
        assert store.lookup(["File:A.jpg"]) is None
        assert store.is_available() is False

    def test_lookup_unsupported_schema_is_unavailable(self, tmp_path):
        path = tmp_path / "old.sqlite"
        make_store(path, [], version="0")
        assert FileStore(path).lookup(["File:A.jpg"]) is None

    def test_lookup_large_batch_crosses_batch_boundary(self, tmp_path):
        path = tmp_path / "big.sqlite"
        names = [f"File:{i}.jpg" for i in range(1200)]
        make_store(path, [{"name": n} for n in names])
        assert len(FileStore(path).lookup(names)) == 1200  # noqa: PLR2004

    def test_follows_atomic_swap(self, tmp_path):
        path = tmp_path / "file_pages.sqlite"
        make_store(path, [{"name": "File:Old.jpg"}])
        store = FileStore(path)
        assert store.lookup(["File:Old.jpg"])

        new = tmp_path / "file_pages.sqlite.new"
        make_store(new, [{"name": "File:New.jpg"}])
        new.replace(path)

        assert store.lookup(["File:Old.jpg"]) == {}
        assert "File:New.jpg" in store.lookup(["File:New.jpg"])


class TestFileStoreImageLookup:
    def test_unconfigured_is_unavailable_and_misses_everything(self):
        lookup = FileStoreImageLookup(conf=FakeConf())
        assert lookup.is_available is False
        assert lookup.fetch_batch(["File:A.jpg"]) == ([], ["File:A.jpg"])

    def test_available_with_readable_store(self, store_path):
        assert FileStoreImageLookup(conf=FakeConf(path=str(store_path))).is_available is True

    def test_missing_file_is_unavailable(self, tmp_path):
        conf = FakeConf(path=str(tmp_path / "missing.sqlite"))
        lookup = FileStoreImageLookup(conf=conf)
        assert lookup.is_available is False
        assert lookup.fetch_batch(["File:A.jpg"]) == ([], ["File:A.jpg"])

    def test_availability_is_decided_once(self, store_path):
        lookup = FileStoreImageLookup(conf=FakeConf(path=str(store_path)))
        store_path.unlink()
        assert lookup.is_available is True  # latched at creation
        # ...and a vanished store degrades to a miss, not an error
        assert lookup.fetch_batch(["File:A.jpg"]) == ([], ["File:A.jpg"])

    def test_store_appearing_later_does_not_flip_availability(self, tmp_path):
        path = tmp_path / "late.sqlite"
        lookup = FileStoreImageLookup(conf=FakeConf(path=str(path)))
        assert lookup.is_available is False
        make_store(path, [{"name": "File:A.jpg"}])
        assert lookup.is_available is False

    def test_fetch_batch_splits_found_and_missing(self, store_path):
        lookup = FileStoreImageLookup(conf=FakeConf(path=str(store_path)))
        rows, missing = lookup.fetch_batch(["File:A_b.jpg", "File:Nope.png", "File:C.png"])
        assert {r["name"] for r in rows} == {"File:A_b.jpg", "File:C.png"}
        assert missing == ["File:Nope.png"]

    def test_fetch_batch_empty(self, store_path):
        lookup = FileStoreImageLookup(conf=FakeConf(path=str(store_path)))
        assert lookup.fetch_batch([]) == ([], [])

    def test_handles_domain_exact_host_only(self):
        lookup = FileStoreImageLookup(conf=FakeConf(domains="EN.Wikipedia.org, de.wikipedia.org"))
        assert lookup.handles_domain("https://en.wikipedia.org:443/wiki/File:A.jpg")
        assert lookup.handles_domain("https://de.wikipedia.org/wiki/File:A.jpg")
        assert lookup.handles_domain("en.wikipedia.org")
        assert not lookup.handles_domain("https://en.wikipedia.org.example.com/x")
        assert not lookup.handles_domain("https://commons.wikimedia.org/wiki/File:A.jpg")


class TestParseNs6Line:
    def test_parses_row(self):
        line = json.dumps(
            {
                "name": "File:A.jpg",
                "identifier": 7,
                "date_modified": "2026-01-01",
                "version": {"identifier": 42},
                "url": "https://en.wikipedia.org/wiki/File:A.jpg",
                "image": {"content_url": "https://u/A.jpg", "width": 800, "height": 600},
                "templates": [{"name": "Template:Cc-by-sa"}],
                "license": [],
            }
        )
        row = parse_ns6_line(line)
        assert row["name"] == "File:A.jpg"
        assert row["version_identifier"] == 42  # noqa: PLR2004
        assert row["image_width"] == 800  # noqa: PLR2004
        assert json.loads(row["templates"]) == [{"name": "Template:Cc-by-sa"}]
        assert row["license"] is None  # empty list stored as NULL

    def test_name_is_stored_with_spaces(self):
        assert parse_ns6_line(json.dumps({"name": "File:A_b.jpg"}))["name"] == "File:A b.jpg"

    @pytest.mark.parametrize("line", ["not json", "[]", json.dumps({"identifier": 1})])
    def test_rejects_bad_lines(self, line):
        assert parse_ns6_line(line) is None

    def test_boolean_revision_is_not_a_revision(self):
        row = parse_ns6_line(json.dumps({"name": "File:A.jpg", "version": {"identifier": True}}))
        assert row["version_identifier"] is None
