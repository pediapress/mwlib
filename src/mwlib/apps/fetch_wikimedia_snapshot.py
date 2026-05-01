#!/usr/bin/env python3
"""Fetch Wikimedia Enterprise namespace snapshots and load them into BigQuery.

Authentication:
    Uses WME_USERNAME / WME_PASSWORD env vars to obtain a bearer token from
    the Wikimedia Enterprise auth endpoint.

BigQuery:
    Uses GOOGLE_APPLICATION_CREDENTIALS (or the service account JSON path
    passed via --credentials) for authentication.

Namespaces:
    --namespace 6 (default): NS6 file description pages → ``file_pages`` table.
        Schema captures dimensions, license, templates, and categories — the
        fields needed to surface cover candidates and check print eligibility.
    --namespace 0: NS0 article HTML → ``article_pages`` table. Lean schema
        (name, identifier, article_body_html, date_modified) sized to keep
        BigQuery storage cost in line with what the page-count estimator
        actually consumes. The table is provisioned by Pulumi (clustered on
        ``name``) — this script never drops or recreates it.

Disk usage:
    NS0 EN ships as multiple multi-GB NDJSON chunks inside one tarball. Local
    disk is capped at "tarball + one extracted NDJSON" by extracting members
    just-in-time and deleting each one after BigQuery has loaded it. Without
    this, peak disk would be roughly 2× the tarball size.

Data handling:
    Each run replaces all data in the target table. The default load-job mode
    submits one BigQuery load job per NDJSON file (WRITE_TRUNCATE on the first,
    WRITE_APPEND afterwards) so a single multi-hundred-GB intermediate file is
    never required. Streaming insert mode is preserved for operators who need
    it but is significantly more expensive at scale.

Usage examples:
    # List available snapshots
    python fetch_wikimedia_snapshot.py --list

    # Default: download + load NS6 (file_pages)
    python fetch_wikimedia_snapshot.py --project pediapress-prod --dataset wikipedia

    # Download + load NS0 (article_pages, EN article HTML)
    python fetch_wikimedia_snapshot.py --namespace 0 --project pediapress-prod

    # Download only — useful for inspecting a snapshot before loading
    python fetch_wikimedia_snapshot.py --namespace 0 --download-only -o enwiki_ns0.tar.gz

    # Load from an already-downloaded tarball (skip download)
    python fetch_wikimedia_snapshot.py --namespace 0 -i /path/to/enwiki_ns0.tar.gz

    # Use streaming inserts instead of batch load jobs
    python fetch_wikimedia_snapshot.py --streaming-insert --project pediapress-prod
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

WME_AUTH_URL = "https://auth.enterprise.wikimedia.com/v1/login"
WME_API_BASE = "https://api.enterprise.wikimedia.com/v2"

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
    if "license" in doc and doc["license"]:
        row["license"] = json.dumps(doc["license"])
    if "templates" in doc and doc["templates"]:
        row["templates"] = json.dumps(doc["templates"])
    if "categories" in doc and doc["categories"]:
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
    """
    extract_dir = tarball_path.parent

    with tarfile.open(tarball_path, "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.name.endswith(".ndjson")]
        if not members:
            raise ValueError(f"No .ndjson files found in {tarball_path}")
        for m in members:
            _validate_tar_member(m)

        logger.info("Tarball contains %d NDJSON files; will extract one at a time", len(members))

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


def _make_bq_client(project: str, credentials_path: str | None):
    """Create a BigQuery client with optional service account credentials."""
    from google.cloud import bigquery
    from google.oauth2 import service_account

    if credentials_path:
        creds = service_account.Credentials.from_service_account_file(credentials_path)
        return bigquery.Client(project=project, credentials=creds)
    return bigquery.Client(project=project)


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

    For script-managed namespaces (NS6) the table is recreated on every run —
    that's the long-standing behaviour and keeps schema changes effortless.
    For externally-managed tables (NS0 → Pulumi) the script never drops the
    table; it just verifies it exists. ``exists_ok=True`` makes the call a
    no-op when Pulumi has already created it, which is the production case,
    while still letting the script bootstrap a missing table in dev.
    """
    from google.cloud import bigquery

    schema = _make_bq_schema(ns.schema)
    table = bigquery.Table(table_ref, schema=schema)

    if ns.script_manages_table:
        client.delete_table(table_ref, not_found_ok=True)
        client.create_table(table)
        logger.info("Created BigQuery table %s", table_ref)
    else:
        client.create_table(table, exists_ok=True)
        logger.info("Using BigQuery table %s (managed externally)", table_ref)


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
        for line in f:
            line = line.strip()
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


def _load_one_file(
    *,
    client,
    ndjson_path: Path,
    file_idx: int,
    table_ref: str,
    schema,
    parser: Callable[[str], dict | None],
    write_disposition,
) -> tuple[int, int]:
    """Stream-transform one NDJSON file and submit it as a single load job.

    Returns (rows_loaded, rows_skipped).
    """
    from google.cloud import bigquery

    logger.info("Preparing NDJSON file %d: %s", file_idx, ndjson_path)

    tmp_path = None
    try:
        prepared = 0
        skipped = 0
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as tmp:
            tmp_path = tmp.name
            with open(ndjson_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = parser(line)
                    if row is None:
                        skipped += 1
                        continue
                    tmp.write(json.dumps(row) + "\n")
                    prepared += 1

        if prepared == 0:
            logger.warning("File %d produced 0 rows after parsing; skipping load job", file_idx)
            return 0, skipped

        job_config = bigquery.LoadJobConfig(
            schema=schema,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=write_disposition,
            max_bad_records=0,
        )

        with open(tmp_path, "rb") as source:
            load_job = client.load_table_from_file(
                source,
                table_ref,
                job_config=job_config,
            )

        logger.info(
            "BigQuery load job started for file %d: %s (%d rows prepared)",
            file_idx,
            load_job.job_id,
            prepared,
        )
        load_job.result()

        if load_job.errors:
            logger.error("BigQuery load job completed with errors:")
            for err in load_job.errors:
                logger.error("  %s", err)

        loaded = load_job.output_rows
        logger.info(
            "Loaded %d rows from file %d (%d prepared, %d skipped)",
            loaded,
            file_idx,
            prepared,
            skipped,
        )

        if loaded != prepared:
            logger.warning(
                "Row count mismatch in file %d: prepared %d, BigQuery loaded %d",
                file_idx,
                prepared,
                loaded,
            )

        return loaded, skipped

    finally:
        if tmp_path and Path(tmp_path).exists():
            os.unlink(tmp_path)


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

    client = _make_bq_client(project, credentials_path)
    table_ref = f"{project}.{dataset}.{ns.table_id}"
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
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
        help="Path to GCP service account JSON (default: GOOGLE_APPLICATION_CREDENTIALS env)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10_000,
        help="Rows per batch for streaming inserts (default: 10000)",
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

    # The script can either reuse a tarball provided on disk or download a
    # new one from WME. ``downloaded_here`` tracks whether *this* run owns
    # the tarball — operator-supplied tarballs (-i) are never deleted.
    downloaded_here = False
    if args.input:
        tarball_path = Path(args.input)
        if not tarball_path.exists():
            logger.error("Input file not found: %s", tarball_path)
            sys.exit(1)
        logger.info("Using existing tarball: %s", tarball_path)
    else:
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
