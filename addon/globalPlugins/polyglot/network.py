# -*- coding: utf-8 -*-

import functools
import time
import requests
from .exceptions import NetworkConnectionError, ApiResponseError, AuthenticationError
from logHandler import log
import addonHandler

addonHandler.initTranslation()

def retry_on_network_error(attempts=3, delay=0.5, backoff=1.5):
    """
    A decorator that provides intelligent retry logic for `requests` calls.
    It handles not only pure network errors (e.g., timeouts) but also recoverable API errors
    (e.g., 408, 429, and 5xx HTTP status codes).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                # Catch pure network-level errors.
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    last_exception = e
                    log_message_prefix = f"Network error on attempt {attempt + 1}/{attempts} for {func.__name__}"
                # Catch all HTTP errors and determine internally if they are retryable.
                except requests.exceptions.HTTPError as e:
                    status_code = e.response.status_code
                    # Define which HTTP status codes are retryable.
                    retryable_status_codes = {408, 429} # 408: Request Time-out, 429: Too Many Requests
                    if status_code >= 500 or status_code in retryable_status_codes:
                        # If it's a retryable error, log it and prepare for the next loop.
                        last_exception = e
                        log_message_prefix = f"Retryable HTTP {status_code} on attempt {attempt + 1}/{attempts} for {func.__name__}"
                    else:
                        # If it's a non-retryable HTTP error (e.g., 400, 403), stop trying and re-raise immediately.
                        # send_request will then catch this exception and wrap it in our custom type.
                        raise e
                # If this is the last attempt, break the loop to prepare for the final wrapped exception.
                if attempt + 1 >= attempts:
                    log.error(f"{func.__name__} failed after {attempts} attempts.", exc_info=last_exception)
                    break
                # Log a warning and wait for the next retry.
                log.warning(
                    f"{log_message_prefix}: {last_exception}. Retrying in {current_delay:.1f}s..."
                )
                time.sleep(current_delay)
                current_delay *= backoff
            # After all retries fail, wrap the last caught exception into our own user-friendly exception type.
            if isinstance(last_exception, requests.exceptions.HTTPError):
                raise ApiResponseError(_("Service temporarily unavailable or timed out. Please try again later. (HTTP {code})").format(code=last_exception.response.status_code)) from last_exception
            elif isinstance(last_exception, requests.exceptions.Timeout):
                raise NetworkConnectionError(_("Request to translation service timed out")) from last_exception
            else:
                raise NetworkConnectionError(_("Network connection error: {error}").format(error=last_exception)) from last_exception
        return wrapper
    return decorator

@retry_on_network_error()
def send_request(method: str, url: str, headers: dict = None, data: bytes = None, timeout: int = 15, proxies: dict = None) -> str:
    """
    Sends an HTTP(S) request using the `requests` library.
    This function is protected by the `@retry_on_network_error` decorator
    and is only responsible for a single request attempt and handling non-retryable business errors.
    """
    headers = headers or {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'Mozilla/5.0'
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            timeout=timeout,
            proxies=proxies
        )
        # Let requests raise an HTTPError for any 4xx or 5xx response.
        # Our decorator will then catch this exception and decide whether to retry.
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        # This try-except block now only handles HTTP errors that the decorator has decided not to retry.
        log.error(f"Non-retryable HTTP error occurred: {e.response.status_code} {e.response.reason}", exc_info=True)
        status_code = e.response.status_code
        if status_code == 403:
            raise AuthenticationError(_("Authentication failed. Please check your API key.")) from e
        if status_code == 456:
             raise ApiResponseError(_("Monthly translation quota has been reached.")) from e
        # For all other non-retryable 4xx errors.
        error_details = e.response.text[:200]
        raise ApiResponseError(
            _("Service returned an error: {code} {reason}. Details: {details}").format(
                code=status_code,
                reason=e.response.reason,
                details=error_details
            )
        ) from e
