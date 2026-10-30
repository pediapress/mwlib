"""Unit tests for mwlib.apps.file_store_builder."""

import fcntl
import gzip
import io
import json
import sqlite3
import tarfile

import pytest

from mwlib.apps import file_store_builder as fsb
from mwlib.network.file_store import FileStore


def ns6_doc(name, revision, width=100):
    return {
        "name": name,
        "identifier": 1,
        "version": {"identifier": revision},
        "image": {"width": width, "height": 50, "content_url": "https://u/x"},
    }


def write_chunk(path, docs, as_tar=True):
    payload = "".join(json.dumps(d) + "\n" for d in docs).encode()
    if not as_tar:
        path.write_bytes(gzip.compress(payload))
        return
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo("part.ndjson")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))


class FakeWme:
    def __init__(self, chunks):
        self.chunks = chunks  # identifier -> (version, docs, as_tar)

    def list_chunks(self):
        return [{"identifier": i, "version": v} for i, (v, _, _) in self.chunks.items()]

    def download_chunk(self, chunk, dest):
        _, docs, as_tar = self.chunks[chunk["identifier"]]
        write_chunk(dest, docs, as_tar)


CONFIG = fsb.BuildConfig(min_rows=1)


def build(live, wme, **kwargs):
    return fsb.build_file_store(
        live_path=live,
        snapshot_id="enwiki_namespace_6",
        list_chunks=wme.list_chunks,
        download_chunk=wme.download_chunk,
        config=kwargs.pop("config", CONFIG),
        **kwargs,
    )


def test_builds_store_readable_by_file_store(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    wme = FakeWme(
        {
            "c0": ("v1", [ns6_doc("File:A.jpg", 1)], True),
            "c1": ("v1", [ns6_doc("File:B.jpg", 1)], False),
        }
    )
    stats = build(live, wme)

    assert stats.rows_in_store == 2  # noqa: PLR2004
    assert stats.chunks_processed == 2  # noqa: PLR2004
    assert set(FileStore(live).lookup(["File:A.jpg", "File:B.jpg"])) == {
        "File:A.jpg",
        "File:B.jpg",
    }
    assert not list(tmp_path.glob("*.new"))
    assert not (tmp_path / "file_pages.sqlite.chunks").exists()


def test_newest_revision_wins_across_chunks(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    wme = FakeWme(
        {
            "c0": ("v1", [ns6_doc("File:A.jpg", 5, width=500)], True),
            "c1": ("v1", [ns6_doc("File:A.jpg", 3, width=300)], True),
        }
    )
    build(live, wme)
    assert FileStore(live).lookup(["File:A.jpg"])["File:A.jpg"]["image_width"] == 500  # noqa: PLR2004


def test_unchanged_snapshot_is_not_rebuilt(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    wme = FakeWme({"c0": ("v1", [ns6_doc("File:A.jpg", 1)], True)})
    build(live, wme)

    def boom(*_):
        raise AssertionError("downloaded an unchanged snapshot")

    wme.download_chunk = boom
    stats = build(live, wme)
    assert stats.unchanged is True
    assert stats.rows_in_store == 1


def test_changed_chunk_version_rebuilds(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    build(live, FakeWme({"c0": ("v1", [ns6_doc("File:A.jpg", 1)], True)}))
    stats = build(live, FakeWme({"c0": ("v2", [ns6_doc("File:B.jpg", 1)], True)}))
    assert stats.unchanged is False
    assert set(FileStore(live).lookup(["File:A.jpg", "File:B.jpg"])) == {"File:B.jpg"}


def test_too_few_rows_leaves_live_store_untouched(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    build(live, FakeWme({"c0": ("v1", [ns6_doc("File:A.jpg", 1)], True)}))
    before = live.read_bytes()

    with pytest.raises(fsb.BuildError, match="minimum"):
        build(
            live,
            FakeWme({"c0": ("v2", [ns6_doc("File:B.jpg", 1)], True)}),
            config=fsb.BuildConfig(min_rows=5),
        )
    assert live.read_bytes() == before
    assert not list(tmp_path.glob("*.new"))


def test_refuses_to_swap_in_a_much_smaller_store(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    docs = [ns6_doc(f"File:{i}.jpg", 1) for i in range(20)]
    build(live, FakeWme({"c0": ("v1", docs, True)}))

    with pytest.raises(fsb.BuildError, match="smaller"):
        build(live, FakeWme({"c0": ("v2", docs[:5], True)}))
    assert fsb.count_rows(live) == 20  # noqa: PLR2004


def test_no_chunks_is_an_error(tmp_path):
    with pytest.raises(fsb.BuildError, match="no chunks"):
        build(tmp_path / "file_pages.sqlite", FakeWme({}))


def test_tar_without_ndjson_is_an_error(tmp_path):
    chunk = tmp_path / "chunk"
    with tarfile.open(chunk, "w:gz") as tar:
        info = tarfile.TarInfo("readme.txt")
        tar.addfile(info, io.BytesIO(b""))
    with pytest.raises(fsb.BuildError, match=r"no \.ndjson"):
        list(fsb.iter_chunk_lines(chunk))


def test_concurrent_build_is_skipped(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    with open(tmp_path / "file_pages.sqlite.build.lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        stats = build(live, FakeWme({"c0": ("v1", [ns6_doc("File:A.jpg", 1)], True)}))
    assert stats is None
    assert not live.exists()


def test_store_is_not_in_wal_mode(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    build(live, FakeWme({"c0": ("v1", [ns6_doc("File:A.jpg", 1)], True)}))
    conn = sqlite3.connect(live)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        conn.close()
    assert not (tmp_path / "file_pages.sqlite-wal").exists()


def test_cli_passes_thresholds_to_the_build(tmp_path, monkeypatch):
    captured = {}

    def fake_build(**kwargs):
        captured.update(kwargs)
        return fsb.BuildStats(rows_in_store=3, unchanged=True)

    monkeypatch.setenv("WME_USERNAME", "u")
    monkeypatch.setenv("WME_PASSWORD", "p")
    monkeypatch.setattr(fsb, "build_file_store", fake_build)

    path = tmp_path / "fp.sqlite"
    assert fsb.main(["--path", str(path), "--min-rows", "10", "--max-shrink", "0.5"]) == 0
    assert captured["config"] == fsb.BuildConfig(min_rows=10, max_shrink=0.5)
    assert captured["live_path"] == path


def test_hostile_chunk_identifier_cannot_escape_the_work_dir(tmp_path):
    live = tmp_path / "file_pages.sqlite"
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    wme = FakeWme({"../victim.txt": ("v1", [ns6_doc("File:A.jpg", 1)], True)})
    seen = []
    original = wme.download_chunk

    def spy(chunk, dest):
        seen.append(dest)
        original(chunk, dest)

    wme.download_chunk = spy
    build(live, wme)
    assert victim.read_text() == "keep"
    assert seen[0].parent == tmp_path / "file_pages.sqlite.chunks"
