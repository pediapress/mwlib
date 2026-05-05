# Release Notes for mwlib 0.18.8

## What's New in 0.18.8

### `wme-ingest` MERGE Swap Reliability

- **Duplicate-article tolerance:** The atomic `MERGE` swap that replaces `article_pages` from staging used to abort a fresh EN NS0 ingest with `UPDATE/MERGE must match at most one source row for each target row` whenever the snapshot shipped duplicate articles for the same title. Wikimedia Enterprise documents that snapshots may carry up to ~1% duplicates and asks consumers to keep the row with the highest `version.identifier`. The MERGE now wraps staging in a `QUALIFY ROW_NUMBER() OVER (PARTITION BY name ORDER BY version_identifier DESC NULLS LAST)` subquery before the join, so duplicates collapse to the latest revision per article.
- **Destination schema unchanged:** The new `version_identifier` field lives only on the staging table. Pulumi-managed schemas (`article_pages`, `file_pages`) need no migration. Streaming-insert and legacy tarball-load paths transparently drop the field.
- **Article deletions:** No change required — the existing `WHEN NOT MATCHED BY SOURCE THEN DELETE` clause already implements WME's recommended approach (deleted articles drop out of the next snapshot, which removes them from the destination on the next swap).

### Operator Safeguards

- **Pre-flight check on swap:** A run that loaded all chunks under 0.18.7 but died before `swap_done = True` left a state file pointing at a staging table without `version_identifier`. Resuming on 0.18.8 now fails fast with an actionable message naming the column and directing the operator to rerun with `--fresh`, instead of crashing inside BigQuery with a vague `Unrecognized name`.
- **Reproducible dedup across re-runs:** The `ROW_NUMBER` ordering now includes `date_modified` then `identifier` as stable tiebreakers (both `DESC NULLS LAST`). Two staging rows tied on `version_identifier` (NULL on older snapshots, or a delete+recreate that reuses a rev id) used to get an undefined winner based on physical storage order; a crash-and-resume now reproduces the same result.

### Defensive Parsing

- **Bool rejected in `version.identifier`:** Python's `isinstance(True, int)` is `True` (bool is a subclass of int), so a malformed snapshot record carrying `"identifier": true` would otherwise have ranked alongside genuine rev id 1 in the dedup ORDER BY. Now explicitly excluded.

## Upgrading to 0.18.8

If you have a `wme-ingest` run that was interrupted on 0.18.7 between "all chunks loaded" and "MERGE complete" (state file shows `swap_done: false`), rerun with `--fresh` so staging is repopulated under the new schema. A clean run from a fresh state file needs no special handling.

---

# Release Notes for mwlib 0.18.2

## What's New in 0.18.2

### BigQuery Lookup for Image Description Pages
- **BigQuery-first lookup:** Image description pages (namespace 6) for configured Wikipedia domains are now batch-queried from Google BigQuery instead of fetching from the remote MediaWiki API. This significantly reduces API requests and bypasses Wikipedia rate limits.
- **Early license checking at fetch time:** Templates from BigQuery are checked against the license database before image downloads are scheduled. Images that fail the license filter (e.g., nonfree album covers) are never downloaded, saving bandwidth and time.
- **Deferred image downloads:** For BigQuery-eligible domains, image downloads are deferred until the license check completes. Only images that pass the filter are downloaded.
- **Configurable domains:** The set of BigQuery-backed domains is fully configurable via `MWLIB_BIGQUERY_DOMAINS` (default: `en.wikipedia.org`). Non-configured domains continue to use the remote API.
- **Graceful fallback:** If BigQuery is unavailable, misconfigured, or missing data for specific pages, all requests fall back to the remote MediaWiki API automatically.
- **New `templates.db` storage:** Pre-extracted templates from BigQuery are stored in a new `templates.db` SqliteDict, which is checked at render time before falling back to wikitext parsing.
- **WME ingestion CLI (`wme-ingest`):** New command-line tool for downloading Wikimedia Enterprise namespace 6 snapshots and loading them into BigQuery.

### Configuration

All BigQuery settings are configurable via environment variables or `mwlib.ini`:

| Environment Variable         | Default          | Description                                       |
|------------------------------|------------------|---------------------------------------------------|
| MWLIB_BIGQUERY_ENABLED       | false            | Master switch to enable BigQuery lookups           |
| MWLIB_BIGQUERY_PROJECT       | _(required)_     | GCP project ID                                    |
| MWLIB_BIGQUERY_DATASET       | wme_snapshots    | BigQuery dataset name                             |
| MWLIB_BIGQUERY_TABLE         | file_pages       | BigQuery table name                               |
| MWLIB_BIGQUERY_TIMEOUT       | 30               | Query timeout in seconds                          |
| MWLIB_BIGQUERY_DOMAINS       | en.wikipedia.org | Comma-separated domains to route through BigQuery |

---

# Release Notes for mwlib 0.18.1

## What's New in 0.18.1

### Domain-Scoped Rate Limiting
- **Per-domain rate limiting:** API requests are now rate-limited per domain using a token-bucket algorithm, preventing excessive requests to any single MediaWiki instance. Configurable via `MWLIB_FETCH_MAX_REQUESTS_PER_SECOND`.
- **Download rate limiting:** Image downloads are also subject to per-domain rate limiting, separate from API request limits.
- **Retry with exponential backoff:** Both `MwApi._fetch` and `download_to_file` now implement retry with exponential backoff and jitter for transient errors (HTTP 429, 5xx, timeouts).
- **Improved error classification:** Network errors are classified by type (http, url, protocol, timeout) with per-type retry decisions — permanent errors (404) are not retried.
- **Configurable retry policies:** Retry count, backoff factor, and max delay are configurable via the `[fetch]` config section.

---

# Release Notes for mwlib 0.18.0

## What's New in 0.18.0

### Project Structure Refactoring
- **Modular package layout:** The codebase has been reorganized into well-defined packages: `mwlib/core/`, `mwlib/parser/`, `mwlib/network/`, `mwlib/rendering/`, `mwlib/writers/`, `mwlib/utils/`, `mwlib/extensions/`, and `mwlib/apps/`.
- **Standardized import paths:** All import paths have been updated to reflect the new package structure.
- **Entry point trampoline:** Introduced `main_trampoline.py` for CLI entry points, replacing monkey patching in `mwlib.apps` initialization.

### Networking & HTTP
- **HTTP client manager:** New `HttpClientManager` singleton with support for both standard and OAuth2 clients, HTTP/2 auto-detection, and connection pool management.
- **httpx migration:** `MwApi` refactored to use `httpx` for HTTP requests, with support for HTTP/2 and OAuth2 client_credentials flow.
- **OAuth2 support:** Built-in OAuth2 authentication for MediaWiki APIs that require it, with token lifecycle management and exponential backoff on failures.
- **Batch contributor lookup:** Contributor API calls are batched for efficiency.

### Build System & Dependencies
- **uv package manager:** Replaced `pip` with `uv pip` throughout the build system for faster dependency resolution.
- **python-dotenv integration:** Environment variables are now loaded from `.env` files automatically.
- **Cython 3.1.2+:** Upgraded Cython with Python 3.8+ compatibility updates for templated nodes and scanner.

### ZIP Creation (`buildzip`)
- **Modernized buildzip:** Consolidated `buildzip` and `buildzip2` into a single implementation with simplified `make_nuwiki` callback handling.
- **File extension filtering:** Added `skip_ext` support to exclude files by extension during ZIP creation.
- **Higher default image size:** Increased default thumbnail size to 1280px to match Wikipedia's largest thumbnail size.

### PDF Writer
- **RlWriter improvements:** Consistent attribute naming for figure dimensions, improved terminology, and better debug handling.
- **RTL text fix:** Fixed right-to-left text alignment handling in `text_style` and `heading_style`.
- **Refactored pdfstyles:** Cleaner styling functions and McCabe complexity compliance.

### Code Quality
- **Ruff linting:** Applied ruff across the entire codebase with rules for complexity (C90), pydocstyle (D), pycodestyle (E), pyflakes (F), isort (I), and flake8-simplify (SIM).
- **Standardized logging:** Consistent logging levels and improved file handling in utility modules.
- **Image path resolution:** Improved fallback handling for image paths in `nuwiki.py`.

### Testing
- **New test suites:** Added unit tests for `fetch_siteinfo`, `download_to_file`, HTTP client manager, OAuth2 token handling, and rate limiting.
- **Integration test marker:** Slow RL writer tests are now marked with `@pytest.mark.integration` and excluded from default test runs.

## Upgrading to 0.18.0

mwlib 0.18.0 requires Python 3.11 or 3.12. The package structure has changed significantly — update any direct imports from `mwlib.*` to the new paths (e.g., `mwlib.nuwiki` → `mwlib.core.nuwiki`).

---

# Release Notes for mwlib 0.17.0

We're thrilled to announce the release of mwlib version 0.17.0, a significant step forward in our journey, primarily focused on transitioning from Python 2 to Python 3. This release brings enhanced code quality, improved scalability, and performance optimizations.

## What's New in 0.17.0

### Python 3 Migration
- **Complete Shift to Python 3:** Embracing the future with full Python 3 support.
- **End of Python 2 Support:** Aligning with modern standards for better performance and security.

### Features and Improvements
- **Ploticus Dependency Removed:** Transitioned to using PNG images from HTML for a more streamlined experience.
- **Docker Compose Examples Added:** Easy-to-follow Docker Compose examples for quick setup and integration.
- **Local MediaWiki Instance Setup:** Instructions on setting up mwlib with a local MediaWiki instance for seamless integration.
- **Integrated Dependencies:** The [qserve](https://github.com/pediapress/qserve) and [mwlib.rl](https://github.com/pediapress/mwlib.rl) libraries are now integrated into core mwlib for a more straightforward development process and easier setup.   


### Code Quality and Security
- **Code Linters Integration:** Used Ruff, Bandit, Pylint and flake8 for robust code quality.
- **Bug Fixes and Optimizations:** Comprehensive code clean-up for enhanced stability and performance.
- **Scalability Enhancements:** Code refactoring for better maintainability and scalability.


### Project Structure Refactoring
- **Refactored Project Structure:** The project structure has been overhauled, with a focus on better organization and maintainability.
- **Creation of Classes and Modules:** Introduction of new classes and the grouping of code into well-defined modules and files for improved clarity and efficiency.


### Performance Enhancements
- **Efficiency Boost:** Leverage the speed and efficiency of Python 3 for faster processing.

## Docker Compose Setup

- **Easy Setup with Docker Compose:** Check out the newly added Docker Compose examples for a straightforward setup process.
- **Local MediaWiki Integration:** Detailed guidelines for integrating mwlib with your local MediaWiki instance using Docker Compose.


## Upgrading to 0.17.0

To benefit from the latest improvements, users are encouraged to upgrade to version 0.17.0. Ensure you have Python 3.8 or later for this version. Follow your standard environment's upgrade procedure to update to the latest mwlib.


## Stay Tuned

We're committed to continual improvement and value your feedback. Stay connected for more updates and enhancements in future releases.

---

Stay tuned for more updates, and happy coding!
