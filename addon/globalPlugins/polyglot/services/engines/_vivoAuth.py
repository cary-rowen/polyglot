# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
import random
import string
import time
import urllib.parse

import addonHandler
from logHandler import log

from ...common import network
from ...common.exceptions import (
	AuthenticationError,
	NetworkConnectionError,
	ResponseParsingError,
)
from ._nvdacn import NVDACN_API_URL

addonHandler.initTranslation()

__all__ = ["genSignHeaders"]

_VIVO_APP_ID = "3046775094"
_AUTH_REQUEST_TIMEOUT = 3  # Seconds for a single authentication request attempt


def _genNonce(length: int = 8) -> str:
	"""Generate a random alphanumeric nonce of the requested length."""
	chars = string.ascii_lowercase + string.digits
	return "".join(random.choice(chars) for _ in range(length))


def _genCanonicalQueryString(params: dict) -> str:
	"""Create a stable, URL-encoded query string for signing."""
	if not params:
		return ""
	sortedParams = sorted(params.items())
	return "&".join(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}" for k, v in sortedParams)


def _fetchSignatureFromService(nvdacnUser: str, nvdacnPass: str, signingStringBytes: bytes) -> str:
	"""Fetch the Vivo signature from the NVDACN API."""
	apiParams = {"user": nvdacnUser, "pass": nvdacnPass, "name": "vivo", "action": "signature"}
	url = f"{NVDACN_API_URL}?{urllib.parse.urlencode(apiParams)}"

	try:
		responseBody = network.sendRequest(
			method="POST",
			url=url,
			data=signingStringBytes,
			timeout=_AUTH_REQUEST_TIMEOUT,
		)

		result = json.loads(responseBody)

		if result.get("code") == 200 and "data" in result:
			return result["data"]
		else:
			errorMessage = result.get("data", "Unknown API error")
			log.error(
				"NVDACN signature API returned a business error (code %s).",
				result.get("code"),
			)
			raise AuthenticationError(f"NVDACN API Error: {errorMessage} (Code: {result.get('code')})")

	except NetworkConnectionError:
		raise AuthenticationError(_("Could not connect to the authentication server.")) from None
	except (json.JSONDecodeError, KeyError, TypeError):
		log.error("NVDACN signature API returned an invalid response.")
		raise ResponseParsingError(_("Invalid response from the authentication server.")) from None


def genSignHeaders(nvdacnUser: str, nvdacnPass: str, method: str, uri: str, query: dict) -> dict:
	"""
	Generate the authentication headers required by the Vivo API.

	This is the main public function of the module.
	"""
	method = str(method).upper()
	timestamp = str(int(time.time()))
	nonce = _genNonce()
	# Step 1: Prepare the canonical string to be signed.
	canonicalQueryString = _genCanonicalQueryString(query)
	signedHeadersString = (
		f"x-ai-gateway-app-id:{_VIVO_APP_ID}\nx-ai-gateway-timestamp:{timestamp}\nx-ai-gateway-nonce:{nonce}"
	)
	signingString = (
		f"{method}\n{uri}\n{canonicalQueryString}\n{_VIVO_APP_ID}\n{timestamp}\n{signedHeadersString}"
	)
	signingStringBytes = signingString.encode("utf-8")
	# Step 2: Fetch the signature from the remote service.
	signature = _fetchSignatureFromService(nvdacnUser, nvdacnPass, signingStringBytes)
	# Step 3: Assemble the final headers dictionary.
	return {
		"X-AI-GATEWAY-APP-ID": _VIVO_APP_ID,
		"X-AI-GATEWAY-TIMESTAMP": timestamp,
		"X-AI-GATEWAY-NONCE": nonce,
		"X-AI-GATEWAY-SIGNED-HEADERS": "x-ai-gateway-app-id;x-ai-gateway-timestamp;x-ai-gateway-nonce",
		"X-AI-GATEWAY-SIGNATURE": signature,
	}
