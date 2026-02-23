#! /usr/bin/env python

"""Transport helpers for network download flows."""

import os
from dataclasses import dataclass
from urllib import parse

import httpx


@dataclass(frozen=True)
class DownloadRetryPolicy:
    max_retries: int
    initial_delay: float
    backoff_factor: float


@dataclass
class DownloadRetryState:
    retry_count: int = 0
    delay: float = 1.0


def resolve_base_url_and_http2(url, *, conf_module, client_manager_factory, logger):
    parsed_url = parse.urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    use_http2 = conf_module.get("http2", "enabled", True, bool)
    http2_auto_detect = conf_module.get("http2", "auto_detect", True, bool)
    http2_supported = False

    if use_http2 and http2_auto_detect:
        client_manager = client_manager_factory()
        http2_supported = client_manager.detect_http2_support(base_url)
        logger.debug(f"HTTP/2 support detected for {base_url}: {http2_supported}")

    return base_url, use_http2 and (http2_supported or not http2_auto_detect)


def get_download_client(
    url,
    *,
    conf_module,
    client_manager_factory,
    oauth2_client_cls,
    logger,
):
    base_url, enable_http2 = resolve_base_url_and_http2(
        url,
        conf_module=conf_module,
        client_manager_factory=client_manager_factory,
        logger=logger,
    )

    client_manager = client_manager_factory()
    client = client_manager.get_client(base_url=base_url, use_http2=enable_http2)
    if isinstance(client, oauth2_client_cls) and (
        not hasattr(client, "token") or not client.token or client.token.is_expired()
    ):
        client.fetch_token()
    return client


def stream_download_to_temp(client, url, temp_path, *, logger, chunk_size=16384):
    size_read = 0
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with open(temp_path, "wb") as out:
            for chunk in response.iter_bytes(chunk_size=chunk_size):
                size_read += len(chunk)
                out.write(chunk)
    logger.debug(f"read {size_read} bytes from {url}")


def should_retry_download(err, retry_count, max_retries, *, http_status_error_cls):
    if not isinstance(err, http_status_error_cls):
        return False
    return err.response.status_code == 429 and retry_count < max_retries


def retry_download(
    *,
    url,
    delay,
    retry_count,
    max_retries,
    backoff_factor,
    sleep_fn,
    logger,
):
    next_retry_count = retry_count + 1
    logger.warning(
        f"Received HTTP 429 (Too Many Requests) for {url}. "
        f"Retrying in {delay} seconds. Retry {next_retry_count}/{max_retries}"
    )
    sleep_fn(delay)
    return DownloadRetryState(retry_count=next_retry_count, delay=delay * backoff_factor)


def build_download_retry_policy(max_retries, initial_delay, backoff_factor):
    return DownloadRetryPolicy(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
    )


def download_with_retries(
    *,
    client,
    url,
    path,
    temp_path,
    retry_policy,
    http_status_error_cls,
    sleep_fn,
    logger,
):
    retry_state = DownloadRetryState(delay=retry_policy.initial_delay)

    while True:
        try:
            stream_download_to_temp(client, url, temp_path, logger=logger)
            os.rename(temp_path, path)
            return
        except http_status_error_cls as err:
            if not should_retry_download(
                err,
                retry_state.retry_count,
                retry_policy.max_retries,
                http_status_error_cls=http_status_error_cls,
            ):
                logger.error(f"ERROR DOWNLOADING {url}: {err}")
                raise
            retry_state = retry_download(
                url=url,
                delay=retry_state.delay,
                retry_count=retry_state.retry_count,
                max_retries=retry_policy.max_retries,
                backoff_factor=retry_policy.backoff_factor,
                sleep_fn=sleep_fn,
                logger=logger,
            )
        except (httpx.RequestError, OSError) as err:
            logger.error(f"ERROR DOWNLOADING {url}: {err}")
            raise
