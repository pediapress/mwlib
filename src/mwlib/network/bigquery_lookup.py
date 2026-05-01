"""BigQuery-first lookup for image description page data.

Queries pre-extracted page metadata (templates, license, dimensions) from BigQuery
instead of fetching from the remote MediaWiki API. Used for configured domains
(default: en.wikipedia.org) where WME snapshot data is available.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from mwlib.utils._conf import ConfMod

logger = logging.getLogger(__name__)

# BigQuery identifiers (project / dataset / table) cannot be passed as query
# parameters — they're interpolated into the SQL string. Validate them up front
# so a misconfigured or malicious config can't break the query or smuggle
# arbitrary SQL through ``table_ref``.
_BIGQUERY_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _validate_bigquery_identifier(value: str, label: str) -> str:
    if not value or not _BIGQUERY_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid BigQuery {label}: {value!r}")
    return value


class BigQueryImageLookup:
    """Batch lookup of image description page data from BigQuery.

    Reads configuration from the [bigquery] section:
    - project: GCP project ID (required)
    - dataset: BigQuery dataset name
    - table: BigQuery table name
    - timeout: Query timeout in seconds
    - domains: Comma-separated list of domains to handle
    """

    def __init__(self, conf: ConfMod | None = None):
        if conf is None:
            from mwlib.utils import conf

        self.project = conf.get("bigquery", "project", "")
        self.dataset = conf.get("bigquery", "dataset", "wme_snapshots")
        self.table = conf.get("bigquery", "table", "file_pages")
        self.timeout = conf.get("bigquery", "timeout", 30, int)

        # Hostnames are case-insensitive; lowercase the configured set so
        # ``EN.Wikipedia.ORG`` in config still matches ``en.wikipedia.org``
        # in a parsed URL.
        domains_str = conf.get("bigquery", "domains", "en.wikipedia.org")
        self.domains = {d.strip().lower() for d in domains_str.split(",") if d.strip()}

        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from google.cloud import bigquery

            self._client = bigquery.Client(
                project=self.project,
                # Use REST transport to avoid gRPC/gevent compatibility issues
                client_options={"api_endpoint": "https://bigquery.googleapis.com"},
            )
        except Exception:
            logger.warning("Failed to initialize BigQuery client", exc_info=True)
            self._client = None

    @property
    def is_available(self) -> bool:
        """Return True if the BigQuery client is initialized and ready."""
        return self._client is not None

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
        """Query BigQuery for image description page data.

        Args:
            titles: List of image page titles (e.g., ["File:Example.jpg", ...])

        Returns:
            Tuple of (rows, missing_titles):
            - rows: List of dicts with BigQuery row data for found titles
            - missing_titles: Titles not found in BigQuery (fall back to remote API)

        On any error, returns ([], titles) so all titles fall back to the remote API.

        """
        if not titles or not self._client:
            return [], list(titles)

        try:
            return self._execute_query(titles)
        except Exception:
            logger.warning(
                "BigQuery lookup failed for %d titles, falling back to remote API",
                len(titles),
                exc_info=True,
            )
            return [], list(titles)

    def _execute_query(self, titles: list[str]) -> tuple[list[dict], list[str]]:
        from google.cloud import bigquery

        project = _validate_bigquery_identifier(self.project, "project")
        dataset = _validate_bigquery_identifier(self.dataset, "dataset")
        table = _validate_bigquery_identifier(self.table, "table")
        table_ref = f"`{project}.{dataset}.{table}`"

        query = f"""
            SELECT name, identifier, url, license, templates, categories,
                   abstract, image_content_url, image_width, image_height
            FROM {table_ref}
            WHERE name IN UNNEST(@titles)
        """  # noqa: S608  identifiers validated above; titles bound as parameter

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("titles", "STRING", titles),
            ],
        )

        # Title batches contain user-controlled page/image names. Keep them
        # at debug level so they don't end up in production info logs.
        logger.debug("BigQuery query: %s", query.strip())
        logger.debug("BigQuery table=%s, %d titles", table_ref, len(titles))

        query_job = self._client.query(query, job_config=job_config, timeout=self.timeout)
        results = query_job.result(timeout=self.timeout)

        # Only accept rows whose name is exactly one of our requested titles.
        # A row with a normalized name (different casing, different namespace
        # prefix, …) is discarded — leaving its requested title in ``missing``
        # so the caller falls back to the remote API and any deferred state
        # keyed on the original title is still reachable.
        requested = set(titles)
        rows: list[dict] = []
        found_titles: set[str] = set()
        unexpected = 0
        for row in results:
            row_dict = dict(row)
            row_name = row_dict.get("name")
            if row_name not in requested:
                unexpected += 1
                continue
            rows.append(row_dict)
            found_titles.add(row_name)

        missing = [t for t in titles if t not in found_titles]

        if unexpected:
            logger.warning(
                "BigQuery returned %d rows with names not in the request set; "
                "those titles will be retried via the remote API",
                unexpected,
            )

        logger.info(
            "BigQuery lookup: %d found, %d missing out of %d requested",
            len(rows),
            len(missing),
            len(titles),
        )

        return rows, missing
