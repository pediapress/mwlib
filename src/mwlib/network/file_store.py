"""Local SQLite store of NS6 file-description pages (image metadata).

Resolves image description page data (templates, license, dimensions) from a
SQLite file built from the Wikimedia Enterprise NS6 snapshot (see
``mwlib.apps.file_store_builder``) instead of fetching it from the remote
MediaWiki API. Used for configured domains (default: en.wikipedia.org).

The file is only ever *read* here; the builder swaps new versions in with an
atomic rename. A ``None`` result from ``FileStore.lookup`` means the store is
*unavailable* (not configured, file missing or unreadable) and the caller falls
back to the remote API; ``{}`` means it answered and nothing matched.

File layout (``SCHEMA_VERSION`` 1)::

    meta(key TEXT PRIMARY KEY, value BLOB)
        schema_version, snapshot, chunk_versions
    files(name TEXT PRIMARY KEY, identifier INTEGER, date_modified TEXT,
          revision_id INTEGER, url TEXT, image_content_url TEXT,
          image_width INTEGER, image_height INTEGER,
          license TEXT, templates TEXT, categories TEXT)
        name is the canonical title with the ``File:`` prefix and spaces;
        license / templates / categories are the JSON lists WME ships,
        stored as text.

Written with ``journal_mode=DELETE`` (the file is opened read-only, which
cannot create a WAL sidecar). One connection per process, re-opened when the
file is replaced, so a process never pins the old inode after a swap.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from mwlib.utils import conf as default_conf

if TYPE_CHECKING:
    from mwlib.utils._conf import ConfMod

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"
SCHEMA_SQL = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value BLOB
);
CREATE TABLE files (
    name TEXT PRIMARY KEY,
    identifier INTEGER,
    date_modified TEXT,
    revision_id INTEGER,
    url TEXT,
    image_content_url TEXT,
    image_width INTEGER,
    image_height INTEGER,
    license TEXT,
    templates TEXT,
    categories TEXT
);
"""
COLUMNS = (
    "name",
    "identifier",
    "date_modified",
    "revision_id",
    "url",
    "image_content_url",
    "image_width",
    "image_height",
    "license",
    "templates",
    "categories",
)
_BATCH_SIZE = 500


class FileStore:
    """Read-only handle on a file-page store that follows file swaps."""

    def __init__(self, path: str | os.PathLike):
        self.path = str(path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._identity: tuple | None = None
        self._warned_missing = False

    def close(self) -> None:
        """Close the cached connection (used on swap, on errors and by tests)."""
        with self._lock:
            self._close()

    def _close(self) -> None:
        if self._conn is not None:
            self._conn.close()
        self._conn = None
        self._identity = None

    def _connection(self) -> sqlite3.Connection:
        st = os.stat(self.path)
        identity = (st.st_dev, st.st_ino, st.st_mtime_ns)
        if self._conn is None or self._identity != identity:
            self._close()
            conn = sqlite3.connect(
                Path(self.path).resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False
            )
            try:
                row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
                version = None if row is None else bytes(row[0]).decode()
                if version != SCHEMA_VERSION:
                    raise ValueError(f"unsupported file store schema in {self.path}: {version!r}")
            except Exception:
                conn.close()
                raise
            self._conn, self._identity = conn, identity
        return self._conn

    def is_available(self) -> bool:
        """True if the file exists and has a supported schema."""
        with self._lock:
            try:
                self._connection()
            except Exception:
                self._close()
                return False
            return True

    def lookup(self, names: list[str]) -> dict[str, dict] | None:
        """Rows for the given ``File:`` titles, keyed by the name as passed.

        Underscore titles match the space-form names stored in the file; the
        returned record's ``name`` is the title as passed, so callers can match
        rows against their request. Returns ``None`` when the store is
        unavailable (logged, never raised).
        """
        if not names:
            return {}

        by_storage: dict[str, list[str]] = {}
        for name in names:
            by_storage.setdefault(name.replace("_", " "), []).append(name)
        storage_names = list(by_storage)

        result: dict[str, dict] = {}
        with self._lock:
            try:
                conn = self._connection()
                self._warned_missing = False
                for start in range(0, len(storage_names), _BATCH_SIZE):
                    batch = storage_names[start : start + _BATCH_SIZE]
                    marks = ",".join("?" * len(batch))
                    rows = conn.execute(
                        f"SELECT {', '.join(COLUMNS)} FROM files WHERE name IN ({marks})",
                        batch,
                    )
                    for row in rows:
                        record = dict(zip(COLUMNS, row, strict=True))
                        for original in by_storage.get(record["name"], ()):
                            result[original] = {**record, "name": original}
            except FileNotFoundError:
                if not self._warned_missing:
                    self._warned_missing = True
                    logger.warning("File store %s does not exist (yet)", self.path)
                self._close()
                return None
            except Exception:
                logger.exception("File store lookup failed for %d files", len(names))
                self._close()
                return None
        logger.info("File store lookup: %d/%d files found", len(result), len(names))
        return result


class FileStoreImageLookup:
    """Batch lookup of image description page data from a ``FileStore``.

    Reads configuration from the [filestore] section (environment:
    ``MWLIB_FILESTORE_PATH`` / ``MWLIB_FILESTORE_DOMAINS``):
    - path: SQLite file to read; the lookup is off when unset
    - domains: Comma-separated list of domains to handle. The store is keyed
      by English ``File:`` titles, so only list wikis whose File namespace is
      called ``File`` (a localised ``Datei:`` wiki would always miss).
    """

    def __init__(self, conf: ConfMod | None = None):
        if conf is None:
            conf = default_conf

        self.path = conf.get("filestore", "path", "")
        # Hostnames are case-insensitive; lowercase the configured set so
        # ``EN.Wikipedia.ORG`` in config still matches ``en.wikipedia.org``
        # in a parsed URL.
        domains_str = conf.get("filestore", "domains", "en.wikipedia.org")
        self.domains = {d.strip().lower() for d in domains_str.split(",") if d.strip()}
        self.store = FileStore(self.path) if self.path else None
        # Decided once, when the fetch starts: the fetcher defers image
        # downloads and builds its license checker based on this answer, so it
        # must not flip mid-fetch. A store that vanishes later just makes
        # ``fetch_batch`` miss, and the remote-API fallback takes over.
        self._available = self.store is not None and self.store.is_available()

    @property
    def is_available(self) -> bool:
        """True if a store was configured and readable when this lookup was created."""
        return self._available

    def handles_domain(self, path: str) -> bool:
        """Return True if the host in ``path`` is exactly one of the configured domains.

        Uses hostname-exact matching, not substring containment. A naive
        ``"en.wikipedia.org" in path`` would also match attacker-controlled
        hosts like ``en.wikipedia.org.example.com`` or unrelated query
        strings. ``.hostname`` (rather than ``.netloc``) is what we want
        because it lowercases automatically and strips both ``user:pass@``
        and trailing ``:port`` — so ``https://en.wikipedia.org:443/x`` and
        ``https://EN.WIKIPEDIA.ORG/x`` both resolve to the same host.
        Anything that fails to parse as a URL is treated as a bare
        hostname for the convenience of callers who pass either form.
        """
        parsed = urlparse(path)
        host = parsed.hostname.lower() if parsed.hostname else ""
        if not host:
            # Caller passed a bare hostname (no scheme). Treat the whole
            # thing as the host, but still require an exact match.
            host = path.lower().strip("/")
        return host in self.domains

    def fetch_batch(self, titles: list[str]) -> tuple[list[dict], list[str]]:
        """Look up image description page data.

        Args:
            titles: List of image page titles (e.g., ["File:Example.jpg", ...])

        Returns:
            Tuple of (rows, missing_titles):
            - rows: List of dicts with store row data for found titles; each
              row's ``name`` is the requested title
            - missing_titles: Titles not found in the store (fall back to remote API)

        An unavailable store returns ``([], titles)`` so callers fall back to
        the remote API.
        """
        if not titles or self.store is None:
            return [], list(titles)

        found = self.store.lookup(titles)
        if found is None:
            return [], list(titles)
        rows = [found[t] for t in dict.fromkeys(titles) if t in found]
        missing = [t for t in titles if t not in found]
        return rows, missing
