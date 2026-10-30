"""Build the local file-page SQLite store (see ``mwlib.network.file_store``) from WME NS6.

NS6 is small (~1M rows, ~10 chunks, ~2 GB download), so the build is
single-pass: no resume state and no compression. What protects production is
a flock against concurrent builds, a chunk-version manifest so an unchanged
snapshot is not re-downloaded, validation (quick_check, minimum rows, maximum
shrink) and an atomic rename, so readers never see a partial file and a failed
run leaves the previous store untouched.

CLI (``mw-file-store``)::

    WME_USERNAME=... WME_PASSWORD=... mw-file-store --path /data/file_pages.sqlite

Without ``--path`` the ``MWLIB_FILESTORE_PATH`` environment variable is used.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import gzip
import json
import logging
import os
import shutil
import sqlite3
import sys
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mwlib.network.file_store import COLUMNS, SCHEMA_SQL, SCHEMA_VERSION
from mwlib.network.wme import NS6_SNAPSHOT_ID, WmeClient, parse_ns6_line

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

logger = logging.getLogger(__name__)

TABLE = "files"
_BATCH = 2000

# Newest revision wins; a row without a revision id loses to one with it.
_UPSERT_SQL = f"""
INSERT INTO files ({", ".join(COLUMNS)})
VALUES ({", ".join("?" * len(COLUMNS))})
ON CONFLICT(name) DO UPDATE SET
    {", ".join(f"{c} = excluded.{c}" for c in COLUMNS[1:])}
WHERE COALESCE(excluded.revision_id, -1) > COALESCE(files.revision_id, -1)
"""


class BuildError(RuntimeError):
    pass


@dataclass
class BuildConfig:
    # Refuse to swap in a file with fewer rows than this, or that has lost
    # more than ``max_shrink`` of the live file's rows. NS6 has ~1.0M rows.
    min_rows: int = 500_000
    max_shrink: float = 0.10


@dataclass
class BuildStats:
    chunks_processed: int = 0
    rows_loaded: int = 0
    rows_skipped: int = 0
    rows_in_store: int = 0
    # True when the live store already matches WME's current chunk versions,
    # so nothing was downloaded or rebuilt.
    unchanged: bool = False


def iter_chunk_lines(chunk_path: Path) -> Iterator[bytes]:
    """Yield NDJSON lines from a chunk without extracting it to disk.

    A WME chunk is either a tar.gz wrapping ``.ndjson`` members or a plain
    gzipped NDJSON file; both shapes occur depending on snapshot generation.
    """
    try:
        tar = tarfile.open(chunk_path, "r:gz")  # noqa: SIM115 (closed by ``with tar`` below)
    except tarfile.ReadError:
        with gzip.open(chunk_path, "rb") as f:
            for line in f:
                if line.strip():
                    yield line
        return

    found = False
    with tar:
        # Sequential iteration; getmembers() would decompress the whole
        # archive once just to list it.
        for member in tar:
            if not (member.isfile() and member.name.endswith(".ndjson")):
                continue
            found = True
            src = tar.extractfile(member)
            if src is None:
                raise BuildError(f"chunk {chunk_path.name}: cannot read {member.name}")
            with src:
                for line in src:
                    if line.strip():
                        yield line
    if not found:
        raise BuildError(f"chunk {chunk_path.name}: tar contains no .ndjson members")


def _manifest(snapshot_id: str, chunks: list[dict]) -> dict:
    return {"snapshot": snapshot_id, "chunks": {c["identifier"]: c["version"] for c in chunks}}


def _text(value) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _open_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)


def read_manifest(path: Path) -> dict | None:
    """The snapshot id and chunk versions a store was built from.

    ``None`` if the file is missing or unreadable, or predates manifests
    (which makes the next run rebuild once and record one).
    """
    try:
        conn = _open_ro(path)
    except sqlite3.Error:
        return None
    try:
        rows = dict(
            conn.execute("SELECT key, value FROM meta WHERE key IN ('snapshot', 'chunk_versions')")
        )
        return {
            "snapshot": _text(rows["snapshot"]),
            "chunks": json.loads(_text(rows["chunk_versions"])),
        }
    except (sqlite3.Error, KeyError, ValueError):
        return None
    finally:
        conn.close()


def count_rows(path: Path) -> int:
    conn = _open_ro(path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    finally:
        conn.close()


def swap_into_place(new_path: Path, live_path: Path, config: BuildConfig) -> int:
    """Validate ``new_path`` and atomically rename it over ``live_path``.

    Returns the new row count. Raises ``BuildError`` (leaving both files
    alone) if the file is unhealthy or implausibly small.
    """
    conn = _open_ro(new_path)
    try:
        check = conn.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        conn.close()
    if check != "ok":
        raise BuildError(f"quick_check failed for {new_path}: {check}")

    new_rows = count_rows(new_path)
    if new_rows < config.min_rows:
        raise BuildError(f"new store has only {new_rows} rows (minimum {config.min_rows})")
    if live_path.exists():
        try:
            old_rows = count_rows(live_path)
        except sqlite3.Error:
            logger.exception("live store %s is unreadable; replacing it", live_path)
            old_rows = 0
        if new_rows < old_rows * (1 - config.max_shrink):
            raise BuildError(
                f"new store has {new_rows} rows, live has {old_rows} "
                f"(more than {config.max_shrink:.0%} smaller); refusing to swap"
            )

    # The build ran with synchronous=OFF, so flush the file itself before the
    # rename makes it live; otherwise a crash can leave a corrupt live store.
    fd = os.open(new_path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(new_path, live_path)
    dir_fd = os.open(live_path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return new_rows


def _row_tuple(row: dict) -> tuple:
    # ``parse_ns6_line`` calls the revision id ``version_identifier``.
    return tuple(row["version_identifier" if c == "revision_id" else c] for c in COLUMNS)


def _remove_build_files(new_path: Path) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        with contextlib.suppress(FileNotFoundError):
            Path(str(new_path) + suffix).unlink()


def build_file_store(
    *,
    live_path: Path,
    snapshot_id: str,
    list_chunks: Callable[[], list[dict]],
    download_chunk: Callable[[dict, Path], None],
    parser: Callable[[str], dict | None] = parse_ns6_line,
    config: BuildConfig | None = None,
    fresh: bool = False,
) -> BuildStats | None:
    """Build the store and swap it into ``live_path``.

    Returns ``None`` if another build holds the lock. ``fresh=True`` rebuilds
    even when the snapshot is unchanged.
    """
    config = config or BuildConfig()
    live_path = Path(live_path)
    live_path.parent.mkdir(parents=True, exist_ok=True)
    new_path = live_path.with_name(live_path.name + ".new")
    work_dir = live_path.with_name(live_path.name + ".chunks")

    with open(live_path.with_name(live_path.name + ".build.lock"), "w") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            logger.warning("another file-store build holds the lock; skipping")
            return None
        try:
            return _build(
                live_path,
                new_path,
                work_dir,
                snapshot_id,
                list_chunks,
                download_chunk,
                parser,
                config,
                fresh,
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)
            _remove_build_files(new_path)


def _build(
    live_path, new_path, work_dir, snapshot_id, list_chunks, download_chunk, parser, config, fresh
):
    chunks = list_chunks()
    if not chunks:
        raise BuildError(f"snapshot {snapshot_id} lists no chunks")
    manifest = _manifest(snapshot_id, chunks)

    if not fresh and read_manifest(live_path) == manifest:
        rows = count_rows(live_path)
        logger.info(
            "file store is up to date (%d rows, %d chunks); nothing to do", rows, len(chunks)
        )
        return BuildStats(rows_in_store=rows, unchanged=True)

    _remove_build_files(new_path)
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True)

    stats = BuildStats()
    conn = sqlite3.connect(new_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=OFF")  # throwaway until the rename
        conn.executescript(SCHEMA_SQL)
        conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (SCHEMA_VERSION.encode(),))
        for number, chunk in enumerate(chunks, 1):
            # Local name: the identifier comes from the remote API and is not a safe path.
            path = work_dir / f"chunk_{number:04d}"
            download_chunk(chunk, path)
            batch: list[tuple] = []
            for line in iter_chunk_lines(path):
                row = parser(line.decode("utf-8", errors="replace"))
                if row is None:
                    stats.rows_skipped += 1
                    continue
                batch.append(_row_tuple(row))
                if len(batch) >= _BATCH:
                    conn.executemany(_UPSERT_SQL, batch)
                    stats.rows_loaded += len(batch)
                    batch = []
            if batch:
                conn.executemany(_UPSERT_SQL, batch)
                stats.rows_loaded += len(batch)
            conn.commit()
            path.unlink(missing_ok=True)
            stats.chunks_processed += 1
            logger.info(
                "[%d/%d] file store chunk %s done", number, len(chunks), chunk["identifier"]
            )

        conn.execute("INSERT OR REPLACE INTO meta VALUES ('snapshot', ?)", (snapshot_id.encode(),))
        conn.execute(
            "INSERT OR REPLACE INTO meta VALUES ('chunk_versions', ?)",
            (json.dumps(manifest["chunks"], sort_keys=True).encode(),),
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        mode = conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        if mode != "delete":
            raise BuildError(f"could not leave WAL mode (journal_mode={mode})")
    finally:
        conn.close()

    stats.rows_in_store = swap_into_place(new_path, live_path, config)
    logger.info(
        "file store built: %d rows (%d loaded, %d skipped)",
        stats.rows_in_store,
        stats.rows_loaded,
        stats.rows_skipped,
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the local NS6 file-page SQLite store from the WME snapshot."
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("MWLIB_FILESTORE_PATH", ""),
        help="Store file to build (default: MWLIB_FILESTORE_PATH env)",
    )
    parser.add_argument(
        "--fresh", action="store_true", help="Rebuild even if the snapshot is unchanged"
    )
    defaults = BuildConfig()
    parser.add_argument(
        "--min-rows",
        type=int,
        default=defaults.min_rows,
        help="Refuse to swap in a store with fewer rows (default: %(default)s)",
    )
    parser.add_argument(
        "--max-shrink",
        type=float,
        default=defaults.max_shrink,
        help="Refuse to swap in a store this fraction smaller than the live one "
        "(default: %(default)s)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not args.path:
        parser.error("--path or MWLIB_FILESTORE_PATH is required")
    username, password = os.environ.get("WME_USERNAME"), os.environ.get("WME_PASSWORD")
    if not (username and password):
        logger.error("WME_USERNAME and WME_PASSWORD environment variables are required")
        return 2

    client = WmeClient(username, password, snapshot_id=NS6_SNAPSHOT_ID)
    try:
        stats = build_file_store(
            live_path=Path(args.path),
            snapshot_id=client.snapshot_id,
            list_chunks=client.list_chunks,
            download_chunk=client.download_chunk,
            config=BuildConfig(min_rows=args.min_rows, max_shrink=args.max_shrink),
            fresh=args.fresh,
        )
    except BuildError as exc:
        logger.error("file store build failed: %s", exc)
        return 1
    if stats is None:
        logger.warning("another build is running; nothing done")
        return 0
    status = "unchanged" if stats.unchanged else "built"
    print(json.dumps({"status": status, **asdict(stats)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
