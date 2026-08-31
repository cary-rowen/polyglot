# -*- coding: utf-8 -*-

# Copyright (C) 2025-2026 cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import functools
import threading
import time
from collections.abc import Callable
from http import cookiejar

# Best practice: Import advanced typing tools for creating robust decorators and `cast`.
from typing import Any, ParamSpec, TypeVar, cast

import addonHandler
import requests
from logHandler import log
from requests.adapters import HTTPAdapter

from .exceptions import ApiResponseError, AuthenticationError, NetworkConnectionError

addonHandler.initTranslation()

# Best practice: Use ParamSpec and TypeVar to create a generic decorator.
P = ParamSpec("P")
R = TypeVar("R")

# Connection pool sizing. Translations run on short-lived worker threads, so the pool must be
# large enough to keep one idle connection per host that is in active use.
_POOL_CONNECTIONS = 8
_POOL_MAXSIZE = 16

_sessionLock = threading.Lock()
_session: requests.Session | None = None


def getSession() -> requests.Session:
	"""
	Return the add-on wide `requests.Session` used for every engine request.

	A single session keeps its underlying HTTPS connections alive, so consecutive
	translations reuse an established connection instead of paying for DNS resolution,
	the TCP handshake and the TLS handshake again. That saves roughly 200-400 ms per
	request, which dominates the response time of fast translation models.

	The session is shared between translation threads: `requests` sessions are safe to
	use this way as long as their attributes are not mutated after creation, and the
	underlying urllib3 connection pool is itself thread-safe.
	"""
	global _session
	with _sessionLock:
		session = _session
		if session is None:
			session = requests.Session()
			# Every request previously ran on a throwaway session, so no cookie ever outlived
			# a call. Preserve that by refusing all cookies, otherwise a shared session would
			# start carrying state between unrelated engines and requests.
			session.cookies.set_policy(cookiejar.DefaultCookiePolicy(allowed_domains=[]))
			adapter = HTTPAdapter(pool_connections=_POOL_CONNECTIONS, pool_maxsize=_POOL_MAXSIZE)
			session.mount("https://", adapter)
			session.mount("http://", adapter)
			_session = session
		return session


def closeSession() -> None:
	"""Close the shared session and release every pooled connection."""
	global _session
	with _sessionLock:
		session = _session
		_session = None
	if session is None:
		return
	try:
		session.close()
	except Exception:
		log.debug("Ignoring an error raised while closing the shared HTTP session.", exc_info=True)


def retryOnNetworkError(
	attempts: int = 3,
	delay: float = 0.5,
	backoff: float = 1.5,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
	"""
	Retry decorated `requests` calls after transient network and HTTP failures.
	It handles not only pure network errors (e.g., timeouts) but also recoverable API errors
	(e.g., 408, 429, and 5xx HTTP status codes).
	"""

	def decorator(func: Callable[P, R]) -> Callable[P, R]:
		@functools.wraps(func)
		def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
			currentDelay = delay
			lastException: Exception | None = None
			for attempt in range(attempts):
				try:
					return func(*args, **kwargs)
				# Catch pure network-level errors.
				except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
					lastException = e
					logMessagePrefix = (
						f"Network error on attempt {attempt + 1}/{attempts} for {func.__name__}"
					)
				# Catch all HTTP errors and determine internally if they are retryable.
				except requests.exceptions.HTTPError as e:
					statusCode = e.response.status_code
					# Define which HTTP status codes are retryable.
					retryableStatusCodes = {408, 429}  # 408: Request Time-out, 429: Too Many Requests
					if statusCode >= 500 or statusCode in retryableStatusCodes:
						# If it's a retryable error, log it and prepare for the next loop.
						lastException = e
						logMessagePrefix = f"Retryable HTTP {statusCode} on attempt {attempt + 1}/{attempts} for {func.__name__}"
					else:
						# If it's a non-retryable HTTP error (e.g., 400, 403), stop trying and re-raise immediately.
						# sendRequest will then catch this exception and wrap it in our custom type.
						raise e
				# If this is the last attempt, break the loop to prepare for the final wrapped exception.
				if attempt + 1 >= attempts:
					log.error(
						"%s failed after %d attempts (%s).",
						func.__name__,
						attempts,
						type(lastException).__name__,
					)
					break
				# Log a warning and wait for the next retry.
				log.warning("%s. Retrying in %.1fs...", logMessagePrefix, currentDelay)
				time.sleep(currentDelay)
				currentDelay *= backoff
			# After all retries fail, wrap the last caught exception into our own user-friendly exception type.
			assert lastException is not None
			if isinstance(lastException, requests.exceptions.HTTPError):
				raise ApiResponseError(
					_(
						"Service temporarily unavailable or timed out. Please try again later. (HTTP {code})",
					).format(code=lastException.response.status_code),
				) from None
			elif isinstance(lastException, requests.exceptions.Timeout):
				raise NetworkConnectionError(
					_("Request to translation service timed out"),
				) from None
			else:
				# Translators: Error message for generic network connection failures. {error} is the detailed error description.
				raise NetworkConnectionError(
					_("Network connection error. Check your connection and try again."),
				) from None

		return wrapper

	return decorator


@retryOnNetworkError()
def sendRequest(
	method: str,
	url: str,
	headers: dict[str, str] | None = None,
	data: bytes | None = None,
	timeout: int = 15,
	proxies: dict[str, str | None] | None = None,
) -> str:
	"""
	Send one HTTP(S) request using the shared, connection-pooling `requests` session.
	This function is protected by the `@retryOnNetworkError` decorator
	and is only responsible for a single request attempt and handling non-retryable business errors.
	"""
	finalHeaders = headers.copy() if headers else {}
	if "User-Agent" not in finalHeaders:
		finalHeaders["User-Agent"] = "Mozilla/5.0"
	try:
		response = getSession().request(
			method=method,
			url=url,
			headers=finalHeaders,
			data=data,
			timeout=timeout,
			proxies=cast(Any, proxies),
		)
		# Let requests raise an HTTPError for any 4xx or 5xx response.
		# Our decorator will then catch this exception and decide whether to retry.
		response.raise_for_status()
		return response.text
	except requests.exceptions.HTTPError as e:
		# This try-except block now only handles HTTP errors that the decorator has decided not to retry.
		log.error("Translation service returned non-retryable HTTP status %d.", e.response.status_code)
		statusCode = e.response.status_code
		if statusCode == 403:
			raise AuthenticationError(_("Authentication failed. Please check your API key.")) from None
		if statusCode == 456:
			raise ApiResponseError(_("Monthly translation quota has been reached.")) from None
		# For all other non-retryable 4xx errors.
		errorDetails = e.response.text[:200]
		# Translators: Error message for HTTP failures. {code} is the HTTP status code, {reason} is the status message, and {details} is the error body.
		raise ApiResponseError(
			_("Service returned an error: {code} {reason}. Details: {details}").format(
				code=statusCode,
				reason=e.response.reason,
				details=errorDetails,
			),
		) from None
