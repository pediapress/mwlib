"""BigQuery-first lookup for image description page data.

Queries pre-extracted page metadata (templates, license, dimensions) from BigQuery
instead of fetching from the remote MediaWiki API. Used for configured domains
(default: en.wikipedia.org) where WME snapshot data is available.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mwlib.utils._conf import ConfMod

logger = logging.getLogger(__name__)


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

        domains_str = conf.get("bigquery", "domains", "en.wikipedia.org")
        self.domains = {d.strip() for d in domains_str.split(",") if d.strip()}

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
        """Check if the given URL path matches a configured BigQuery domain."""
        return any(domain in path for domain in self.domains)

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

        table_ref = f"`{self.project}.{self.dataset}.{self.table}`"
        query = f"""
            SELECT name, identifier, url, license, templates, categories,
                   abstract, image_content_url, image_width, image_height
            FROM {table_ref}
            WHERE name IN UNNEST(@titles)
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("titles", "STRING", titles),
            ],
        )

        logger.info("BigQuery query: %s", query.strip())
        logger.info("BigQuery table: %s, titles: %r", table_ref, titles)

        query_job = self._client.query(query, job_config=job_config, timeout=self.timeout)
        results = query_job.result(timeout=self.timeout)

        rows = []
        found_titles = set()
        for row in results:
            row_dict = dict(row)
            rows.append(row_dict)
            found_titles.add(row_dict["name"])

        missing = [t for t in titles if t not in found_titles]

        logger.info(
            "BigQuery lookup: %d found, %d missing out of %d requested",
            len(rows),
            len(missing),
            len(titles),
        )

        return rows, missing
