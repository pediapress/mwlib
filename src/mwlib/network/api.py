#! /usr/bin/env python

"""API request helpers for retry and error handling."""

from dataclasses import dataclass
from typing import Literal

import httpx

FetchErrorType = Literal["http", "url", "protocol", "timeout"]


@dataclass(frozen=True)
class FetchRetryPolicy:
    max_retries: int
    backoff_factor: float
    jitter: float
    max_delay: float | None


@dataclass
class FetchRetryState:
    retry_count: int = 0
    delay: float = 1.0


@dataclass(frozen=True)
class FetchError:
    error_type: FetchErrorType
    error_detail: object
    status_code: int | None = None


def build_fetch_retry_policy(max_retries, backoff_factor, jitter, max_delay):
    return FetchRetryPolicy(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        jitter=jitter,
        max_delay=max_delay,
    )


def classify_retryable_fetch_error(url, err, *, logger):
    if isinstance(err, httpx.HTTPStatusError):
        status_code = err.response.status_code
        return FetchError("http", status_code, status_code=status_code)
    if isinstance(err, httpx.LocalProtocolError):
        logger.error("HTTP/2 Protocol error for url: %r", url)
        return FetchError("protocol", str(err))
    if isinstance(err, httpx.ReadTimeout):
        logger.error("Read Timeout for url: %r", url)
        return FetchError("timeout", str(err))
    if isinstance(err, httpx.RequestError):
        return FetchError("url", str(err))
    raise TypeError("not a retryable fetch error")


def should_retry(
    error_type: FetchErrorType,
    error_code=None,
    retry_count=0,
    max_retries=0,
):
    if retry_count >= max_retries:
        return False
    if error_type == "http":
        return error_code == 429 or (500 <= error_code < 600)
    return error_type in {"url", "protocol", "timeout"}


def compute_effective_delay(delay, jitter, max_delay, *, uniform_fn):
    effective = delay
    if jitter:
        effective *= uniform_fn(1.0 - jitter, 1.0 + jitter)
    if max_delay is not None:
        effective = min(effective, max_delay)
    return effective


def log_fetch_error(
    url,
    error_type: FetchErrorType | Literal["other"],
    error_detail,
    *,
    logger,
    max_retries=None,
):
    if error_type == "http":
        logger.error(f"HTTP error {error_detail} for {url} after {max_retries} retries")
    elif error_type == "url":
        logger.error(f"URL error {error_detail} for {url} after {max_retries} retries")
    elif error_type == "protocol":
        logger.error(f"Protocol error {error_detail} for {url} after {max_retries} retries")
    elif error_type == "timeout":
        logger.error(f"Timeout error {error_detail} for {url} after {max_retries} retries")
    else:
        logger.error(f"Error fetching {url}: {error_detail}")


def handle_retry(
    *,
    url,
    error_type: FetchErrorType,
    error_detail,
    retry_count,
    max_retries,
    delay,
    backoff_factor,
    sleep_fn,
    logger,
):
    if error_type == "http":
        if error_detail == 429:
            logger.warning(
                f"Rate limit exceeded (HTTP 429) for {url}. "
                f"Retrying in {delay} seconds. Retry {retry_count}/{max_retries}"
            )
        else:
            logger.warning(
                f"Server error {error_detail} for {url}. "
                f"Retrying in {delay} seconds. Retry {retry_count}/{max_retries}"
            )
    elif error_type == "url":
        logger.warning(
            f"URL error {error_detail} for {url}. "
            f"Retrying in {delay} seconds. Retry {retry_count}/{max_retries}"
        )
    else:
        logger.warning(
            f"{error_type} error {error_detail} for {url}. "
            f"Retrying in {delay} seconds. Retry {retry_count}/{max_retries}"
        )

    sleep_fn(delay)
    return delay * backoff_factor


def retry_or_raise(
    *,
    url,
    error,
    retry_state,
    retry_policy,
    logger,
    sleep_fn,
    uniform_fn,
):
    code_for_retry = error.status_code if error.error_type == "http" else None
    if not should_retry(
        error.error_type, code_for_retry, retry_state.retry_count, retry_policy.max_retries
    ):
        log_fetch_error(
            url,
            error.error_type,
            error.error_detail,
            logger=logger,
            max_retries=retry_policy.max_retries,
        )
        return False, retry_state

    next_retry_count = retry_state.retry_count + 1
    effective_delay = compute_effective_delay(
        retry_state.delay,
        retry_policy.jitter,
        retry_policy.max_delay,
        uniform_fn=uniform_fn,
    )
    next_delay = handle_retry(
        url=url,
        error_type=error.error_type,
        error_detail=error.error_detail,
        retry_count=next_retry_count,
        max_retries=retry_policy.max_retries,
        delay=effective_delay,
        backoff_factor=retry_policy.backoff_factor,
        sleep_fn=sleep_fn,
        logger=logger,
    )
    return True, FetchRetryState(retry_count=next_retry_count, delay=next_delay)
