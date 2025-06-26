.. _mwlib-configuration:

~~~~~~~~~~~~~~~~~~~~~~~
Configuration Options
~~~~~~~~~~~~~~~~~~~~~~~

mwlib provides several configuration options that can be set in an ini file or through environment variables.

Configuration File
=================

By default, mwlib looks for configuration in ``~/.mwlibrc``. You can also specify a different configuration file path when using the configuration API.

The configuration file uses the ini format with sections and key-value pairs::

    [section]
    key = value

Environment Variables
====================

Configuration options can also be set through environment variables. The environment variable name is constructed as follows:

- For options in the "mwlib" section: ``MWLIB_OPTION_NAME``
- For options in other sections: ``MWLIB_SECTION_OPTION_NAME``

For example, the "user_agent" option in the "mwlib" section can be set with the ``MWLIB_USER_AGENT`` environment variable.

Available Options
================

mwlib Section
------------

user_agent
  The user agent string to use for HTTP requests.

  Default: "mwlib {version}"

oauth2 Section
------------

client_id
  The OAuth2 client ID for authentication with the MediaWiki API.

  Default: None

client_secret
  The OAuth2 client secret for authentication with the MediaWiki API.

  Default: None

token_url
  The URL for obtaining OAuth2 tokens.

  Default: "https://meta.wikimedia.org/w/rest.php/oauth2/access_token"

enabled
  Whether to use OAuth2 authentication.

  Default: False

  Type: Boolean (yes/true/on/1 for True, no/false/off/0 for False)

http2 Section
------------

enabled
  Whether to use HTTP/2 for API requests.

  Default: True

  Type: Boolean (yes/true/on/1 for True, no/false/off/0 for False)

auto_detect
  Whether to auto-detect HTTP/2 support.

  Default: True

  Type: Boolean (yes/true/on/1 for True, no/false/off/0 for False)

fetch Section
------------

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
  Maximum number of retry attempts.

  Default: 2

  Type: Integer

rvlimit
  Maximum number of revisions to fetch.

  Default: 500

  Type: Integer

Example Configuration
====================

Here's an example configuration file::

    [mwlib]
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
