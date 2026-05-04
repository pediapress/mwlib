#!/usr/bin/env python3
"""Fetch Wikimedia Enterprise namespace snapshots and load them into BigQuery.

Authentication:
    Uses WME_USERNAME / WME_PASSWORD env vars to obtain a bearer token from
    the Wikimedia Enterprise auth endpoint.

BigQuery:
    Uses ``BIGQUERY_CREDENTIALS`` (preferred) or ``GOOGLE_APPLICATION_CREDENTIALS``
    (fallback) — or the service-account JSON path passed via ``--credentials``
    — for authentication. The active SA's email is logged at INFO when the
    BigQuery client is constructed so 403 errors can be diagnosed without
    guessing which identity the request was signed with.

Namespaces:
    --namespace 6 (default): NS6 file description pages → ``file_pages`` table.
        Schema captures dimensions, license, templates, and categories — the
        fields needed to surface cover candidates and check print eligibility.
    --namespace 0: NS0 article HTML → ``article_pages`` table. Lean schema
        (name, identifier, article_body_html, date_modified) sized to keep
        BigQuery storage cost in line with what the page-count estimator
        actually consumes. The table is provisioned by Pulumi (clustered on
        ``name``) — this script never drops or recreates it.

Transport:
    The script auto-detects which transport WME exposes for the snapshot:

    1. **Chunked** (preferred). Snapshots whose ``/v2/snapshots/{id}/chunks``
       endpoint returns ≥1 chunk are pulled chunk-by-chunk. Each chunk is
       a small (~300 MB) atomic unit downloaded to disk, verified against
       the listing's ``version`` (== S3 ETag), loaded into BigQuery, and
       checkpointed into a JSON state file. A crash mid-run is resumable;
       a re-issued snapshot is detected by version drift and refused (the
       operator must rerun with ``--fresh``). EN NS0 is split into ~700
       chunks and **only** the chunked path produces a complete table —
       the legacy single-tarball ``/download`` returns just the first
       chunk-group, ~70% of the data.

    2. **Single tarball** (legacy fallback). Snapshots without a chunks
       endpoint, or runs invoked with ``--no-chunked``, download one
       multi-GB tarball, then iterate its NDJSON members in a
       just-in-time extract loop. Peak disk is "tarball + one extracted
       NDJSON". No resume; a TCP drop restarts the whole download.

Data handling:
    Each run replaces all data in the target table. The default load-job mode
    submits one BigQuery load job per NDJSON file (WRITE_TRUNCATE on the first
    chunk of a fresh run, WRITE_APPEND afterwards), so a single
    multi-hundred-GB intermediate file is never required. Resumed chunked
    runs always WRITE_APPEND. Streaming insert mode is preserved for
    operators who need it but is significantly more expensive at scale.

Usage examples:
    # List available snapshots
    python fetch_wikimedia_snapshot.py --list

    # Default: chunked load of NS6 (file_pages) — auto-detected
    python fetch_wikimedia_snapshot.py --project pediapress-prod --dataset wikipedia

    # Chunked load of NS0 (article_pages, EN article HTML, ~700 chunks)
    python fetch_wikimedia_snapshot.py --namespace 0 --project pediapress-prod

    # Resume a chunked run after a crash — picks up from the saved state
    python fetch_wikimedia_snapshot.py --namespace 0 --project pediapress-prod

    # Force-restart a chunked run from scratch (truncates the table)
    python fetch_wikimedia_snapshot.py --namespace 0 --fresh

    # Disable chunked path; use the legacy single-tarball /download endpoint
    python fetch_wikimedia_snapshot.py --namespace 6 --no-chunked

    # Load from an already-downloaded tarball (skip download)
    python fetch_wikimedia_snapshot.py --namespace 0 -i /path/to/enwiki_ns0.tar.gz

    # Use streaming inserts instead of batch load jobs
    python fetch_wikimedia_snapshot.py --streaming-insert --project pediapress-prod
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
# Silence urllib3's per-request DEBUG line. ``job.result()`` polls
# BigQuery every second or two for the duration of every load job —
# during a multi-hour EN NS0 refresh that's tens of thousands of
# debug lines that drown the script's actual progress logs. The
# request-failure path remains visible at WARNING and above.
logging.getLogger("urllib3").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

WME_AUTH_URL = "https://auth.enterprise.wikimedia.com/v1/login"
WME_API_BASE = "https://api.enterprise.wikimedia.com/v2"
_HTTP_NOT_FOUND = 404

# BigQuery schema for namespace 6 file description pages.
# Focused on fields needed for license checking. article_body html is omitted
# to avoid storage bloat — templates and categories cover license-checking needs.
NS6_SCHEMA = [
    {
        "name": "name",
        "type": "STRING",
        "mode": "REQUIRED",
        "description": "Page title (e.g. File:Example.jpg)",
    },
    {
        "name": "identifier",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "MediaWiki page ID",
    },
    {
        "name": "url",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Full URL to the wiki page",
    },
    {
        "name": "date_modified",
        "type": "TIMESTAMP",
        "mode": "NULLABLE",
        "description": "Last modification timestamp",
    },
    {
        "name": "license",
        "type": "JSON",
        "mode": "NULLABLE",
        "description": "License information array",
    },
    {
        "name": "templates",
        "type": "JSON",
        "mode": "NULLABLE",
        "description": "Templates used on the page (for license checking)",
    },
    {
        "name": "categories",
        "type": "JSON",
        "mode": "NULLABLE",
        "description": "Categories the page belongs to",
    },
    {
        "name": "abstract",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Short description / abstract",
    },
    {
        "name": "image_content_url",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "URL to the actual image file",
    },
    {
        "name": "image_width",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Image width in pixels",
    },
    {
        "name": "image_height",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "Image height in pixels",
    },
]

# BigQuery schema for namespace 0 article HTML.
# Deliberately minimal: storing full Parsoid HTML for English Wikipedia is the
# dominant cost in this dataset, so anything we don't need for the R3 page-count
# estimator (abstract, templates, categories, version metadata, wikitext, etc.)
# is dropped at ingest time. The table is clustered on ``name`` in Pulumi so
# point lookups by article title don't scan the whole table.
NS0_SCHEMA = [
    {
        "name": "name",
        "type": "STRING",
        "mode": "REQUIRED",
        "description": "Article title (e.g. 'Mainz')",
    },
    {
        "name": "identifier",
        "type": "INTEGER",
        "mode": "NULLABLE",
        "description": "MediaWiki page ID",
    },
    {
        "name": "date_modified",
        "type": "TIMESTAMP",
        "mode": "NULLABLE",
        "description": "Last modification timestamp (for snapshot freshness checks)",
    },
    {
        "name": "article_body_html",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "Parsoid HTML body — input to the page-count estimator",
    },
]

# Progress logging interval (bytes) during download
_DOWNLOAD_LOG_INTERVAL = 100 * 1024 * 1024  # log every 100 MB


def parse_ns6_row(line: str) -> dict | None:
    """Parse a single NS6 NDJSON line into a BigQuery-compatible row."""
    try:
        doc = json.loads(line)
    except json.JSONDecodeError:
        logger.warning("Skipping malformed JSON line: %s...", line[:100])
        return None

    name = doc.get("name")
    if not name:
        logger.warning("Skipping row with missing 'name' field: %s...", line[:100])
        return None

    row = {
        "name": name,
        "identifier": doc.get("identifier"),
        "url": doc.get("url"),
        "date_modified": doc.get("date_modified"),
    }

    # Serialize complex fields as JSON strings for BigQuery JSON columns
    if doc.get("license"):
        row["license"] = json.dumps(doc["license"])
    if doc.get("templates"):
        row["templates"] = json.dumps(doc["templates"])
    if doc.get("categories"):
        row["categories"] = json.dumps(doc["categories"])

    row["abstract"] = doc.get("abstract")

    image = doc.get("image")
    if image and isinstance(image, dict):
        row["image_content_url"] = image.get("content_url")
        row["image_width"] = image.get("width")
        row["image_height"] = image.get("height")

    return row


def parse_ns0_row(line: str) -> dict | None:
    """Parse a single NS0 NDJSON line into a lean BigQuery row.

    Drops every field except (name, identifier, date_modified, article_body_html).
    Rows missing ``article_body.html`` are skipped — they can't serve any R3
    query, and storing empty placeholders just bloats a table that already
    runs to hundreds of GB.
    """
    try:
        doc = json.loads(line)
    except json.JSONDecodeError:
        logger.warning("Skipping malformed JSON line: %s...", line[:100])
        return None

    name = doc.get("name")
    if not name:
        logger.warning("Skipping row with missing 'name' field: %s...", line[:100])
        return None

    article_body = doc.get("article_body")
    html = None
    if isinstance(article_body, dict):
        html = article_body.get("html")
    if not html:
        return None

    return {
        "name": name,
        "identifier": doc.get("identifier"),
        "date_modified": doc.get("date_modified"),
        "article_body_html": html,
    }


@dataclass(frozen=True)
class NamespaceConfig:
    """Per-namespace configuration: snapshot, target table, schema, parser.

    ``script_manages_table`` is True for tables this script creates and
    recreates on each run (NS6 — the legacy behaviour, preserved to avoid
    regressions). It is False for tables provisioned externally (NS0 —
    declared in Pulumi); for those, the script only loads data and never
    drops the table.
    """

    namespace: int
    snapshot_id: str
    table_id: str
    schema: list[dict]
    parser: Callable[[str], dict | None]
    script_manages_table: bool


NAMESPACES: dict[int, NamespaceConfig] = {
    6: NamespaceConfig(
        namespace=6,
        snapshot_id="enwiki_namespace_6",
        table_id="file_pages",
        schema=NS6_SCHEMA,
        parser=parse_ns6_row,
        script_manages_table=True,
    ),
    0: NamespaceConfig(
        namespace=0,
        snapshot_id="enwiki_namespace_0",
        table_id="article_pages",
        schema=NS0_SCHEMA,
        parser=parse_ns0_row,
        script_manages_table=False,
    ),
}


def get_bearer_token(username: str, password: str) -> str:
    """Authenticate with Wikimedia Enterprise and return an access token."""
    logger.info("Authenticating with Wikimedia Enterprise API...")
    resp = requests.post(
        WME_AUTH_URL,
        json={"username": username, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    logger.info("Authentication successful (token expires in %ss)", data.get("expires_in"))
    return token


def list_snapshots(token: str) -> list[dict]:
    """List available snapshots from the Wikimedia Enterprise API."""
    resp = requests.get(
        f"{WME_API_BASE}/snapshots",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def download_snapshot_streaming(
    token: str,
    snapshot_id: str,
    output_path: Path,
) -> Path:
    """Download a snapshot as a gzipped tarball, streaming to disk.

    Verifies download completeness by comparing bytes received to Content-Length.
    """
    url = f"{WME_API_BASE}/snapshots/{snapshot_id}/download"
    logger.info("Downloading snapshot %s to %s (streaming)...", snapshot_id, output_path)

    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=(30, None),  # 30s connect, no read timeout for large downloads
    )
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    last_logged = 0
    sha256 = hashlib.sha256()

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):  # 8MB chunks
            f.write(chunk)
            sha256.update(chunk)
            downloaded += len(chunk)
            if downloaded - last_logged >= _DOWNLOAD_LOG_INTERVAL:
                if total > 0:
                    pct = 100.0 * downloaded / total
                    logger.info("  %.1f%% (%d / %d MB)", pct, downloaded >> 20, total >> 20)
                else:
                    logger.info("  %d MB downloaded", downloaded >> 20)
                last_logged = downloaded

    if total > 0 and downloaded != total:
        os.unlink(output_path)
        raise RuntimeError(
            f"Download incomplete: expected {total} bytes, got {downloaded}. "
            f"File removed. Please retry."
        )

    logger.info(
        "Download complete: %s (%d MB, sha256=%s)",
        output_path,
        downloaded >> 20,
        sha256.hexdigest()[:16],
    )
    return output_path


def _validate_tar_member(member: tarfile.TarInfo) -> None:
    """Reject anything that isn't a regular file at a safe relative path.

    A crafted tarball could otherwise smuggle in symlinks, hardlinks,
    devices, or absolute / parent-traversal paths and trick
    ``tar.extract`` into writing or reading outside ``extract_dir``.
    Combined with the ``shutil.copyfileobj`` extraction below, this
    ensures we only ever materialise plain regular files at relative
    paths under the tarball's parent directory.
    """
    name = member.name
    p = Path(name)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"Suspicious tar member path: {name}")
    if not member.isfile():
        raise ValueError(
            f"Refusing to extract non-regular tar member: {name} (type={member.type!r})"
        )


def iter_extract_ndjson(tarball_path: Path) -> Iterator[Path]:
    """Yield each .ndjson member of the tarball, extracting just-in-time.

    The previously yielded NDJSON is unlinked before the next is extracted
    (and the last one is unlinked when the iterator finishes), so peak local
    disk usage stays at "tarball + at most one extracted NDJSON" rather than
    "tarball + every NDJSON". For NS0 EN this is the difference between a
    feasible sync and one that needs a TB of free disk.

    Members are validated as regular files at relative paths and then
    streamed via ``shutil.copyfileobj`` rather than handed to
    ``tar.extract`` — see ``_validate_tar_member``.

    Extraction lands in a private temporary directory rather than the
    tarball's parent. Otherwise a member named ``existing.ndjson`` would
    overwrite ``/path/to/existing.ndjson`` whenever the operator passes
    ``-i /path/to/snapshot.tar.gz``, and our cleanup would then unlink
    a file we didn't create.
    """
    with tempfile.TemporaryDirectory(prefix="wme-ndjson-", dir=tarball_path.parent) as tmp:
        extract_dir = Path(tmp)

        with tarfile.open(tarball_path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.name.endswith(".ndjson")]
            if not members:
                raise ValueError(f"No .ndjson files found in {tarball_path}")
            for m in members:
                _validate_tar_member(m)

            logger.info(
                "Tarball contains %d NDJSON files; will extract one at a time",
                len(members),
            )

            for idx, member in enumerate(members, 1):
                src = tar.extractfile(member)
                if src is None:
                    raise ValueError(f"Cannot extract tar member: {member.name}")
                path = extract_dir / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                with src, open(path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                logger.info("Extracted %d/%d: %s (%d bytes)", idx, len(members), path, member.size)
                try:
                    yield path
                finally:
                    if path.exists():
                        try:
                            path.unlink()
                            logger.info("Removed extracted NDJSON: %s", path)
                        except OSError:
                            logger.exception("Failed to clean up %s", path)


# ---------------------------------------------------------------------------
# Chunked ingest (WME /chunks API)
#
# Large snapshots (notably EN NS0, ~700 chunks at ~300 MB each) are exposed by
# WME as individually-downloadable chunks under
#     GET /v2/snapshots/{id}/chunks
#     GET /v2/snapshots/{id}/chunks/{chunk_id}/download
#
# The legacy ``/download`` endpoint only returns the first chunk-group of such
# snapshots, which silently produces an *incomplete* table. The chunked path
# below replaces that for any snapshot whose ``/chunks`` listing returns at
# least one entry, and adds three properties the single-tarball path lacks:
#
#   1. **Per-chunk atomicity** — each chunk is downloaded fully (~30 s),
#      verified against the listing's ``version`` (== S3 ETag), loaded into
#      BigQuery, and only then checkpointed. A network drop or BigQuery error
#      mid-chunk loses ~30 s of work, never the whole table.
#   2. **Crash-safe resume** — a tiny JSON state file on disk records which
#      chunk versions have already loaded. Re-running the script picks up
#      where it left off, skipping completed chunks. Single-chunk reruns are
#      ``WRITE_APPEND``; only the first chunk of a brand-new run truncates.
#   3. **Snapshot-rotation safety** — if WME has re-issued the snapshot
#      since the previous run (every chunk's ``version`` differs from the
#      saved one) we refuse to silently mix versions and tell the operator
#      to rerun with ``--fresh``.
# ---------------------------------------------------------------------------

# Read timeout per chunk (in seconds). Each chunk is ~300 MB; at 11 MB/s
# transatlantic that's ~30 s, so 5 minutes is a generous "the connection
# has clearly stalled" cutoff. The single-tarball path uses ``timeout=(30,
# 300)`` for the same reason.
_CHUNK_HTTP_TIMEOUT = (30, 300)
_CHUNK_DOWNLOAD_RETRIES = 3
_CHUNK_RETRY_BACKOFF_BASE_SECONDS = 10


def list_chunks(token: str, snapshot_id: str) -> list[dict]:
    """List chunk metadata for a snapshot via the WME ``/chunks`` endpoint.

    Returns the raw list of dicts (each carries ``identifier``, ``version``,
    ``size``, ``date_modified``, …). Returns an empty list for snapshots
    that don't expose chunks — the caller should fall back to the
    single-tarball path in that case.
    """
    resp = requests.get(
        f"{WME_API_BASE}/snapshots/{snapshot_id}/chunks",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == _HTTP_NOT_FOUND:
        return []
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list):
        return []
    return payload


def download_chunk(
    token: str,
    snapshot_id: str,
    chunk_id: str,
    output_path: Path,
    *,
    retries: int = _CHUNK_DOWNLOAD_RETRIES,
) -> str:
    """Download a single chunk to ``output_path`` with retry-on-failure.

    Each attempt is a fresh whole-file GET — no byte-range resume within a
    chunk. Chunks are small enough (~300 MB / ~30 s) that whole-file retry
    is cheaper than the bookkeeping of a partial-chunk resume.

    Returns the response ``ETag`` (which WME populates with the chunk's
    content hash; matches the listing's ``version`` field).
    """
    url = f"{WME_API_BASE}/snapshots/{snapshot_id}/chunks/{chunk_id}/download"
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                stream=True,
                timeout=_CHUNK_HTTP_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                expected = int(resp.headers.get("content-length", 0))
                etag = resp.headers.get("etag", "").strip('"')
                received = 0
                last_logged = 0
                with open(output_path, "wb") as f:
                    for piece in resp.iter_content(chunk_size=8 * 1024 * 1024):
                        f.write(piece)
                        received += len(piece)
                        # Periodic progress so a slow link doesn't look hung.
                        # Cross-Atlantic single-stream downloads sit around
                        # ~10 MB/s; without this the operator sees nothing
                        # for ~30 s per 300 MB chunk.
                        if received - last_logged >= _DOWNLOAD_LOG_INTERVAL:
                            if expected:
                                pct = 100.0 * received / expected
                                logger.info(
                                    "    %s: %.1f%% (%d / %d MB)",
                                    chunk_id,
                                    pct,
                                    received >> 20,
                                    expected >> 20,
                                )
                            else:
                                logger.info(
                                    "    %s: %d MB downloaded",
                                    chunk_id,
                                    received >> 20,
                                )
                            last_logged = received
                if expected and received != expected:
                    raise OSError(f"chunk {chunk_id}: short read ({received} of {expected} bytes)")
                return etag
        except (requests.RequestException, OSError) as exc:
            last_exc = exc
            if output_path.exists():
                with contextlib.suppress(OSError):
                    output_path.unlink()
            if attempt < retries:
                wait = _CHUNK_RETRY_BACKOFF_BASE_SECONDS * (3 ** (attempt - 1))
                logger.warning(
                    "chunk %s attempt %d/%d failed: %s — retry in %ds",
                    chunk_id,
                    attempt,
                    retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
    assert last_exc is not None  # for mypy; loop guarantees it's set
    raise last_exc


@dataclass
class ChunkLoadState:
    """Resume-state for a chunked ingest run.

    Tracks which chunk versions have already been loaded into BigQuery so a
    rerun can skip them. Persisted to ``state_path`` after every successful
    chunk load — the file is the durable record of partial progress.

    Mismatched ``snapshot`` between state and current run is a hard error:
    the operator either hit the wrong CLI args or the state file is stale.
    A re-issued snapshot (same id, every chunk's ``version`` changed) is
    also caught at chunk-iteration time so we never mix old and new data.
    """

    run_id: str
    snapshot: str
    started_at: str
    chunks_loaded: dict[str, str] = field(default_factory=dict)
    # ``swap_done`` is the second-stage flag: chunks load into a staging
    # table, then a single MERGE atomically replaces the destination
    # table's contents. A run that crashes between "all chunks loaded"
    # and "MERGE complete" resumes by running just the swap, not by
    # re-loading data. ``False`` (or absent) means swap still pending.
    swap_done: bool = False

    @classmethod
    def new(cls, snapshot_id: str) -> ChunkLoadState:
        return cls(
            run_id=str(uuid.uuid4()),
            snapshot=snapshot_id,
            started_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def load(cls, path: Path) -> ChunkLoadState:
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        # Atomic write: write to a sibling tempfile then rename. Avoids
        # leaving a half-written state on disk if the process is killed
        # between the open() and the final flush.
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(path)


def _default_state_path(snapshot_id: str) -> Path:
    """State-file path used when ``--state-file`` isn't passed.

    Lives under the system temp dir, keyed by snapshot id so concurrent
    runs for different namespaces (NS6 / NS0) don't clobber each other.
    """
    return Path(tempfile.gettempdir()) / f"wme-ingest-{snapshot_id}.state.json"


def _iter_chunk_ndjson(chunk_path: Path) -> Iterator[Path]:
    """Yield NDJSON file path(s) extracted from a downloaded chunk.

    Each WME chunk is either a gzipped NDJSON (most common) or a tar.gz
    wrapping one or more NDJSON members (matches the legacy single-tarball
    layout). Both shapes appear in the wild depending on the namespace and
    the snapshot generation, so detect by trying tarfile first and falling
    back to a plain gzip stream.

    The yielded NDJSON file lives in a ``TemporaryDirectory`` rooted next
    to the chunk and is deleted after the consumer finishes with it.
    """
    with tempfile.TemporaryDirectory(prefix="wme-chunk-", dir=chunk_path.parent) as tmp:
        extract_dir = Path(tmp)
        try:
            with tarfile.open(chunk_path, "r:gz") as tar:
                members = [m for m in tar.getmembers() if m.name.endswith(".ndjson")]
                for m in members:
                    _validate_tar_member(m)
                if not members:
                    raise ValueError(f"chunk {chunk_path.name}: tar contains no .ndjson members")
                for member in members:
                    src = tar.extractfile(member)
                    if src is None:
                        raise ValueError(f"chunk {chunk_path.name}: cannot extract {member.name}")
                    out = extract_dir / member.name
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with src, open(out, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    try:
                        yield out
                    finally:
                        if out.exists():
                            out.unlink()
                return
        except tarfile.ReadError:
            pass

        # Not a tarball — assume gzipped NDJSON.
        out = extract_dir / f"{chunk_path.stem}.ndjson"
        with gzip.open(chunk_path, "rb") as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst)
        try:
            yield out
        finally:
            if out.exists():
                out.unlink()


def load_chunked_to_bigquery(
    *,
    token: str,
    chunks: list[dict],
    project: str,
    dataset: str,
    ns: NamespaceConfig,
    credentials_path: str | None,
    state_path: Path,
    fresh: bool,
    work_dir: Path | None = None,
    use_streaming_insert: bool = False,
    batch_size: int = 10_000,
) -> tuple[int, int]:
    """Iterate WME chunks, downloading and BigQuery-loading each atomically.

    Two-stage load to keep the destination table queryable throughout the
    refresh window:

    1. Each chunk loads into a per-namespace **staging** table (e.g.
       ``article_pages_staging``). The first chunk of a fresh run uses
       ``WRITE_TRUNCATE`` to wipe any leftover staging from a previous
       failed run; subsequent chunks ``WRITE_APPEND`` into staging. The
       destination table is *not* touched during this phase, so readers
       continue to see the previous snapshot's data.

    2. After every chunk is in staging, a single atomic ``MERGE``
       statement replaces the destination table's contents in one shot —
       readers transition from "old snapshot" to "new snapshot" with no
       window of partial or missing data. The ``MERGE`` UPSERTs rows
       present in staging and DELETEs target rows whose key isn't in
       staging (full snapshot replacement semantics).

    Crash-safe: a run that dies between "all chunks loaded" and "MERGE
    complete" resumes by running just the MERGE on the next invocation
    (no re-loading). The state file's ``swap_done`` flag distinguishes
    "still loading chunks" from "loaded, just need the swap".

    Returns ``(rows_loaded, rows_skipped)`` aggregated across all chunks
    actually processed in this invocation. Chunks skipped because they
    were already loaded in a previous run aren't counted (their rows were
    counted by the previous run).
    """
    from google.cloud import bigquery

    from mwlib.network.bigquery_lookup import _validate_bigquery_identifier

    client = _make_bq_client(project, credentials_path)
    safe_project = _validate_bigquery_identifier(project, "project")
    safe_dataset = _validate_bigquery_identifier(dataset, "dataset")
    safe_table = _validate_bigquery_identifier(ns.table_id, "table")
    safe_staging_table = _validate_bigquery_identifier(
        f"{ns.table_id}{_STAGING_TABLE_SUFFIX}", "staging table"
    )
    table_ref = f"{safe_project}.{safe_dataset}.{safe_table}"
    staging_ref = f"{safe_project}.{safe_dataset}.{safe_staging_table}"

    if fresh and state_path.exists():
        state_path.unlink()
        logger.info("--fresh: removed previous state %s", state_path)

    if state_path.exists():
        state = ChunkLoadState.load(state_path)
        if state.snapshot != ns.snapshot_id:
            raise RuntimeError(
                f"state file {state_path} is for snapshot "
                f"{state.snapshot!r} but this run targets "
                f"{ns.snapshot_id!r}; pick a different --state-file or "
                f"rerun with --fresh"
            )
        logger.info(
            "resuming run %s: %d/%d chunks already loaded",
            state.run_id,
            len(state.chunks_loaded),
            len(chunks),
        )
    else:
        state = ChunkLoadState.new(ns.snapshot_id)
        logger.info("starting new run %s (%d chunks)", state.run_id, len(chunks))

    # Detect snapshot-rotation: any saved chunk whose id reappears in the
    # current listing with a different version means WME has re-issued the
    # snapshot. Refuse rather than silently mix versions across runs.
    by_id = {c["identifier"]: c for c in chunks}
    drift = [
        (cid, ver, by_id[cid]["version"])
        for cid, ver in state.chunks_loaded.items()
        if cid in by_id and by_id[cid]["version"] != ver
    ]
    if drift:
        sample = drift[:3]
        raise RuntimeError(
            f"snapshot {ns.snapshot_id!r} appears to have been re-issued: "
            f"{len(drift)} chunk(s) now offer a different version than the "
            f"saved state. Examples: {sample}. "
            f"Rerun with --fresh to start over against the new snapshot."
        )

    # Verify the destination table exists. We never drop/recreate it
    # during a refresh — the staging+swap pattern keeps it queryable
    # the whole time, and Pulumi-managed properties on it stay intact.
    starting_fresh = not state.chunks_loaded
    if starting_fresh:
        _prepare_table(client, table_ref, ns)

    schema = None
    if use_streaming_insert:
        # The streaming-insert path doesn't go through staging — it's a
        # legacy code path for operators who explicitly opt in, and
        # streaming inserts to a staging table followed by a MERGE
        # double-counts the cost. For now, --streaming-insert preserves
        # the old TRUNCATE+APPEND-on-target semantics. If you need
        # zero-downtime *and* streaming, file an issue.
        if starting_fresh and not ns.script_manages_table:
            logger.info("Truncating %s before streaming inserts", table_ref)
            client.query(f"TRUNCATE TABLE `{table_ref}`").result()
    else:
        schema = _make_bq_schema(ns.schema)

    work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="wme-chunks-"))
    work_dir.mkdir(parents=True, exist_ok=True)
    logger.info("chunk work dir: %s", work_dir)

    total_loaded = 0
    total_skipped = 0
    chunks_processed = 0
    for i, chunk in enumerate(chunks, 1):
        cid = chunk["identifier"]
        version = chunk["version"]
        if state.chunks_loaded.get(cid) == version:
            logger.info("[%d/%d] skip already-loaded %s", i, len(chunks), cid)
            continue

        logger.info(
            "[%d/%d] download %s (%s MB)",
            i,
            len(chunks),
            cid,
            chunk.get("size", {}).get("value", "?"),
        )
        chunk_path = work_dir / cid
        try:
            etag = download_chunk(token, ns.snapshot_id, cid, chunk_path)
            if etag and etag != version:
                logger.warning(
                    "chunk %s ETag %r differs from listing version %r — "
                    "proceeding (chunks API is the authoritative listing)",
                    cid,
                    etag,
                    version,
                )

            # WRITE_TRUNCATE on the very first chunk of a fresh run, on
            # the *staging* table — wipes any leftover staging from a
            # previous failed run before populating it from chunk 0.
            # Subsequent chunks (and all chunks of a resumed run, since
            # staging already holds the resumed state) WRITE_APPEND.
            # Either way the destination ``table_ref`` is *not* touched
            # during this phase; readers continue to see the pre-refresh
            # snapshot.
            is_first_load = chunks_processed == 0 and starting_fresh
            for ndjson_path in _iter_chunk_ndjson(chunk_path):
                if use_streaming_insert:
                    # Legacy path — streaming inserts go straight to the
                    # destination, not through staging. See the
                    # ``starting_fresh and not ns.script_manages_table``
                    # comment above for the rationale.
                    loaded, skipped = _stream_one_file(
                        client=client,
                        table_ref=table_ref,
                        ndjson_path=ndjson_path,
                        parser=ns.parser,
                        batch_size=batch_size,
                    )
                else:
                    write_disposition = (
                        bigquery.WriteDisposition.WRITE_TRUNCATE
                        if is_first_load
                        else bigquery.WriteDisposition.WRITE_APPEND
                    )
                    loaded, skipped = _load_one_file(
                        client=client,
                        ndjson_path=ndjson_path,
                        file_idx=i,
                        table_ref=staging_ref,
                        schema=schema,
                        parser=ns.parser,
                        write_disposition=write_disposition,
                    )
                total_loaded += loaded
                total_skipped += skipped
                # If a chunk has multiple NDJSON members (rare), all but
                # the first must append even within a fresh-run first chunk.
                is_first_load = False
        finally:
            if chunk_path.exists():
                try:
                    chunk_path.unlink()
                except OSError:
                    logger.exception("failed to unlink %s", chunk_path)

        state.chunks_loaded[cid] = version
        state.save(state_path)
        chunks_processed += 1

    logger.info(
        "Chunked load complete (staging): %d chunks processed in this run, "
        "%d skipped (already loaded by prior run), "
        "%d rows loaded, %d rows skipped",
        chunks_processed,
        len(chunks) - chunks_processed,
        total_loaded,
        total_skipped,
    )

    all_chunks_loaded = len(state.chunks_loaded) >= len(chunks)

    # Atomic MERGE swap: replace destination contents from staging in
    # one statement, then drop staging. Skipped on the streaming-insert
    # path (which loads directly to the destination — no staging exists).
    # Skipped if a previous run already swapped (state.swap_done) — that
    # can happen if the run died after the swap but before the state
    # file was cleaned up; the MERGE would be a no-op against an empty
    # already-dropped staging table anyway, but skipping is cheaper.
    if all_chunks_loaded and not use_streaming_insert and not state.swap_done:
        _swap_staging_into_target(
            client,
            target_ref=table_ref,
            staging_ref=staging_ref,
            schema=ns.schema,
        )
        state.swap_done = True
        state.save(state_path)
        # Drop staging now that it's served its purpose. Best-effort:
        # a failure here leaves an orphan staging table that the next
        # run's WRITE_TRUNCATE on first chunk will recycle anyway, so
        # no need to fail the whole ingest over it.
        try:
            client.delete_table(staging_ref, not_found_ok=True)
            logger.info("Dropped staging table %s", staging_ref)
        except Exception:
            logger.exception("Failed to drop staging table %s; continuing", staging_ref)

    # Successful end-to-end run: drop the state file so the next invocation
    # starts fresh by default. (If the operator wants to keep it as an
    # audit trail, they can copy it before running.)
    run_complete = all_chunks_loaded and (use_streaming_insert or state.swap_done)
    if run_complete and state_path.exists():
        state_path.unlink()
        logger.info("All chunks loaded and swapped; cleared state file %s", state_path)

    return total_loaded, total_skipped


def _make_bq_client(project: str, credentials_path: str | None):
    """Create a BigQuery client with optional service account credentials.

    Logs the active service-account email at INFO so the operator can tell
    at a glance which SA is talking to BigQuery — IAM 403s look identical
    whether the wrong SA is loaded or the right SA lacks a binding, and
    knowing which SA the request is signed with cuts the diagnosis from
    a guessing game to a one-line check.
    """
    from google.cloud import bigquery
    from google.oauth2 import service_account

    if credentials_path:
        creds = service_account.Credentials.from_service_account_file(credentials_path)
        logger.info(
            "BigQuery client authenticating as %s (from %s)",
            creds.service_account_email,
            credentials_path,
        )
        return bigquery.Client(project=project, credentials=creds)

    # No explicit credentials path — google-auth's default chain (env vars,
    # gcloud user creds, GCE metadata server, …). Log whatever it picks so
    # the operator isn't left wondering which identity ended up in play.
    import google.auth

    creds, _ = google.auth.default()
    sa_email = getattr(creds, "service_account_email", None)
    logger.info(
        "BigQuery client authenticating via google-auth default chain (%s)",
        sa_email or f"non-SA credentials of type {type(creds).__name__}",
    )
    return bigquery.Client(project=project, credentials=creds)


def _make_bq_schema(schema: list[dict]):
    """Build a list of BigQuery SchemaField objects from a schema spec."""
    from google.cloud import bigquery

    return [
        bigquery.SchemaField(
            name=f["name"],
            field_type=f["type"],
            mode=f["mode"],
            description=f.get("description", ""),
        )
        for f in schema
    ]


def _prepare_table(client, table_ref: str, ns: NamespaceConfig) -> None:
    """Ensure the destination table exists with the right schema.

    For script-managed namespaces (NS6) the table is recreated on every
    run — that's the long-standing behaviour and keeps schema changes
    effortless.

    For externally-managed tables (NS0 → Pulumi) the script must NOT
    bootstrap the table. Pulumi is the source of truth for the
    clustering / deletion-protection / partitioning settings; if we
    silently created the table when missing we'd produce a stripped-down
    table without those guarantees and the next Pulumi run would see
    drift. Fail loudly with a pointer to the operator instead.
    """
    from google.cloud import bigquery

    if ns.script_manages_table:
        schema = _make_bq_schema(ns.schema)
        table = bigquery.Table(table_ref, schema=schema)
        client.delete_table(table_ref, not_found_ok=True)
        client.create_table(table)
        logger.info("Created BigQuery table %s", table_ref)
    else:
        # ``get_table`` returns a 404 if the table truly doesn't exist and a
        # 403 if it exists but the calling SA lacks ``bigquery.tables.get``.
        # The two diagnoses lead the operator to very different fixes
        # (provision via Pulumi vs. grant IAM), so distinguish them.
        from google.api_core.exceptions import Forbidden, NotFound

        try:
            client.get_table(table_ref)
        except NotFound as exc:
            raise RuntimeError(
                f"BigQuery table {table_ref} is externally managed (e.g. by "
                f"Pulumi) and was not found. Provision it before running the "
                f"ingest — the script refuses to bootstrap a missing "
                f"externally-managed table because doing so would silently "
                f"drop clustering / deletion-protection settings."
            ) from exc
        except Forbidden as exc:
            raise RuntimeError(
                f"BigQuery table {table_ref} exists but the calling service "
                f"account is denied ``bigquery.tables.get``. Grant "
                f"``roles/bigquery.dataEditor`` on the dataset (and "
                f"``roles/bigquery.jobUser`` at project level) to whichever "
                f"SA the worker uses — typically the one mounted at "
                f"``BIGQUERY_CREDENTIALS`` / ``GOOGLE_APPLICATION_CREDENTIALS``."
            ) from exc
        logger.info("Using BigQuery table %s (managed externally)", table_ref)


def _swap_staging_into_target(
    client,
    *,
    target_ref: str,
    staging_ref: str,
    schema: list[dict],
    primary_key: str = "name",
) -> None:
    """Atomically replace ``target_ref`` contents with ``staging_ref`` via MERGE.

    Single-statement MERGE handles UPSERT (rows present in both / staging
    only) and DELETE (rows in target whose key isn't in staging). BigQuery
    treats MERGE as atomic — readers querying ``target_ref`` during the
    swap see either the pre-swap state or the post-swap state, never a
    partial mix and never a "table not found" error. Pulumi-managed
    properties on ``target_ref`` (clustering, deletion_protection) are
    untouched because the table itself is never dropped or recreated.

    ``primary_key`` is the column used as the join key. Defaults to
    ``"name"`` — matches both ``article_pages`` (article title) and
    ``file_pages`` (``File:…`` page title), the only namespaces this
    script handles today. If a future namespace is keyed differently the
    caller should pass the right column.
    """
    columns = [f["name"] for f in schema]
    if primary_key not in columns:
        raise ValueError(f"primary_key {primary_key!r} not in schema columns {columns!r}")
    non_key_cols = [c for c in columns if c != primary_key]

    # Build the MERGE statement. The table identifiers come from
    # ``_validate_bigquery_identifier`` upstream, and column names come
    # from a hard-coded schema dict — both are safe against injection.
    set_clause = (
        ", ".join(f"{c} = S.{c}" for c in non_key_cols) or f"{primary_key} = S.{primary_key}"
    )
    insert_cols = ", ".join(columns)
    insert_vals = ", ".join(f"S.{c}" for c in columns)

    merge_sql = f"""
    MERGE `{target_ref}` T
    USING `{staging_ref}` S
    ON T.{primary_key} = S.{primary_key}
    WHEN MATCHED THEN UPDATE SET {set_clause}
    WHEN NOT MATCHED BY TARGET THEN INSERT ({insert_cols}) VALUES ({insert_vals})
    WHEN NOT MATCHED BY SOURCE THEN DELETE
    """
    logger.info("Atomic MERGE swap: %s <- %s", target_ref, staging_ref)
    job = client.query(merge_sql)
    job.result()
    if job.errors:
        logger.error("MERGE job completed with errors:")
        for err in job.errors:
            logger.error("  %s", err)
        raise RuntimeError(f"MERGE swap into {target_ref} failed; see logs above")
    affected = getattr(job, "num_dml_affected_rows", None)
    logger.info("Atomic MERGE swap complete: %s rows affected in %s", affected, target_ref)


def _insert_batch_with_retry(client, table_ref: str, batch: list[dict]) -> tuple[int, int]:
    """Insert a batch of rows, retrying failed rows once.

    Returns (inserted_count, failed_count).
    """
    errors = client.insert_rows_json(table_ref, batch)
    if not errors:
        return len(batch), 0

    failed_indices = set()
    for err in errors:
        idx = err.get("index")
        if idx is not None:
            failed_indices.add(idx)
        for detail in err.get("errors", []):
            logger.warning("  Insert error: %s", detail)

    if not failed_indices:
        logger.warning("Insert returned %d errors but no row indices", len(errors))
        return 0, len(batch)

    succeeded = len(batch) - len(failed_indices)

    retry_batch = [batch[i] for i in sorted(failed_indices)]
    logger.info("Retrying %d failed rows...", len(retry_batch))
    retry_errors = client.insert_rows_json(table_ref, retry_batch)
    if not retry_errors:
        return len(batch), 0

    permanent_failures = len(retry_errors)
    for err in retry_errors[:3]:
        logger.error("Permanent insert failure: %s", err)

    return succeeded + (len(retry_batch) - permanent_failures), permanent_failures


def _stream_one_file(
    *,
    client,
    table_ref: str,
    ndjson_path: Path,
    parser: Callable[[str], dict | None],
    batch_size: int,
) -> tuple[int, int]:
    """Stream one NDJSON file's rows into BigQuery via insert_rows_json.

    Returns (rows_inserted, rows_skipped).
    """
    inserted_total = 0
    skipped = 0
    errors_total = 0
    batch: list[dict] = []

    with open(ndjson_path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            row = parser(line)
            if row is None:
                skipped += 1
                continue
            batch.append(row)
            if len(batch) >= batch_size:
                inserted, failed = _insert_batch_with_retry(client, table_ref, batch)
                inserted_total += inserted
                errors_total += failed
                logger.info(
                    "  Streamed %d rows (%d total, %d errors so far)",
                    inserted,
                    inserted_total,
                    errors_total,
                )
                batch = []

    if batch:
        inserted, failed = _insert_batch_with_retry(client, table_ref, batch)
        inserted_total += inserted
        errors_total += failed

    if errors_total > 0:
        logger.error(
            "WARNING: %d rows failed to insert from %s. Table may be incomplete.",
            errors_total,
            ndjson_path.name,
        )
    return inserted_total, skipped


# Default cap on transformed bytes per BigQuery load job. Sized so a
# typical chunk's transformed NDJSON (~2 GB for EN NS0 article HTML)
# becomes a single load job, which matters for two reasons:
#
# 1. **BigQuery quota.** The "load jobs per table per day" hard limit
#    is 1,500. A 419-chunk EN NS0 refresh splitting each chunk into
#    ~10 batches at the previous 200 MB cap would issue ~4,200 jobs
#    against ``article_pages`` and trip the quota mid-refresh.
#    One job per chunk -> 419 jobs/refresh, well under the ceiling.
#
# 2. **Atomicity.** ``WRITE_APPEND`` semantics mean a chunk that's
#    mid-load when something fails (quota hit, network blip, BQ 5xx)
#    leaves partially-loaded batches behind; on resume the whole chunk
#    re-loads and those rows are duplicated. One job per chunk = either
#    the whole chunk's rows are in BQ or none are, with no
#    re-load-on-retry duplication.
#
# Operators with smaller datasets or who specifically want fine-grained
# load-job retries can override per call site; this is just the default.
_DEFAULT_LOAD_BATCH_BYTES = 4 * 1024 * 1024 * 1024

# Interval (seconds) between progress logs while polling a load job that
# hasn't finished yet. The default ``job.result()`` blocks silently with
# its own backoff schedule; for the multi-minute waits a 2 GB chunk's
# load can take, we want a heartbeat in the log instead.
_LOAD_JOB_POLL_INTERVAL = 30

# Suffix appended to the destination table name to derive the staging
# table that chunks land in during a refresh. The staging table is
# wiped at the start of a fresh run, populated chunk-by-chunk, then
# its contents are MERGE-swapped into the destination atomically. Kept
# in the same dataset so a single set of IAM grants covers both.
_STAGING_TABLE_SUFFIX = "_staging"


def _submit_batch_load_job(
    *,
    client,
    table_ref: str,
    batch_path: Path,
    schema,
    write_disposition,
    file_idx: int,
    batch_idx: int,
    rows_in_batch: int,
    bytes_in_batch: int,
) -> int:
    """Submit one BigQuery load job for a transformed-NDJSON batch file.

    Returns the BigQuery-reported ``output_rows``. Caller is responsible
    for unlinking ``batch_path``.
    """
    from google.cloud import bigquery

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=write_disposition,
        max_bad_records=0,
    )
    with open(batch_path, "rb") as source:
        load_job = client.load_table_from_file(source, table_ref, job_config=job_config)
    started_at = time.monotonic()
    logger.info(
        "BQ load: file %d batch %d started (%s rows=%d, %d MB, disposition=%s)",
        file_idx,
        batch_idx,
        load_job.job_id,
        rows_in_batch,
        bytes_in_batch >> 20,
        write_disposition,
    )

    # Block on completion, but log a heartbeat every poll interval so the
    # operator can tell a slow-but-progressing load apart from a stalled
    # job. ``add_done_callback`` would be cleaner but doesn't fire until
    # ``.result()`` is called anyway, so a plain poll loop is simpler.
    while not load_job.done(retry=None):
        elapsed = time.monotonic() - started_at
        logger.info(
            "BQ load: file %d batch %d still running (state=%s, %.0fs elapsed)",
            file_idx,
            batch_idx,
            getattr(load_job, "state", "?"),
            elapsed,
        )
        time.sleep(_LOAD_JOB_POLL_INTERVAL)
    # ``done()`` returning True doesn't necessarily reload error state;
    # ``result()`` does, and re-raises any exception the job recorded.
    load_job.result()
    if load_job.errors:
        logger.error("BigQuery load job completed with errors:")
        for err in load_job.errors:
            logger.error("  %s", err)
    loaded = load_job.output_rows
    logger.info(
        "BQ load: file %d batch %d loaded %d rows",
        file_idx,
        batch_idx,
        loaded,
    )
    if loaded != rows_in_batch:
        logger.warning(
            "Row count mismatch in file %d batch %d: prepared %d, BigQuery loaded %d",
            file_idx,
            batch_idx,
            rows_in_batch,
            loaded,
        )
    return loaded


def _load_one_file(
    *,
    client,
    ndjson_path: Path,
    file_idx: int,
    table_ref: str,
    schema,
    parser: Callable[[str], dict | None],
    write_disposition,
    batch_max_bytes: int = _DEFAULT_LOAD_BATCH_BYTES,
) -> tuple[int, int]:
    """Stream-transform one NDJSON file into BigQuery as one or more load jobs.

    A single source NDJSON can be ~2 GB (one chunk's worth of EN NS0
    article HTML). Submitting that as one load job blocks the operator
    on a silent multi-minute ``job.result()`` poll. Splitting it into
    ``batch_max_bytes``-sized pieces gives a visible log line per batch
    and shrinks the retry atom to a few minutes' work.

    The first batch uses ``write_disposition``; subsequent batches always
    WRITE_APPEND so a single source file isn't repeatedly truncating
    away its own previously-loaded rows.

    Returns ``(rows_loaded, rows_skipped)`` aggregated across all batches.
    """
    from google.cloud import bigquery

    logger.info("Preparing NDJSON file %d: %s", file_idx, ndjson_path)

    skipped = 0
    total_loaded = 0
    batch_idx = 0

    with open(ndjson_path, encoding="utf-8") as src:
        while True:
            # ``delete=False`` keeps the file alive after the ``with``
            # block exits so the load job can re-open it for reading.
            # Cleanup happens in the ``finally`` below.
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".ndjson", delete=False, encoding="utf-8"
            ) as tmp:
                tmp_path = Path(tmp.name)
                rows_in_batch = 0
                bytes_in_batch = 0
                for raw_line in src:
                    line = raw_line.strip()
                    if not line:
                        continue
                    row = parser(line)
                    if row is None:
                        skipped += 1
                        continue
                    payload = json.dumps(row) + "\n"
                    tmp.write(payload)
                    bytes_in_batch += len(payload.encode("utf-8"))
                    rows_in_batch += 1
                    if bytes_in_batch >= batch_max_bytes:
                        break
            try:
                if rows_in_batch == 0:
                    if batch_idx == 0:
                        logger.warning(
                            "File %d produced 0 rows after parsing; skipping load job",
                            file_idx,
                        )
                    return total_loaded, skipped

                batch_idx += 1
                disposition = (
                    write_disposition if batch_idx == 1 else bigquery.WriteDisposition.WRITE_APPEND
                )
                total_loaded += _submit_batch_load_job(
                    client=client,
                    table_ref=table_ref,
                    batch_path=tmp_path,
                    schema=schema,
                    write_disposition=disposition,
                    file_idx=file_idx,
                    batch_idx=batch_idx,
                    rows_in_batch=rows_in_batch,
                    bytes_in_batch=bytes_in_batch,
                )

                if bytes_in_batch < batch_max_bytes:
                    # Inner loop ended due to source exhaustion, not size cap.
                    return total_loaded, skipped
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()


def load_tarball_to_bigquery(
    tarball_path: Path,
    *,
    project: str,
    dataset: str,
    ns: NamespaceConfig,
    credentials_path: str | None = None,
    use_streaming_insert: bool = False,
    batch_size: int = 10_000,
) -> tuple[int, int]:
    """Stream-extract a tarball into BigQuery, one NDJSON file at a time.

    Caps local disk usage at "tarball + at most one extracted NDJSON" — the
    iterator deletes each NDJSON immediately after the load job (or streaming
    batch) for it has finished.

    Returns ``(rows_loaded, rows_skipped)``.
    """
    from google.cloud import bigquery

    from mwlib.network.bigquery_lookup import _validate_bigquery_identifier

    client = _make_bq_client(project, credentials_path)
    # ``project`` and ``dataset`` come from CLI flags / env vars and end
    # up interpolated into the raw ``TRUNCATE TABLE`` statement below.
    # BigQuery identifiers can't be passed as query parameters, so
    # validate them here exactly like ``BigQueryImageLookup._execute_query``
    # does at runtime — a backtick in either value would otherwise close
    # ``table_ref`` early.
    safe_project = _validate_bigquery_identifier(project, "project")
    safe_dataset = _validate_bigquery_identifier(dataset, "dataset")
    safe_table = _validate_bigquery_identifier(ns.table_id, "table")
    table_ref = f"{safe_project}.{safe_dataset}.{safe_table}"
    _prepare_table(client, table_ref, ns)

    schema = None
    if use_streaming_insert:
        # Streaming inserts append, so for externally managed tables we must
        # explicitly clear the previous run's data first. ``_prepare_table``
        # already truncated implicitly for script-managed tables (drop+create),
        # so the TRUNCATE here is only needed for the Pulumi-managed case.
        if not ns.script_manages_table:
            logger.info("Truncating %s before streaming inserts", table_ref)
            client.query(f"TRUNCATE TABLE `{table_ref}`").result()
    else:
        schema = _make_bq_schema(ns.schema)

    total_loaded = 0
    total_skipped = 0
    file_idx = 0

    for ndjson_path in iter_extract_ndjson(tarball_path):
        file_idx += 1
        if use_streaming_insert:
            loaded, skipped = _stream_one_file(
                client=client,
                table_ref=table_ref,
                ndjson_path=ndjson_path,
                parser=ns.parser,
                batch_size=batch_size,
            )
        else:
            write_disposition = (
                bigquery.WriteDisposition.WRITE_TRUNCATE
                if file_idx == 1
                else bigquery.WriteDisposition.WRITE_APPEND
            )
            loaded, skipped = _load_one_file(
                client=client,
                ndjson_path=ndjson_path,
                file_idx=file_idx,
                table_ref=table_ref,
                schema=schema,
                parser=ns.parser,
                write_disposition=write_disposition,
            )
        total_loaded += loaded
        total_skipped += skipped

    logger.info(
        "Load complete: %d rows loaded across %d files (%d skipped)",
        total_loaded,
        file_idx,
        total_skipped,
    )
    return total_loaded, total_skipped


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Fetch a Wikimedia Enterprise namespace snapshot and load it into BigQuery."),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available snapshots and exit",
    )
    parser.add_argument(
        "--namespace",
        type=int,
        choices=sorted(NAMESPACES),
        default=6,
        help=(
            "Wikipedia namespace to sync. 6 = file description pages "
            "(file_pages table). 0 = article HTML (article_pages table). "
            "Default: 6."
        ),
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download the snapshot but skip BigQuery loading",
    )
    parser.add_argument(
        "--keep-tarball",
        action="store_true",
        help=(
            "Keep the downloaded tarball after BigQuery loading completes "
            "(default: delete to free disk)."
        ),
    )
    parser.add_argument(
        "--streaming-insert",
        action="store_true",
        help="Use BigQuery streaming inserts instead of the default batch load job",
    )
    parser.add_argument(
        "--snapshot-id",
        default=None,
        help=(
            "Snapshot identifier override. Defaults to the namespace-derived "
            "snapshot (enwiki_namespace_6 / enwiki_namespace_0)."
        ),
    )
    parser.add_argument(
        "-i",
        "--input",
        help="Path to an already-downloaded .tar.gz file (skips download)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output path for the downloaded tarball (default: auto-generated in /tmp)",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("BIGQUERY_PROJECT", "pediapress-prod"),
        help="Google Cloud project ID (default: BIGQUERY_PROJECT env or 'pediapress-prod')",
    )
    parser.add_argument(
        "--dataset",
        default=os.environ.get("BIGQUERY_DATASET", "wikipedia"),
        help="BigQuery dataset ID (default: BIGQUERY_DATASET env or 'wikipedia')",
    )
    parser.add_argument(
        "--credentials",
        default=(
            os.environ.get("BIGQUERY_CREDENTIALS")
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        ),
        help=(
            "Path to GCP service account JSON. Defaults to BIGQUERY_CREDENTIALS "
            "if set, otherwise GOOGLE_APPLICATION_CREDENTIALS — same precedence "
            "the runtime BigQuery lookup uses, so a worker mounting a dedicated "
            "BigQuery SA at /run/secrets/bigquery_credentials gets used by the "
            "ingest CLI without an explicit --credentials flag."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10_000,
        help="Rows per batch for streaming inserts (default: 10000)",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help=(
            "Path to the chunked-ingest state file (default: auto under "
            "the system temp dir, keyed by snapshot id). Resume picks up "
            "from this file; --fresh ignores it."
        ),
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "Ignore any existing state file and start a new run from "
            "chunk 0 (truncates the destination table). Required when "
            "WME has re-issued the snapshot since the previous run."
        ),
    )
    parser.add_argument(
        "--no-chunked",
        action="store_true",
        help=(
            "Disable the chunked-ingest path even if the snapshot exposes "
            "/chunks; falls back to downloading a single tarball via the "
            "legacy /download endpoint. Provided as an escape hatch — "
            "note that for snapshots WME has split (notably EN NS0), the "
            "single-tarball path returns only the first group and "
            "produces an *incomplete* table."
        ),
    )
    parser.add_argument(
        "--chunk-work-dir",
        default=None,
        help=(
            "Working directory for downloaded chunks (default: a fresh "
            "tempdir per run). Each chunk is unlinked after its load "
            "finishes; peak disk is ~1 chunk (~300 MB)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int | None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    ns = NAMESPACES[args.namespace]
    snapshot_id = args.snapshot_id or ns.snapshot_id

    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("Loaded environment from %s", env_path)
    except ImportError:
        pass

    # Operator-supplied tarball (--input) bypasses both the chunked path
    # and the network entirely.
    if args.input:
        tarball_path = Path(args.input)
        if not tarball_path.exists():
            logger.error("Input file not found: %s", tarball_path)
            sys.exit(1)
        logger.info("Using existing tarball: %s", tarball_path)

        loaded, skipped = load_tarball_to_bigquery(
            tarball_path,
            project=args.project,
            dataset=args.dataset,
            ns=ns,
            credentials_path=args.credentials,
            use_streaming_insert=args.streaming_insert,
            batch_size=args.batch_size,
        )
        logger.info(
            "Done! %d rows loaded into %s.%s.%s (%d rows skipped)",
            loaded,
            args.project,
            args.dataset,
            ns.table_id,
            skipped,
        )
        return None

    username = os.environ.get("WME_USERNAME")
    password = os.environ.get("WME_PASSWORD")
    if not username or not password:
        logger.error("WME_USERNAME and WME_PASSWORD environment variables are required")
        sys.exit(1)

    token = get_bearer_token(username, password)

    if args.list:
        snapshots = list_snapshots(token)
        print(json.dumps(snapshots, indent=2))
        return None

    # Try the chunked path first unless the operator has explicitly disabled
    # it. Snapshots without a chunks endpoint fall through to the legacy
    # single-tarball path. Important: for EN NS0 the chunks endpoint
    # *exists* and is the only complete listing — the legacy /download
    # silently returns just the first chunk-group (~70% of the data).
    chunks: list[dict] = []
    if not args.no_chunked:
        chunks = list_chunks(token, snapshot_id)
        logger.info(
            "Snapshot %s exposes %d chunks via /chunks API",
            snapshot_id,
            len(chunks),
        )

    if chunks:
        if args.download_only:
            logger.warning(
                "--download-only is a no-op for chunked ingest (chunks are "
                "downloaded just-in-time and unlinked after their load); "
                "use --no-chunked --download-only to fetch the legacy "
                "single tarball instead."
            )
            return None

        state_path = Path(args.state_file) if args.state_file else _default_state_path(snapshot_id)
        work_dir = Path(args.chunk_work_dir) if args.chunk_work_dir else None
        loaded, skipped = load_chunked_to_bigquery(
            token=token,
            chunks=chunks,
            project=args.project,
            dataset=args.dataset,
            ns=ns,
            credentials_path=args.credentials,
            state_path=state_path,
            fresh=args.fresh,
            work_dir=work_dir,
            use_streaming_insert=args.streaming_insert,
            batch_size=args.batch_size,
        )
        logger.info(
            "Done! %d rows loaded into %s.%s.%s (%d rows skipped)",
            loaded,
            args.project,
            args.dataset,
            ns.table_id,
            skipped,
        )
        return None

    # Legacy single-tarball path. Reached only when --no-chunked is set or
    # the snapshot's /chunks endpoint returned nothing.
    if args.output:
        tarball_path = Path(args.output)
    else:
        tarball_path = Path(tempfile.mkdtemp()) / f"{snapshot_id}.tar.gz"

    download_snapshot_streaming(token, snapshot_id, tarball_path)
    downloaded_here = True

    if args.download_only:
        logger.info("Download-only mode. Tarball saved to: %s", tarball_path)
        return None

    try:
        loaded, skipped = load_tarball_to_bigquery(
            tarball_path,
            project=args.project,
            dataset=args.dataset,
            ns=ns,
            credentials_path=args.credentials,
            use_streaming_insert=args.streaming_insert,
            batch_size=args.batch_size,
        )
    finally:
        if downloaded_here and not args.keep_tarball and tarball_path.exists():
            try:
                tarball_path.unlink()
                logger.info("Removed downloaded tarball: %s", tarball_path)
            except OSError:
                logger.exception("Failed to remove tarball %s", tarball_path)

    logger.info(
        "Done! %d rows loaded into %s.%s.%s (%d rows skipped)",
        loaded,
        args.project,
        args.dataset,
        ns.table_id,
        skipped,
    )
    return None


if __name__ == "__main__":
    main()
