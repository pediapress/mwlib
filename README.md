# mwlib - MediaWiki Parser and Utility Library

## Overview
**mwlib** is a versatile library designed for parsing MediaWiki articles and converting them to various output formats. A notable application of mwlib is in Wikipedia's "Print/export" feature, where it is used to create PDF documents from Wikipedia articles.


## Getting Started

### Prerequisites
To build mwlib, ensure you have the following software installed:
- Python (version 3.11 or 3.12)
- Ploticus
- re2c
- Perl
- Pillow / PyImage
- ImageMagick
- uv (Python package installer, faster alternative to pip)


Setup a virtual environment for Python 3.11 or 3.12 and activate it.

#### Installing uv
If you don't have uv installed, you can install it following the instructions at [uv's official documentation](https://github.com/astral-sh/uv).

For example, on Unix-like systems:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or using pip:
```bash
pip install uv
```

#### Installing mwlib
To install all dependencies and the project, run:

    $ make install

This will use uv to install all required dependencies.

To build the C extensions and install mwlib in development mode:

    $ make build
    $ make develop

## Documentation

Please visit http://mwlib.readthedocs.org/en/latest/index.html for
detailed documentation.

## Configuration

### OAuth2 Configuration
mwlib supports OAuth2 client_credentials flow for Wikipedia API access. This allows authenticated access to MediaWiki APIs that require OAuth2 authentication, while maintaining compatibility with wikis that don't use OAuth2.



#### OAuth2 Configuration Options

The following configuration options are available for OAuth2:

- `oauth2.client_id`: OAuth2 client ID
- `oauth2.client_secret`: OAuth2 client secret
- `oauth2.token_url`: URL for obtaining OAuth2 tokens (default: https://meta.wikimedia.org/w/rest.php/oauth2/access_token)
- `oauth2.enabled`: Whether to use OAuth2 (default: False)

#### HTTP/2 Configuration Options

mwlib also supports HTTP/2 for improved performance:

- `http2.enabled`: Whether to use HTTP/2 (default: True)
- `http2.auto_detect`: Whether to auto-detect HTTP/2 support (default: True)

These configuration options can be set either through environment variables or in a configuration
file (mwlib.ini or ~/.mwlibrc). The following table shows the mapping between configuration file 
options and their corresponding environment variables:

| Config File Option   | Environment Variable       | Description                |
|----------------------|----------------------------|----------------------------|
| oauth2.client_id     | MWLIB_OAUTH2_CLIENT_ID     | OAuth2 client ID           |
| oauth2.client_secret | MWLIB_OAUTH2_CLIENT_SECRET | OAuth2 client secret       |
| oauth2.token_url     | MWLIB_OAUTH2_TOKEN_URL     | Token endpoint URL         |
| oauth2.enabled       | MWLIB_OAUTH2_ENABLED       | Enable OAuth2 (true/false) |
| http2.enabled        | MWLIB_HTTP2_ENABLED        | Enable HTTP/2 (true/false) |
| http2.auto_detect    | MWLIB_HTTP2_AUTO_DETECT    | Auto-detect HTTP/2 support |

Example configuration file (mwlib.ini):

```ini
[oauth2]
enabled=true
client_id=your-client-id
client_secret=your-client-secret

[http2]
auto_detect=true

```

#### Example Usage
You can also set the config parameters directly when instantiating MwApi:

```python
from mwlib.network.sapi import MwApi

# Using OAuth2
api = MwApi(
    apiurl="https://en.wikipedia.org/w/api.php",
    use_oauth2=True
)
```

The recommended best practice, however, is to configure environment variables:
```shell
export MWLIB_OAUTH2_CLIENT_ID="your_client_id"
export MWLIB_OAUTH2_CLIENT_SECRET="your_client_secret"
export MWLIB_OAUTH2_ENABLED="True"
```

### File Store Lookup for Image Description Pages

mwlib can look up image description pages (namespace 6) in a local SQLite file instead of fetching them from the remote MediaWiki API. This significantly reduces the number of API requests and bypasses Wikipedia rate limits for configured domains.

The data originates from the [Wikimedia Enterprise API](https://enterprise.wikimedia.com/docs/snapshot/) snapshot endpoint, which provides Wikipedia page data as NDJSON files. `mw-file-store` turns that snapshot into a SQLite file of pre-extracted metadata: templates (used for license checking), image dimensions, content URLs, and license information.

#### How it works

1. During ZIP creation (`mw-zip`), image description page titles for configured domains (default: `en.wikipedia.org`) are batched and looked up in the file store.
2. For pages found in the store, templates are stored locally and an early license check is performed — images that fail the license filter are never downloaded.
3. Pages not found in the store fall back to the remote MediaWiki API.
4. Non-configured domains (e.g., Commons) always use the remote API.

#### Configuration Options

| Config File Option | Environment Variable     | Default          | Description                                            |
|--------------------|--------------------------|------------------|--------------------------------------------------------|
| filestore.path     | MWLIB_FILESTORE_PATH     | _(unset)_        | SQLite file to read; the lookup is off when unset      |
| filestore.domains  | MWLIB_FILESTORE_DOMAINS  | en.wikipedia.org | Comma-separated domains to route through the file store (wikis with the English `File:` namespace only) |

Example environment variable configuration:
```shell
export MWLIB_FILESTORE_PATH="/data/file_pages.sqlite"
export MWLIB_FILESTORE_DOMAINS="en.wikipedia.org"
```

Or in a configuration file (mwlib.ini):
```ini
[filestore]
path=/data/file_pages.sqlite
domains=en.wikipedia.org
```

When no store is configured, or the file is missing or unreadable, mwlib falls back to the remote API automatically with no change in behavior. The file is re-opened whenever it is replaced, so a rebuild needs no restart.

#### Building the File Store

Use the `mw-file-store` command to download the Wikimedia Enterprise namespace 6 snapshot (about 2 GB) and build the SQLite file:

```bash
mw-file-store --path /data/file_pages.sqlite

# Rebuild even if the snapshot has not changed
mw-file-store --path /data/file_pages.sqlite --fresh
```

The build writes `<path>.new` and atomically renames it over `<path>`, so readers never see a partial file. A run whose snapshot matches the live file exits without downloading, and a new file with too few rows (or more than 10% fewer than the live one) is refused. `--path` defaults to `MWLIB_FILESTORE_PATH`.

This requires Wikimedia Enterprise API credentials:
```shell
export WME_USERNAME="your-username"
export WME_PASSWORD="your-password"
```

## Docker Compose Setup
For users interested in setting up mwlib using Docker Compose, detailed instructions are available at [Docker Compose documentation](https://docs.docker.com/compose/).


## License

Copyright (c) 2007-2012 PediaPress GmbH

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

* Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above
  copyright notice, this list of conditions and the following
  disclaimer in the documentation and/or other materials provided
  with the distribution. 

* Neither the name of PediaPress GmbH nor the names of its
  contributors may be used to endorse or promote products derived
  from this software without specific prior written permission. 

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

.. _SpamBayes: http://spambayes.sourceforge.net/
