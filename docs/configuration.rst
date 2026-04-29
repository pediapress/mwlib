.. _mwlib-configuration:

~~~~~~~~~~~~~~~~~~~~~~~
Configuration Options
~~~~~~~~~~~~~~~~~~~~~~~

mwlib provides several configuration options that can be set in an ini file or through environment variables.

Configuration File
=================

mwlib looks for configuration files in the following order (later sources override earlier ones):

1. ``~/.mwlibrc`` — user-specific configuration
2. ``/etc/mwlib.ini`` — system-wide configuration
3. ``mwlib.ini`` in the current working directory — local configuration
4. ``.env`` file (loaded via python-dotenv) — environment file
5. ``MWLIB_*`` environment variables — highest priority

The configuration file uses the ini format with sections and key-value pairs::

    [section]
    key = value

Environment Variables
====================

Configuration options can be set through environment variables using the
pattern ``MWLIB_SECTION_OPTION``. For example, to set ``user_agent`` in the
``DEFAULT`` section::

    MWLIB_DEFAULT_USER_AGENT=MyBot/1.0

Or to set ``max_connections`` in the ``fetch`` section::

    MWLIB_FETCH_MAX_CONNECTIONS=10

The following special environment variables are used directly (without the
``MWLIB_`` prefix):

``WME_USERNAME``
  Wikimedia Enterprise API username (used by ``wme-ingest``).

``WME_PASSWORD``
  Wikimedia Enterprise API password (used by ``wme-ingest``).

``GOOGLE_APPLICATION_CREDENTIALS``
  Path to a GCP service account JSON key file. Used by BigQuery lookup and
  ``wme-ingest`` when no ``--credentials`` argument is given.

``BIGQUERY_PROJECT``
  Default Google Cloud project ID for ``wme-ingest`` (overridden by
  ``--project``).

``BIGQUERY_DATASET``
  Default BigQuery dataset ID for ``wme-ingest`` (overridden by
  ``--dataset``).

``PORT``
  Port for the nserve render server to listen on.

``XNET``
  Set to ``1`` to exclude network tests from the test suite.

Available Options
================

mwlib Section (DEFAULT)
-----------------------

user_agent
  The user agent string to use for HTTP requests.

  Default: "mwlib {version}"

oauth2 Section
--------------

enabled
  Whether to use OAuth2 authentication.

  Default: False

  Type: Boolean (yes/true/on/1 for True, no/false/off/0 for False)

client_id
  The OAuth2 client ID for authentication with the MediaWiki API.

  Default: None

client_secret
  The OAuth2 client secret for authentication with the MediaWiki API.

  Default: None

token_url
  The URL for obtaining OAuth2 tokens.

  Default: "https://meta.wikimedia.org/w/rest.php/oauth2/access_token"

http2 Section
-------------

enabled
  Whether to use HTTP/2 for API requests.

  Default: True

  Type: Boolean (yes/true/on/1 for True, no/false/off/0 for False)

auto_detect
  Whether to auto-detect HTTP/2 support.

  Default: True

  Type: Boolean (yes/true/on/1 for True, no/false/off/0 for False)

fetch Section
-------------

noedits
  Whether edits should be disabled.

  Default: False

  Type: Boolean (yes/true/on/1 for True, no/false/off/0 for False)

api_result_limit
  Maximum number of results per API request.

  Default: 500

  Type: Integer

api_request_limit
  Maximum number of API requests.

  Default: 15

  Type: Integer

max_connections
  Maximum number of connections.

  Default: 20

  Type: Integer

max_retry_count
  Maximum number of retry attempts for failed API requests.

  Default: 2

  Type: Integer

max_requests_per_second
  Domain-scoped rate limit for API requests (token-bucket limiter). Set to 0
  to disable rate limiting.

  Default: 0 (disabled)

  Type: Float

rvlimit
  Maximum number of revisions to fetch.

  Default: 500

  Type: Integer

bigquery Section
----------------

The ``[bigquery]`` section enables a BigQuery-backed lookup for File namespace
description pages. When enabled, mwlib queries a pre-populated BigQuery table
(sourced from Wikimedia Enterprise snapshots) instead of making remote API
calls for each image. This can significantly speed up rendering of
image-heavy articles.

The optional ``google-cloud-bigquery`` dependency must be installed::

    uv pip install "mwlib[bigquery]"

GCP authentication uses ``GOOGLE_APPLICATION_CREDENTIALS`` or Application
Default Credentials.

enabled
  Whether to use BigQuery for image description lookups.

  Default: false

  Type: Boolean (yes/true/on/1 for True, no/false/off/0 for False)

project
  Google Cloud project ID containing the BigQuery dataset.

  Default: "" (required when enabled)

dataset
  BigQuery dataset ID.

  Default: "wme_snapshots"

table
  BigQuery table name.

  Default: "file_pages"

timeout
  Query timeout in seconds.

  Default: 30

  Type: Integer

domains
  Comma-separated list of wiki domains for which BigQuery lookup is used.
  Queries for other domains fall back to the normal API.

  Default: "en.wikipedia.org"

Example Configuration
====================

Here's an example configuration file::

    [DEFAULT]
    user_agent = MyCustomUserAgent/1.0

    [oauth2]
    client_id = your_client_id
    client_secret = your_client_secret
    token_url = https://meta.wikimedia.org/w/rest.php/oauth2/access_token
    enabled = yes

    [http2]
    enabled = yes
    auto_detect = yes

    [fetch]
    noedits = yes
    api_result_limit = 1000
    max_connections = 10
    max_requests_per_second = 5
    max_retry_count = 3

    [bigquery]
    enabled = yes
    project = my-gcp-project
    dataset = wme_snapshots
    table = file_pages
    timeout = 30
    domains = en.wikipedia.org
