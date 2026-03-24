# Plan: BigQuery-first lookup for image description pages

## Context

mwlib fetches image description pages (NS 6 / `File:` pages) from the remote MediaWiki API during ZIP creation to enable license checking. For English Wikipedia this generates many API requests subject to rate limits. The Wikimedia Enterprise (WME) API provides snapshot data as NDJSON with pre-extracted fields (templates, license, image dimensions). By loading this into BigQuery, we can batch-lookup description page data locally — bypassing Wikipedia rate limits.

**Initial scope**: English Wikipedia namespace 6. Commons is not available from WME. The set of BigQuery-backed domains is fully configurable via environment variable.

**Key insight**: The BigQuery table stores pre-extracted data (templates, license info, image URL/dimensions) — not raw wikitext. This means the lookup replaces both `fetch_image_page` (wikitext fetch) and provides supplemental imageinfo, without needing to parse wikitext at render time.

## BigQuery Table Schema

```json
[
  {"name": "name",              "type": "STRING",    "mode": "REQUIRED", "description": "Page title (e.g. File:Example.jpg)"},
  {"name": "identifier",        "type": "INTEGER",   "description": "MediaWiki page ID"},
  {"name": "url",               "type": "STRING",    "description": "Full URL to the wiki page"},
  {"name": "date_modified",     "type": "TIMESTAMP", "description": "Last modification timestamp"},
  {"name": "license",           "type": "JSON",      "description": "License information array"},
  {"name": "templates",         "type": "JSON",      "description": "Templates used on the page (for license checking)"},
  {"name": "categories",        "type": "JSON",      "description": "Categories the page belongs to"},
  {"name": "abstract",          "type": "STRING",    "description": "Short description / abstract"},
  {"name": "image_content_url", "type": "STRING",    "description": "URL to the actual image file"},
  {"name": "image_width",       "type": "INTEGER",   "description": "Image width in pixels"},
  {"name": "image_height",      "type": "INTEGER",   "description": "Image height in pixels"}
]
```

## Implementation

### Step 1: Add `google-cloud-bigquery` as optional dependency

**File**: `pyproject.toml`

```toml
[dependency-groups]
bigquery = ["google-cloud-bigquery>=3.0"]
```

### Step 2: Add BigQuery + WME config defaults

**File**: `src/mwlib/utils/_conf.py` — add to `default_config` dict (line ~72)

```python
"bigquery": {
    "enabled": "false",
    "project": "",
    "dataset": "wme_snapshots",
    "table": "file_pages",
    "timeout": "30",
    "domains": "en.wikipedia.org",
},
```

All keys configurable via environment variables:

| Config key | Env var | Default | Description |
|---|---|---|---|
| `bigquery.enabled` | `MWLIB_BIGQUERY_ENABLED` | `false` | Master switch |
| `bigquery.project` | `MWLIB_BIGQUERY_PROJECT` | _(required when enabled)_ | GCP project ID |
| `bigquery.dataset` | `MWLIB_BIGQUERY_DATASET` | `wme_snapshots` | BigQuery dataset name |
| `bigquery.table` | `MWLIB_BIGQUERY_TABLE` | `file_pages` | BigQuery table name |
| `bigquery.timeout` | `MWLIB_BIGQUERY_TIMEOUT` | `30` | Query timeout in seconds |
| `bigquery.domains` | `MWLIB_BIGQUERY_DOMAINS` | `en.wikipedia.org` | Comma-separated domains to route through BigQuery |

WME credentials for ingestion: `MWLIB_WME_USERNAME`, `MWLIB_WME_PASSWORD`.

GCP auth via standard `GOOGLE_APPLICATION_CREDENTIALS` env var.

### Templates field and license checking

The `LicenseChecker` (licensechecker.py:131) calls `image_db.get_image_templates_and_args(imgname)` which returns lowercased template names matched against `wplicenses.csv`. The current `get_image_templates_and_args` (nuwiki.py:479-506) returns both:
1. **Template names** from the page (e.g., `cc-by-4.0`, `pd-old`) — extracted via `get_templates(rawtext)`
2. **Template argument names** (strings with len > 3, no spaces) — a heuristic to catch license identifiers passed as arguments (e.g. `{{Information|license=cc-by-4.0}}`)

The WME `templates` field contains template names used on the page. This covers (1) directly. For (2), the argument-name heuristic: most license templates on Commons/enwiki are standalone (e.g., `{{cc-by-4.0}}`), not passed as arguments. The WME templates list should be sufficient for the vast majority of license decisions. If edge cases arise, we can refine later.

**License checking at fetch time**: Currently licenses are only checked at render time. By moving the check to fetch time (inside `_store_bq_result` or after BigQuery results arrive), we can skip downloading images that would be filtered out anyway. The `LicenseChecker` needs templates + the license CSV — both available at fetch time. We'll instantiate a `LicenseChecker` in the `Fetcher` and use the BigQuery-provided templates to make the decision before scheduling image downloads.

### imageinfo.db compatibility

The renderer uses `imageinfo.db` only in `set_svg_default_size` (rl/writer.py:1709) to read `url` (check if SVG), `width`, and `height`. The BigQuery schema has `image_content_url`, `image_width`, `image_height` which map to these fields. However, `imageinfo.db` is primarily populated by `_extract_info_from_image` from the `fetch_imageinfo` API call — which **always runs** (it provides `thumburl` for downloads). BigQuery data only supplements via `setdefault()`, so existing API data takes priority. The BigQuery data is sufficient for any fields the API doesn't provide.

### Step 3: Add `templates.db` to FsOutput and NuWiki

The BigQuery data has pre-extracted templates — no wikitext to parse. We need a new storage channel.

**File**: `src/mwlib/network/fetch.py` — `FsOutput.__init__` (line 114)

Add `"templates"` to the storage list:
```python
for storage in ["authors", "html", "imageinfo", "templates"]:
```

This creates a `templates.db` SqliteDict where BigQuery results can write `title → json(template_list)`.

**File**: `src/mwlib/core/nuwiki.py` — `NuWiki.__init__` (after line 116)

Load `templates.db` if it exists:
```python
file_name = os.path.join(self.path, "templates.db")
self.templates = DumbJsonDB(file_name) if os.path.exists(file_name) else None
```

**File**: `src/mwlib/core/nuwiki.py` — `Adapt.get_image_templates_and_args` (line 479)

Check `templates.db` first before falling back to wikitext parsing:
```python
def get_image_templates_and_args(self, name, wikidb=None):
    # Check pre-extracted templates (from BigQuery) first
    if self.nuwiki.templates is not None:
        _, partial, fqname = self.nshandler.splitname(name, nshandling.NS_FILE)
        for lookup_name in [fqname, self.en_nshandler.get_fqname(partial, nshandling.NS_FILE)]:
            try:
                cached = self.nuwiki.templates[lookup_name]
                if cached:
                    return set(cached)
            except KeyError:
                pass

    # Existing wikitext parsing path (unchanged)
    from mwlib.parser.expander import get_templates
    page = self.get_image_description_page(name)
    ...
```

### Step 4: Create `src/mwlib/network/bigquery_lookup.py`

New module:

```python
class BigQueryImageLookup:
    def __init__(self):
        # Read project/dataset/table/timeout/domains from conf
        # Parse domains into a set for O(1) lookup
        # Lazy-import google.cloud.bigquery
        # Init Client with REST transport (create_bq_storage_client=False)
        #   to avoid gRPC/gevent compatibility issues

    @property
    def is_available(self) -> bool:
        # True if client initialized successfully

    def handles_domain(self, path: str) -> bool:
        # Check if any configured domain appears in path

    def fetch_batch(self, titles: list[str]) -> tuple[list[dict], list[str]]:
        # Parameterized query:
        #   SELECT name, identifier, url, license, templates, categories,
        #          abstract, image_content_url, image_width, image_height
        #   FROM `{project}.{dataset}.{table}`
        #   WHERE name IN UNNEST(@titles)
        #
        # Returns (rows, missing_titles):
        #   - rows: list of dicts with BigQuery row data
        #   - missing_titles: titles not found → fall through to remote API
        #
        # On ANY exception: log warning, return ([], all_titles) → full fallback
```

### Step 5: Integrate into `Fetcher` in `fetch.py`

**File**: `src/mwlib/network/fetch.py`

**Batching strategy**: `handle_new_basepath` is called via `_refcall` from `fetch_imageinfo`, and multiple `fetch_imageinfo` calls run concurrently. The same base path can trigger multiple `handle_new_basepath` calls, each with a subset of titles. To minimize BigQuery round-trips, we collect BigQuery-eligible titles into a pending list and flush them in a single query when the batch is large enough or when all tasks are draining.

**5a. Init in `__init__`** (after line ~377):
```python
self.bq_lookup = None
self._bq_pending = []              # (title, api) tuples awaiting BQ lookup
self._bq_batch_size = 50           # flush threshold
self._bq_deferred_downloads = {}   # title → thumburl, awaiting license check
if conf.get("bigquery", "enabled", False, bool):
    from mwlib.network.bigquery_lookup import BigQueryImageLookup
    try:
        self.bq_lookup = BigQueryImageLookup()
    except Exception:
        logger.warning("BigQuery lookup init failed, using remote API", exc_info=True)
```

**5b. Modify `handle_new_basepath`** (lines 965-992):

For BigQuery-eligible domains, collect titles into `_bq_pending` instead of dispatching immediately. For non-eligible domains, existing flow is unchanged.

```python
def handle_new_basepath(self, path):
    api = self._get_mwapi_for_path(path)
    todo = self.imagedescription_todo[path]
    del self.imagedescription_todo[path]

    titles = {x[0] for x in todo}
    titles = [t for t in titles if "-d-" + t not in self.scheduled]
    self.scheduled.update(["-d-" + x for x in titles])
    if not titles:
        return

    siteinfo = self.get_siteinfo_for(api)
    ns_handler = nshandling.NsHandler(siteinfo)
    nsname = ns_handler.get_nsname_by_number(6)

    local_names = []
    for title in titles:
        partial = title.split(":", 1)[1]
        local_names.append(f"{nsname}:{partial}")

    # BigQuery-eligible: collect into pending batch
    if self.bq_lookup and self.bq_lookup.is_available and self.bq_lookup.handles_domain(path):
        for name in local_names:
            self._bq_pending.append((name, api))
        if len(self._bq_pending) >= self._bq_batch_size:
            self._flush_bq_batch()
        # Contributor lookup always uses remote API
        for title in local_names:
            self._refcall(self.get_image_edits, title, api)
        return

    # Non-BigQuery path: unchanged
    for block in split_blocks(local_names, api.api_request_limit):
        self._refcall(self.fetch_image_page, block, api)
    for title in local_names:
        self._refcall(self.get_image_edits, title, api)
```

**5c. Add `_flush_bq_batch` method**:

Called when batch reaches threshold, and also at end of fetching (in `run()` or a cleanup step) to flush remaining titles.

```python
def _flush_bq_batch(self):
    """Send all pending titles to BigQuery in a single query, fall back to remote API for misses."""
    if not self._bq_pending:
        return

    pending = self._bq_pending
    self._bq_pending = []

    titles = [t for t, _ in pending]
    api_by_title = {t: api for t, api in pending}

    rows, missing = self.bq_lookup.fetch_batch(titles)

    # Store BigQuery results + license check + deferred downloads
    for row in rows:
        title = row["name"]
        passes_license = self._store_bq_result(row)
        if passes_license and title in self._bq_deferred_downloads:
            self.schedule_download_image(self._bq_deferred_downloads.pop(title), title)
        elif not passes_license:
            self._bq_deferred_downloads.pop(title, None)
            logger.info("Skipping image download for %s (license filtered)", title)

    # Fall back to remote API for missing titles
    if missing:
        by_api = {}
        for title in missing:
            api = api_by_title[title]
            by_api.setdefault(api, []).append(title)
        for api, api_titles in by_api.items():
            for block in split_blocks(api_titles, api.api_request_limit):
                self._refcall(self.fetch_image_page, block, api)
        # Schedule deferred downloads for fallback titles (no license info yet)
        for title in missing:
            if title in self._bq_deferred_downloads:
                self.schedule_download_image(self._bq_deferred_downloads.pop(title), title)
```

Must also be called in `finish()` (line 1085) to flush remaining titles below batch threshold.

**5d. Initialize `LicenseChecker` for early filtering** (in `__init__`, alongside bq_lookup):

When BigQuery is enabled, create a `LicenseChecker` instance for use at fetch time. This allows skipping image downloads for images that would be filtered at render time anyway.

The filter_type must match the render-time policy. The RL writer (writer.py:173-186) uses:
- `"whitelist"` for `de.wikipedia.org` (only "free" licenses allowed)
- `"blacklist"` for everything else (all except "nonfree" allowed)

We derive the filter_type from the primary wiki URL:

```python
self.fetch_license_checker = None
if self.bq_lookup:
    from mwlib.rendering.licensechecker import LicenseChecker
    # Match the render-time policy: de.wikipedia.org uses whitelist, others use blacklist
    filter_type = "whitelist" if "de.wikipedia.org" in self.api.apiurl else "blacklist"
    self.fetch_license_checker = LicenseChecker(image_db=None, filter_type=filter_type)
    self.fetch_license_checker.read_licenses_csv()
```

The `image_db=None` is fine — `_check_license_from_templates` uses `_get_licenses` directly without needing image_db.

**5e. Add `_check_license_from_templates` helper**:

```python
def _check_license_from_templates(self, title: str, templates: list[str]) -> bool:
    """Check if image should be included based on templates. Returns True if image passes filter."""
    if not self.fetch_license_checker:
        return True  # no checker → include everything
    lowered = [t.lower() for t in templates]
    licenses = self.fetch_license_checker._get_licenses(lowered)
    # Simplified check: no stats tracking (no image_db needed)
    for lic in licenses:
        if lic.license_type == "free":
            return True
        elif lic.license_type == "nonfree":
            return self.fetch_license_checker.filter_type == "nofilter"
    # All unknown → follow filter_type
    return self.fetch_license_checker.filter_type in ["blacklist", "nofilter"]
```

**5f. Use early license check in `_store_bq_result`** to skip image download scheduling:

The `_store_bq_result` method returns a boolean indicating whether the image passed the license check. The caller (`_flush_bq_batch`) uses this to decide whether to skip the image download (but still stores templates for render-time use).

**5g. Add `_store_bq_result` helper**:

```python
def _store_bq_result(self, row) -> bool:
    """Store a BigQuery row into fsout databases. Returns True if image passes license check."""
    title = row["name"]

    # Store pre-extracted templates in templates.db
    templates = row.get("templates", [])
    if templates:
        self.fsout.set_db_key("templates", title, templates)

    # Early license check — skip image download if it won't pass filter
    passes_license = self._check_license_from_templates(title, templates)

    # Supplement imageinfo with dimensions and content URL
    existing = {}
    try:
        existing = self.fsout.get_db_key("imageinfo", title)
    except (KeyError, Exception):
        pass

    if row.get("image_content_url"):
        existing.setdefault("url", row["image_content_url"])
    if row.get("image_width"):
        existing.setdefault("width", row["image_width"])
    if row.get("image_height"):
        existing.setdefault("height", row["image_height"])
    if row.get("url"):
        existing.setdefault("descriptionurl", row["url"])

    if existing:
        self.fsout.set_db_key("imageinfo", title, existing)

    return passes_license
```

**5h. Defer image downloads for BigQuery-eligible domains**:

Currently, `_extract_info_from_image` (line 910-933) calls `schedule_download_image` immediately. For BigQuery-eligible domains, we defer the download until after the license check.

Modify `_extract_info_from_image` to check if the description URL path is BigQuery-eligible. If yes, store `(thumburl, title)` in a new `_bq_deferred_downloads` dict (keyed by title) instead of calling `schedule_download_image`. The download info travels alongside the title through `_bq_pending` → `_flush_bq_batch`.

In `_flush_bq_batch`, after BigQuery results arrive and `_store_bq_result` returns the license decision:
- If license passes: call `schedule_download_image(url, title)` for the deferred download
- If license fails: skip the download entirely, log the filtered image

For titles that fall back to the remote API (missing from BigQuery): schedule their downloads immediately in the fallback path since we don't have templates to check.

```python
def _extract_info_from_image(self, image, imageinfo, new_base_paths, title):
    self.fsout.set_db_key("imageinfo", title, imageinfo)
    thumb_url = imageinfo.get("thumburl") or imageinfo.get("url")
    if thumb_url:
        if thumb_url.startswith("/"):
            thumb_url = parse.urljoin(self.api.baseurl, thumb_url)

        description_url = imageinfo.get("descriptionurl", "") or image.get("fullurl", "")

        # Check if this image is BigQuery-eligible (defer download)
        if self.bq_lookup and description_url and self.bq_lookup.handles_domain(description_url):
            self._bq_deferred_downloads[title] = thumb_url
        else:
            self.schedule_download_image(thumb_url, title)

        if description_url and "/" in description_url:
            path, _ = description_url.rsplit("/", 1)
            # ... rest unchanged (imagedescription_todo handling)
```

### Step 6: Ingestion pipeline (external)

WME snapshot fetching already exists at `../pediapress/infrastructure/bin/fetch_wikimedia_snapshot.py`. No new ingestion code needed in mwlib. The external script downloads NDJSON from the WME API and loads it into BigQuery with the schema defined above.

### Step 7: Tests

**`tests/mwlib/network/test_bigquery_lookup.py`**:
- Mock `google.cloud.bigquery.Client`
- `fetch_batch`: all found, partial match, none found, BigQuery error → graceful fallback
- `handles_domain`: matches configured domains, rejects others
- Data returned has correct shape

**Extend `tests/mwlib/network/test_fetch.py`**:
- `handle_new_basepath` with mocked `bq_lookup`: verify BigQuery tried for configured domains, skipped for others
- `_store_bq_result` writes templates.db and imageinfo.db correctly
- Fallback when BigQuery returns partial results
- `get_image_edits` still called for ALL titles
- Early license check: image with `cc-by-4.0` template → download scheduled; image with `nonfree` template → download skipped
- `_extract_info_from_image` defers downloads for BQ-eligible domains, schedules immediately for others

**`tests/mwlib/core/test_nuwiki.py`** (extend or create):
- `get_image_templates_and_args` returns templates from `templates.db` when available
- Falls back to wikitext parsing when `templates.db` has no entry


## Files to create
- `src/mwlib/network/bigquery_lookup.py`
- `tests/mwlib/network/test_bigquery_lookup.py`

## Files to modify
- `pyproject.toml` — dependency group
- `src/mwlib/utils/_conf.py` — default config for `[bigquery]` section
- `src/mwlib/network/fetch.py` — `FsOutput.__init__` (add templates.db), `Fetcher.__init__`, `_extract_info_from_image` (defer downloads), `handle_new_basepath`, `_flush_bq_batch`, `_store_bq_result`, `_check_license_from_templates`, `finish()`
- `src/mwlib/core/nuwiki.py` — `NuWiki.__init__` (load templates.db), `Adapt.get_image_templates_and_args` (check templates.db first)

## Git branch

Create a new branch `feature/bigquery-image-lookup` from `main` before making any changes.

## Execution order

1. Steps 1–2: Dependencies and config
2. Steps 3–5: Core lookup + storage + fetch integration (templates.db, bigquery_lookup.py, fetch.py changes, nuwiki.py changes)
3. Step 7: Tests throughout

## Verification

1. **Unit tests**: `py.test tests/mwlib/network/test_bigquery_lookup.py tests/mwlib/core/test_nuwiki.py -v`
2. **Existing tests pass**: `py.test tests -n6` (BigQuery disabled by default → zero change to existing behavior)
3. **Manual integration**: With `MWLIB_BIGQUERY_ENABLED=true` + loaded data, run `mw-zip` for an English Wikipedia article with images — verify templates fetched from BigQuery (visible in logs), license checking works
4. **Fallback**: `MWLIB_BIGQUERY_ENABLED=false` → behavior identical to current
5. **Domain config**: `MWLIB_BIGQUERY_DOMAINS=de.wikipedia.org,en.wikipedia.org` → both routed through BigQuery
