#! /usr/bin/env python

"""Authentication helpers for OAuth2 token lifecycle."""

from urllib import parse

import httpx


def get_oauth_domain(apiurl):
    return parse.urlparse(apiurl).netloc


def token_needs_refresh(token_info, current_time):
    return not token_info or current_time >= token_info.get("expires_at", 0)


def token_backoff_elapsed(token_info, current_time):
    return current_time >= token_info.get("next_retry_at", 0)


def store_oauth_token(token_info_map, domain, token, current_time):
    token_info_map[domain] = {
        "token": token,
        "expires_at": current_time + token.get("expires_in", 3600),
        "next_retry_at": 0,
        "retry_delay": 0,
    }


def store_oauth_token_failure(token_info_map, domain, token_info, current_time):
    retry_delay = token_info.get("retry_delay", 5) or 5
    retry_delay = min(retry_delay * 2, 300)
    token_info_map[domain] = {
        **token_info,
        "next_retry_at": current_time + retry_delay,
        "retry_delay": retry_delay,
    }
    return retry_delay


def fetch_and_store_oauth_token(
    *,
    domain,
    token_info,
    current_time,
    token_info_map,
    http_client,
    logger,
):
    logger.debug(f"Fetching OAuth2 token for domain: {domain}")
    user_agent = http_client.headers.get("user-agent", "mwlib")
    try:
        token = http_client.fetch_token(headers={"User-Agent": user_agent})
    except httpx.HTTPError as exc:
        retry_delay = store_oauth_token_failure(token_info_map, domain, token_info, current_time)
        logger.error(
            f"Failed to fetch OAuth2 token for {domain}: {exc}. Retrying in {retry_delay} seconds."
        )
        raise RuntimeError(f"Failed to fetch OAuth2 token for {domain}: {exc}") from exc

    store_oauth_token(token_info_map, domain, token, current_time)


def ensure_oauth2_token(
    *,
    enabled,
    apiurl,
    token_info_map,
    http_client,
    logger,
    current_time_fn,
):
    """Make sure the OAuth2 client has a valid token.

    The token is cached by domain in ``token_info_map``. The OAuth2 client
    holds its own ``client.token`` attribute that authlib reads when
    serializing the ``Authorization`` header. The two pieces of state can
    drift apart — most obviously when the client is invalidated and
    recreated while the per-domain cache entry is still fresh. If we
    short-circuit on ``token_info_map`` alone, the new client would send
    unauthenticated requests.

    Order of operations:
    1. If the cached entry is fresh and the client already has the same
       token, return.
    2. If the cached entry is fresh but the client is missing it, push
       the cached token onto the client and return.
    3. Otherwise refetch (subject to backoff).
    """
    if not enabled:
        return

    domain = get_oauth_domain(apiurl)
    current_time = current_time_fn()
    token_info = token_info_map.get(domain, {})

    if not token_needs_refresh(token_info, current_time):
        cached_token = token_info.get("token")
        client_token = getattr(http_client, "token", None)
        if cached_token is not None and client_token == cached_token:
            return
        if cached_token is not None:
            try:
                http_client.token = cached_token
                return
            except Exception:
                logger.warning(
                    "Failed to restore cached OAuth token onto client; will refetch",
                    exc_info=True,
                )
                # Fall through to refetch.

    if not token_backoff_elapsed(token_info, current_time):
        return

    fetch_and_store_oauth_token(
        domain=domain,
        token_info=token_info,
        current_time=current_time,
        token_info_map=token_info_map,
        http_client=http_client,
        logger=logger,
    )
