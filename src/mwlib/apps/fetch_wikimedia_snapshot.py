#!/usr/bin/env python3
"""Fetch Wikimedia Enterprise namespace 6 snapshot and load into BigQuery.

Authentication:
    Uses WME_USERNAME / WME_PASSWORD env vars to obtain a bearer token from
    the Wikimedia Enterprise auth endpoint.

BigQuery:
    Uses GOOGLE_APPLICATION_CREDENTIALS (or the service account JSON path
    passed via --credentials) for authentication.

Data handling:
    Each run replaces all data in the target table (WRITE_TRUNCATE / drop+create).
    This is intentional for snapshot ETL — no upsert logic is needed.

Usage examples:
    # List available snapshots
    python fetch_wikimedia_snapshot.py --list

    # Download namespace 6 snapshot only (no BigQuery load)
    python fetch_wikimedia_snapshot.py --download-only -o enwiki_ns6.tar.gz

    # Full pipeline: download + load into BigQuery (default: batch load job)
    python fetch_wikimedia_snapshot.py --project pediapress-prod --dataset wikipedia

    # Load from an already-downloaded tarball (skip download)
    python fetch_wikimedia_snapshot.py -i /path/to/enwiki_ns6.tar.gz

    # Use streaming inserts instead of batch load job
    python fetch_wikimedia_snapshot.py --streaming-insert --project pediapress-prod
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

WME_AUTH_URL = "https://auth.enterprise.wikimedia.com/v1/login"
WME_API_BASE = "https://api.enterprise.wikimedia.com/v2"
DEFAULT_SNAPSHOT_ID = "enwiki_namespace_6"

# BigQuery schema for the namespace 6 file description pages.
# Focused on fields needed for license checking. article_body_html is omitted
# to avoid storage bloat — templates and categories cover license-checking needs.
BQ_TABLE_ID = "file_pages"
BQ_SCHEMA = [
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

# Progress logging interval (bytes) during download
_DOWNLOAD_LOG_INTERVAL = 100 * 1024 * 1024  # log every 100 MB


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
    logger.info(
        "Authentication successful (token expires in %ss)", data.get("expires_in")
    )
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
    logger.info(
        "Downloading snapshot %s to %s (streaming)...", snapshot_id, output_path
    )

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
                    logger.info(
                        "  %.1f%% (%d / %d MB)", pct, downloaded >> 20, total >> 20
                    )
                else:
                    logger.info("  %d MB downloaded", downloaded >> 20)
                last_logged = downloaded

    # Verify completeness
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


def extract_ndjson_from_tarball(tarball_path: Path) -> list[Path]:
    """Extract all .ndjson files from a gzipped tarball.

    Returns a list of paths to the extracted NDJSON files.
    """
    logger.info("Extracting NDJSON files from %s...", tarball_path)
    extract_dir = tarball_path.parent

    with tarfile.open(tarball_path, "r:gz") as tar:
        ndjson_members = [m for m in tar.getmembers() if m.name.endswith(".ndjson")]
        if not ndjson_members:
            raise ValueError(f"No .ndjson files found in {tarball_path}")

        # Path traversal guard
        for m in ndjson_members:
            if Path(m.name).is_absolute() or ".." in Path(m.name).parts:
                raise ValueError(f"Suspicious tar member path: {m.name}")

        extracted = []
        for member in ndjson_members:
            tar.extract(member, path=extract_dir)
            path = extract_dir / member.name
            logger.info("Extracted: %s (%d bytes)", path, member.size)
            extracted.append(path)

        logger.info("Extracted %d NDJSON files", len(extracted))
        return extracted


def parse_ndjson_row(line: str) -> dict | None:
    """Parse a single NDJSON line into a BigQuery-compatible row."""
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

    # Extract image metadata
    image = doc.get("image")
    if image and isinstance(image, dict):
        row["image_content_url"] = image.get("content_url")
        row["image_width"] = image.get("width")
        row["image_height"] = image.get("height")

    return row


def _make_bq_client(project: str, credentials_path: str | None):
    """Create a BigQuery client with optional service account credentials."""
    from google.cloud import bigquery
    from google.oauth2 import service_account

    if credentials_path:
        creds = service_account.Credentials.from_service_account_file(credentials_path)
        return bigquery.Client(project=project, credentials=creds)
    return bigquery.Client(project=project)


def _make_bq_schema():
    """Build a list of BigQuery SchemaField objects from BQ_SCHEMA."""
    from google.cloud import bigquery

    return [
        bigquery.SchemaField(
            name=f["name"],
            field_type=f["type"],
            mode=f["mode"],
            description=f.get("description", ""),
        )
        for f in BQ_SCHEMA
    ]


def load_ndjson_to_bigquery_streaming(
    ndjson_paths: list[Path],
    project: str,
    dataset: str,
    credentials_path: str | None = None,
    batch_size: int = 10_000,
) -> int:
    """Load parsed NDJSON rows into BigQuery using the streaming insert API.

    Processes all NDJSON files in order. Failed rows are retried once.

    Returns the total number of rows successfully loaded.
    """
    client = _make_bq_client(project, credentials_path)
    table_ref = f"{project}.{dataset}.{BQ_TABLE_ID}"

    schema = _make_bq_schema()
    from google.cloud import bigquery

    table = bigquery.Table(table_ref, schema=schema)
    client.delete_table(table_ref, not_found_ok=True)
    client.create_table(table)
    logger.info("Created BigQuery table %s", table_ref)

    total_rows = 0
    skipped_rows = 0
    errors_total = 0

    for file_idx, ndjson_path in enumerate(ndjson_paths, 1):
        logger.info(
            "Processing file %d/%d: %s", file_idx, len(ndjson_paths), ndjson_path
        )
        batch = []

        with open(ndjson_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                row = parse_ndjson_row(line)
                if row is None:
                    skipped_rows += 1
                    continue

                batch.append(row)

                if len(batch) >= batch_size:
                    inserted, failed = _insert_batch_with_retry(
                        client, table_ref, batch
                    )
                    total_rows += inserted
                    errors_total += failed
                    logger.info(
                        "Loaded %d rows (%d total, %d errors so far)...",
                        inserted,
                        total_rows,
                        errors_total,
                    )
                    batch = []

        # Final batch for this file
        if batch:
            inserted, failed = _insert_batch_with_retry(client, table_ref, batch)
            total_rows += inserted
            errors_total += failed

    logger.info(
        "Load complete: %d rows loaded from %d files, %d errors, %d skipped",
        total_rows,
        len(ndjson_paths),
        errors_total,
        skipped_rows,
    )
    if errors_total > 0:
        logger.error(
            "WARNING: %d rows failed to insert. The table may be incomplete.",
            errors_total,
        )
    return total_rows


def _insert_batch_with_retry(
    client, table_ref: str, batch: list[dict]
) -> tuple[int, int]:
    """Insert a batch of rows, retrying failed rows once.

    Returns (inserted_count, failed_count).
    """
    errors = client.insert_rows_json(table_ref, batch)
    if not errors:
        return len(batch), 0

    # Identify which rows failed
    failed_indices = set()
    for err in errors:
        idx = err.get("index")
        if idx is not None:
            failed_indices.add(idx)
        for detail in err.get("errors", []):
            logger.warning("  Insert error: %s", detail)

    if not failed_indices:
        # Can't determine which rows failed — count all as failed
        logger.warning("Insert returned %d errors but no row indices", len(errors))
        return 0, len(batch)

    succeeded = len(batch) - len(failed_indices)

    # Retry failed rows once
    retry_batch = [batch[i] for i in sorted(failed_indices)]
    logger.info("Retrying %d failed rows...", len(retry_batch))
    retry_errors = client.insert_rows_json(table_ref, retry_batch)
    if not retry_errors:
        return len(batch), 0

    # Log permanently failed rows
    permanent_failures = len(retry_errors)
    for err in retry_errors[:3]:
        logger.error("Permanent insert failure: %s", err)

    return succeeded + (len(retry_batch) - permanent_failures), permanent_failures


def load_ndjson_to_bigquery_load_job(
    ndjson_paths: list[Path],
    project: str,
    dataset: str,
    credentials_path: str | None = None,
) -> int:
    """Load NDJSON into BigQuery using a load job (better for large files).

    Reads all NDJSON files, converts each line to our schema, writes to a
    single temporary file, then uses a BigQuery load job with WRITE_TRUNCATE.

    Returns the total number of rows loaded.
    """
    from google.cloud import bigquery

    client = _make_bq_client(project, credentials_path)
    table_ref = f"{project}.{dataset}.{BQ_TABLE_ID}"
    schema = _make_bq_schema()

    # Write transformed rows from ALL files to a single temp NDJSON file
    tmp_path = None
    skipped_rows = 0
    try:
        total_rows = 0
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ndjson", delete=False
        ) as tmp:
            tmp_path = tmp.name
            for file_idx, ndjson_path in enumerate(ndjson_paths, 1):
                logger.info(
                    "Preparing file %d/%d: %s",
                    file_idx,
                    len(ndjson_paths),
                    ndjson_path,
                )
                with open(ndjson_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        row = parse_ndjson_row(line)
                        if row is None:
                            skipped_rows += 1
                            continue
                        tmp.write(json.dumps(row) + "\n")
                        total_rows += 1

        logger.info(
            "Prepared %d rows from %d files for BigQuery load job (%d skipped)",
            total_rows,
            len(ndjson_paths),
            skipped_rows,
        )

        # Configure load job
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            max_bad_records=0,  # Fail on any bad record
        )

        with open(tmp_path, "rb") as source:
            load_job = client.load_table_from_file(
                source,
                table_ref,
                job_config=job_config,
            )

        logger.info("BigQuery load job started: %s", load_job.job_id)
        load_job.result()  # Wait for completion

        # Check for errors in the load job
        if load_job.errors:
            logger.error("BigQuery load job completed with errors:")
            for err in load_job.errors:
                logger.error("  %s", err)

        loaded = load_job.output_rows
        logger.info("BigQuery load job completed: %d rows loaded", loaded)

        if loaded != total_rows:
            logger.warning(
                "Row count mismatch: prepared %d rows but BigQuery loaded %d. "
                "%d rows may have been rejected.",
                total_rows,
                loaded,
                total_rows - loaded,
            )

        return loaded

    finally:
        if tmp_path and Path(tmp_path).exists():
            os.unlink(tmp_path)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Wikimedia Enterprise namespace 6 snapshot and load into BigQuery.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available snapshots and exit",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download the snapshot but skip BigQuery loading",
    )
    parser.add_argument(
        "--streaming-insert",
        action="store_true",
        help="Use BigQuery streaming inserts instead of the default batch load job",
    )
    parser.add_argument(
        "--snapshot-id",
        default=DEFAULT_SNAPSHOT_ID,
        help=f"Snapshot identifier (default: {DEFAULT_SNAPSHOT_ID})",
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

    args = parser.parse_args()

    # Load .env if present
    try:
        from dotenv import load_dotenv

        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("Loaded environment from %s", env_path)
    except ImportError:
        pass

    # Use existing tarball or download a new one
    if args.input:
        output_path = Path(args.input)
        if not output_path.exists():
            logger.error("Input file not found: %s", output_path)
            sys.exit(1)
        logger.info("Using existing tarball: %s", output_path)
    else:
        # Authenticate with Wikimedia Enterprise
        username = os.environ.get("WME_USERNAME")
        password = os.environ.get("WME_PASSWORD")
        if not username or not password:
            logger.error(
                "WME_USERNAME and WME_PASSWORD environment variables are required"
            )
            sys.exit(1)

        token = get_bearer_token(username, password)

        # --list mode
        if args.list:
            snapshots = list_snapshots(token)
            print(json.dumps(snapshots, indent=2))
            return

        # Download snapshot
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = Path(tempfile.mkdtemp()) / f"{args.snapshot_id}.tar.gz"

        download_snapshot_streaming(token, args.snapshot_id, output_path)

        if args.download_only:
            logger.info("Download-only mode. Tarball saved to: %s", output_path)
            return

    # Extract all NDJSON files
    ndjson_paths = extract_ndjson_from_tarball(output_path)

    # Count lines across all NDJSON files for reference
    line_count = 0
    for ndjson_path in ndjson_paths:
        with open(ndjson_path, encoding="utf-8") as f:
            file_lines = sum(1 for line in f if line.strip())
        logger.info("  %s: %d non-empty lines", ndjson_path.name, file_lines)
        line_count += file_lines
    logger.info(
        "Total: %d non-empty lines across %d files", line_count, len(ndjson_paths)
    )

    # Load into BigQuery (default: batch load job, optional: streaming inserts)
    if args.streaming_insert:
        total = load_ndjson_to_bigquery_streaming(
            ndjson_paths,
            project=args.project,
            dataset=args.dataset,
            credentials_path=args.credentials,
            batch_size=args.batch_size,
        )
    else:
        total = load_ndjson_to_bigquery_load_job(
            ndjson_paths,
            project=args.project,
            dataset=args.dataset,
            credentials_path=args.credentials,
        )

    logger.info(
        "Done! %d rows loaded into %s.%s.%s (from %d NDJSON lines in %d files)",
        total,
        args.project,
        args.dataset,
        BQ_TABLE_ID,
        line_count,
        len(ndjson_paths),
    )

    if total < line_count:
        logger.warning(
            "INCOMPLETE: only %d of %d lines were loaded. "
            "Check logs above for parse errors or BigQuery insert failures.",
            total,
            line_count,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
