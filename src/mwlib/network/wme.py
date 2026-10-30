"""Minimal Wikimedia Enterprise client for downloading snapshot chunks.

Auth, ``/chunks`` listing and one whole-file GET per chunk with retry, plus
the parser for NS6 (file description page) records. Used by
``mwlib.apps.file_store_builder``.
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading
import time
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

WME_AUTH_URL = "https://auth.enterprise.wikimedia.com/v1/login"
WME_API_BASE = "https://api.enterprise.wikimedia.com/v2"
NS6_SNAPSHOT_ID = "enwiki_namespace_6"

# (connect, read) seconds. Chunks are ~300 MB; the read timeout is per
# socket read, so it only trips when the stream has clearly stalled.
_HTTP_TIMEOUT = (30, 300)
_DOWNLOAD_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 10
# WME access tokens outlive this by a wide margin; refreshing early keeps a
# multi-hour build from ever presenting an expired one.
_TOKEN_MAX_AGE_SECONDS = 30 * 60


class WmeClient:
    def __init__(self, username: str, password: str, snapshot_id: str = NS6_SNAPSHOT_ID):
        self._username = username
        self._password = password
        self.snapshot_id = snapshot_id
        self._token: str | None = None
        self._token_time = 0.0
        self._lock = threading.Lock()

    def _get_token(self) -> str:
        with self._lock:
            if self._token is None or time.monotonic() - self._token_time > _TOKEN_MAX_AGE_SECONDS:
                resp = requests.post(
                    WME_AUTH_URL,
                    json={"username": self._username, "password": self._password},
                    timeout=30,
                )
                resp.raise_for_status()
                self._token = resp.json()["access_token"]
                self._token_time = time.monotonic()
            return self._token

    def list_chunks(self) -> list[dict]:
        """Chunk metadata (``identifier``, ``version``, ``size``, ...) for the snapshot."""
        resp = requests.get(
            f"{WME_API_BASE}/snapshots/{self.snapshot_id}/chunks",
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list):
            # Surface the real shape instead of a misleading "no chunks" later.
            keys = sorted(payload) if isinstance(payload, dict) else None
            raise RuntimeError(
                f"unexpected /chunks payload for {self.snapshot_id}: "
                f"{type(payload).__name__} (keys: {keys})"
            )
        return payload

    def download_chunk(self, chunk: dict, dest: Path) -> None:
        """Download one chunk to ``dest``; whole-file retry on failure."""
        chunk_id = chunk["identifier"]
        url = f"{WME_API_BASE}/snapshots/{self.snapshot_id}/chunks/{chunk_id}/download"
        for attempt in range(1, _DOWNLOAD_RETRIES + 1):
            try:
                with requests.get(
                    url,
                    # A chunk is already a gzip/tar.gz file: ask for it untouched and
                    # read the raw stream, so received bytes are comparable to
                    # Content-Length even if a proxy adds Content-Encoding.
                    headers={
                        "Authorization": f"Bearer {self._get_token()}",
                        "Accept-Encoding": "identity",
                    },
                    stream=True,
                    timeout=_HTTP_TIMEOUT,
                ) as resp:
                    resp.raise_for_status()
                    expected = int(resp.headers.get("content-length", 0))
                    received = 0
                    with open(dest, "wb") as f:
                        for piece in resp.raw.stream(8 * 1024 * 1024, decode_content=False):
                            f.write(piece)
                            received += len(piece)
                    if expected and received != expected:
                        raise OSError(
                            f"chunk {chunk_id}: short read ({received} of {expected} bytes)"
                        )
                return
            except (requests.RequestException, OSError) as exc:
                with contextlib.suppress(OSError):
                    dest.unlink()
                if attempt == _DOWNLOAD_RETRIES:
                    raise
                wait = _RETRY_BACKOFF_SECONDS * 3 ** (attempt - 1)
                logger.warning(
                    "chunk %s attempt %d/%d failed: %s; retrying in %ds",
                    chunk_id,
                    attempt,
                    _DOWNLOAD_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)


def _revision_id(doc: dict) -> int | None:
    version = doc.get("version")
    revision = version.get("identifier") if isinstance(version, dict) else None
    # bool is an int subclass; a malformed ``true`` must not rank as revision 1.
    if isinstance(revision, bool) or not isinstance(revision, int):
        return None
    return revision


def parse_ns6_line(line: str) -> dict | None:
    """Parse one NS6 (file description page) NDJSON line into a store row.

    Returns ``None`` for malformed lines and records without a name.
    ``license`` / ``templates`` / ``categories`` are kept as JSON text, or
    ``None`` when absent or empty.
    """
    try:
        doc = json.loads(line)
    except json.JSONDecodeError:
        logger.warning("Skipping malformed JSON line: %s...", line[:100])
        return None
    if not isinstance(doc, dict) or not doc.get("name"):
        return None

    image = doc.get("image") if isinstance(doc.get("image"), dict) else {}
    row = {
        # Stored with spaces (the canonical form) so lookups can match on one key.
        "name": doc["name"].replace("_", " "),
        "identifier": doc.get("identifier"),
        "date_modified": doc.get("date_modified"),
        "version_identifier": _revision_id(doc),
        "url": doc.get("url"),
        "image_content_url": image.get("content_url"),
        "image_width": image.get("width"),
        "image_height": image.get("height"),
    }
    for key in ("license", "templates", "categories"):
        row[key] = json.dumps(doc[key]) if doc.get(key) else None
    return row
