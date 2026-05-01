"""Targeted tests for ``fetch_wikimedia_snapshot``.

Focused on the security-sensitive tar extraction path. The full ingestion
path (download, BigQuery load) is exercised by ops runs rather than unit
tests because it requires WME credentials and a real BigQuery target.
"""

from __future__ import annotations

import io
import tarfile

import pytest

from mwlib.apps.fetch_wikimedia_snapshot import extract_ndjson_from_tarball


def _add_regular_file(tar, name, content):
    info = tarfile.TarInfo(name=name)
    data = content.encode("utf-8")
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _add_symlink(tar, name, target):
    info = tarfile.TarInfo(name=name)
    info.type = tarfile.SYMTYPE
    info.linkname = target
    tar.addfile(info)


def _add_hardlink(tar, name, target):
    info = tarfile.TarInfo(name=name)
    info.type = tarfile.LNKTYPE
    info.linkname = target
    tar.addfile(info)


class TestExtractNdjsonFromTarball:
    def test_extracts_regular_ndjson_files(self, tmp_path):
        tarball = tmp_path / "snap.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            _add_regular_file(tar, "a.ndjson", '{"x": 1}\n')
            _add_regular_file(tar, "b.ndjson", '{"x": 2}\n')

        paths = extract_ndjson_from_tarball(tarball)

        assert sorted(p.name for p in paths) == ["a.ndjson", "b.ndjson"]
        assert all(p.read_text().strip() for p in paths)

    def test_rejects_path_traversal(self, tmp_path):
        tarball = tmp_path / "snap.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            _add_regular_file(tar, "../escape.ndjson", "x\n")

        with pytest.raises(ValueError, match="Suspicious tar member path"):
            extract_ndjson_from_tarball(tarball)

    def test_rejects_absolute_path(self, tmp_path):
        tarball = tmp_path / "snap.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            _add_regular_file(tar, "/etc/passwd.ndjson", "x\n")

        with pytest.raises(ValueError, match="Suspicious tar member path"):
            extract_ndjson_from_tarball(tarball)

    def test_rejects_symlink_member(self, tmp_path):
        """A crafted tarball must not be able to write *through* a symlink.

        Symlinks ending in ``.ndjson`` would otherwise be passed to
        ``tar.extract``, which happily creates the symlink and then a
        subsequent extracted file written to that name follows it out
        of the target directory.
        """
        tarball = tmp_path / "snap.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            _add_symlink(tar, "evil.ndjson", "/tmp/evil-target")

        with pytest.raises(ValueError, match="non-regular tar member"):
            extract_ndjson_from_tarball(tarball)

    def test_rejects_hardlink_member(self, tmp_path):
        tarball = tmp_path / "snap.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            _add_hardlink(tar, "evil.ndjson", "../something")

        with pytest.raises(ValueError, match="non-regular tar member"):
            extract_ndjson_from_tarball(tarball)

    def test_no_ndjson_raises(self, tmp_path):
        tarball = tmp_path / "snap.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            _add_regular_file(tar, "README.md", "x\n")

        with pytest.raises(ValueError, match="No .ndjson files"):
            extract_ndjson_from_tarball(tarball)
