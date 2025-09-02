# -*- coding: utf-8 -*-

# Copyright (C) 2025, Cary-rowen from NVDACN
#
# This module handles the generation of authentication headers required
# for the VIVO API. It interfaces with the NVDACN API to securely
# obtain a signature without exposing the private APP_KEY on the client-side.

import json
import random
import string
import time
import urllib.parse
from logHandler import log

from .. import network
from ..exceptions import (
    AuthenticationError,
    NetworkConnectionError,
    ResponseParsingError,
)

__all__ = ['gen_sign_headers']

NVDACN_API_URL = 'https://nvdacn.com/api/'
VIVO_APP_ID = "3046775094"
AUTH_REQUEST_TIMEOUT = 3  # Seconds for a single authentication request attempt

def _gen_nonce(length: int = 8) -> str:
    """Generates a random alphanumeric string of a given length."""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def _gen_canonical_query_string(params: dict) -> str:
    """Creates a sorted, URL-encoded query string for signature consistency."""
    if not params:
        return ''
    sorted_params = sorted(params.items())
    return "&".join(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}" for k, v in sorted_params)

@network.retry_on_network_error(attempts=3, delay=0.5, backoff=2)
def _fetch_signature_from_service(nvdacn_user: str, nvdacn_pass: str, signing_string_bytes: bytes) -> str:
    """
    Fetches the signature from the NVDACN API using the robust network module.
    This function benefits from the centralized retry logic.
    """
    api_params = {
        'user': nvdacn_user,
        'pass': nvdacn_pass,
        'name': 'vivo',
        'action': 'signature'
    }
    url = f"{NVDACN_API_URL}?{urllib.parse.urlencode(api_params)}"

    log.debug("Requesting Vivo signature from NVDACN API for user: %s", nvdacn_user)

    try:
        response_body = network.send_request(
            method='POST',
            url=url,
            data=signing_string_bytes,
            timeout=AUTH_REQUEST_TIMEOUT
        )

        result = json.loads(response_body)

        if result.get('code') == 200 and 'data' in result:
            log.info("Successfully fetched Vivo signature for user %s.", nvdacn_user)
            return result['data']
        else:
            error_message = result.get('data', 'Unknown API error')
            log.error(
                "NVDACN signature API returned a business error for user %s: %s (Code: %s)",
                nvdacn_user, error_message, result.get('code')
            )
            raise AuthenticationError(f"NVDACN API Error: {error_message} (Code: {result.get('code')})")

    except NetworkConnectionError as e:
        log.error("A network error occurred while fetching Vivo signature for user: %s.", nvdacn_user, exc_info=True)
        raise AuthenticationError(_("Could not connect to the authentication server.")) from e
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log.error(
            "Invalid response from NVDACN API: %s",
            response_body.decode('utf-8', errors='ignore'),
            exc_info=True
        )
        raise ResponseParsingError(_("Invalid response from the authentication server.")) from e

def gen_sign_headers(nvdacn_user: str, nvdacn_pass: str, method: str, uri: str, query: dict) -> dict:
    """
    Generates the complete set of authentication headers for the VIVO API.

    This is the main public function of the module.
    """
    method = str(method).upper()
    timestamp = str(int(time.time()))
    nonce = _gen_nonce()
    # Step 1: Prepare the canonical string to be signed.
    canonical_query_string = _gen_canonical_query_string(query)
    signed_headers_string = (
        f'x-ai-gateway-app-id:{VIVO_APP_ID}\n'
        f'x-ai-gateway-timestamp:{timestamp}\n'
        f'x-ai-gateway-nonce:{nonce}'
    )
    signing_string = (
        f'{method}\n'
        f'{uri}\n'
        f'{canonical_query_string}\n'
        f'{VIVO_APP_ID}\n'
        f'{timestamp}\n'
        f'{signed_headers_string}'
    )
    signing_string_bytes = signing_string.encode('utf-8')
    # Step 2: Fetch the signature from the remote service.
    signature = _fetch_signature_from_service(nvdacn_user, nvdacn_pass, signing_string_bytes)
    # Step 3: Assemble the final headers dictionary.
    return {
        'X-AI-GATEWAY-APP-ID': VIVO_APP_ID,
        'X-AI-GATEWAY-TIMESTAMP': timestamp,
        'X-AI-GATEWAY-NONCE': nonce,
        'X-AI-GATEWAY-SIGNED-HEADERS': "x-ai-gateway-app-id;x-ai-gateway-timestamp;x-ai-gateway-nonce",
        'X-AI-GATEWAY-SIGNATURE': signature
    }