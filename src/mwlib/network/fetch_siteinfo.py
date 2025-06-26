#!/usr/bin/env python3

import json
import sys
import logging
from urllib.error import URLError
from urllib.request import urlopen
from authlib.integrations.httpx_client import OAuth2Client

import httpx
from mwlib.network.http_client import HttpClientManager
from mwlib.utils import conf

logger = logging.getLogger(__name__)


def detect_http2_support(url):
    """Detect if the server at the given URL supports HTTP/2.

    Args:
        url: The URL to check.

    Returns:
        bool: True if the server supports HTTP/2, False otherwise.
    """
    # Use the HttpClientManager to detect HTTP/2 support
    client_manager = HttpClientManager.get_instance()
    return client_manager.detect_http2_support(url)


def fetch(lang):
    base_url = f"https://{lang}.wikipedia.org"
    api_url = f"{base_url}/w/api.php"
    query_params = {
        "action": "query",
        "meta": "siteinfo",
        "siprop": "general|namespaces|namespacealiases|magicwords|interwikimap",
        "format": "json"
    }

    full_url = f"{api_url}?action=query&meta=siteinfo&siprop=general|namespaces|namespacealiases|magicwords|interwikimap&format=json"
    logger.info(f"fetching {full_url}")

    # Check if HTTP/2 is enabled in configuration
    use_http2 = conf.get("http2", "enabled", True, bool)

    # Detect HTTP/2 support if auto-detect is enabled
    http2_auto_detect = conf.get("http2", "auto_detect", True, bool)
    http2_supported = False

    if use_http2 and http2_auto_detect:
        http2_supported = detect_http2_support(base_url)
        logger.info(f"HTTP/2 support detected: {http2_supported}")

    try:
        # Use HttpClientManager to get a client with appropriate HTTP/2 settings
        client_manager = HttpClientManager.get_instance()
        client = client_manager.get_client(
            base_url=base_url,
            use_http2=use_http2 and (http2_supported or not http2_auto_detect)
        )
        if isinstance(client, OAuth2Client) and (
            not hasattr(client, "token") or not client.token or client.token.is_expired()
        ):
            client.fetch_token()

        # Make the request using the client
        response = client.get(api_url, params=query_params)
        response.raise_for_status()
        data = response.json()["query"]

        # Add HTTP/2 support information to the siteinfo
        data["http2_supported"] = http2_supported

    except Exception as exc:
        logger.error(f"Error fetching {full_url} with httpx: {exc}")
        # Fall back to urllib if httpx fails
        try:
            with urlopen(full_url) as remote_file:
                data = json.loads(remote_file.read())["query"]
                # HTTP/2 support is unknown when falling back to urllib
                data["http2_supported"] = False
        except URLError as exc:
            logger.error(f"error fetching {full_url}: {exc}")
            return

    site_info_path = f"siteinfo-{lang}.json"
    logger.info(f"writing {site_info_path}")
    with open(site_info_path, "w", encoding="utf-8") as site_info_file:
        json.dump(data, site_info_file, indent=4, sort_keys=True)


def main(argv):
    languages = argv[1:]
    if not languages:
        languages = ["de", "en", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "simple", "sv"]

    for lang in languages:
        fetch(lang.lower())


if __name__ == "__main__":
    main(sys.argv)
