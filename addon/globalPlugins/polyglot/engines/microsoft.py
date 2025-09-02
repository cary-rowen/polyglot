# -*- coding: utf-8 -*-

import json
import time
import urllib.parse
from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError, AuthenticationError, EngineError
from .. import languages
from logHandler import log
import addonHandler

try:
    import requests
except ImportError:
    requests = None

addonHandler.initTranslation()

class MicrosoftApiError(ApiResponseError):
    """Custom exception for Microsoft Translator API errors."""
    pass

class MicrosoftTranslateEngine(BaseHttpEngine):
    """
    An engine for Microsoft Translator, simulating requests from the Edge browser.
    This engine does not require a user-provided API key. It fetches a temporary
    authentication token automatically.
    """
    id = "microsoft"
    name = _("Microsoft Translator (key-free)")

    # Class-level cache for the authentication token
    _token_cache = {
        "token": None,
        "expiry": 0
    }

    @property
    def auto_detect_code(self) -> str | None:
        # The API expects an empty string for auto-detection
        return ''

    @property
    def default_target_language(self) -> str:
        return 'zh-Hans' # Microsoft's code for Simplified Chinese

    def get_supported_languages(self) -> dict:
        supported_codes = [
            '', 'zh-Hans', 'zh-Hant', 'en', 'ja', 'ko', 'fr', 'es', 'ru',
            'de', 'it', 'pt', 'ar', 'th', 'vi'
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        """This engine does not require any specific configuration."""
        return super().get_config_spec()

    def _get_auth_token(self, config: dict) -> str:
        """
        Fetches or returns a cached authentication token from Microsoft's auth service.
        The token is typically valid for 10 minutes.
        """
        # Check if we have a valid, non-expired token
        if self._token_cache["token"] and self._token_cache["expiry"] > time.time():
            return self._token_cache["token"]

        if not requests:
            raise EngineError("The 'requests' library is required for this engine.")

        log.info("Microsoft Translator: Fetching new authentication token.")
        url = "https://edge.microsoft.com/translate/auth"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        }

        proxy_mode = config.get('proxyMode', 'system')
        proxies_dict = {"http": None, "https": None} if proxy_mode == 'none' else None
        timeout_int = int(config.get('timeout', '15'))

        try:
            response = requests.get(url, headers=headers, proxies=proxies_dict, timeout=timeout_int)
            response.raise_for_status()
            token = response.text

            # Cache the token and set its expiry time (e.g., 9 minutes to be safe)
            self._token_cache["token"] = token
            self._token_cache["expiry"] = time.time() + 9 * 60

            return token
        except Exception as e:
            log.error("Failed to fetch Microsoft Translator auth token.", exc_info=True)
            # Clear cache on failure
            self._token_cache["token"] = None
            self._token_cache["expiry"] = 0
            raise AuthenticationError(_("Could not get Microsoft Translator authentication token.")) from e

    def translate(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        """
        Overrides the base translate method to handle the two-step token authentication.
        """
        try:
            # Step 1: Get the authentication token
            auth_token = self._get_auth_token(config)

            # Step 2: Build and send the translation request
            params = self._build_request_params(text, lang_from, lang_to, config, auth_token)

            proxy_mode = config.get('proxyMode', 'system')
            proxies_dict = {"http": None, "https": None} if proxy_mode == 'none' else None
            timeout_int = int(config.get('timeout', '15'))

            # Use requests directly to avoid complexity with our network wrapper for this flow
            response = requests.post(
                url=params['url'],
                headers=params['headers'],
                data=params['data'],
                proxies=proxies_dict,
                timeout=timeout_int
            )
            response.raise_for_status()
            response_body = response.text

            log.debug(f"Engine '{self.id}' raw response: {response_body}")
            return self._parse_response(response_body)
        except requests.exceptions.HTTPError as e:
            # If the error is 401 Unauthorized, our token has likely expired. Clear it.
            if e.response.status_code == 401:
                log.warning("Microsoft Translator returned 401 Unauthorized. Clearing token cache.")
                self._token_cache["token"] = None
                self._token_cache["expiry"] = 0
            # Re-raise as our custom exception type
            raise MicrosoftApiError(f"HTTP Error: {e.response.status_code}") from e
        except Exception as e:
            log.error(f"An unexpected error occurred in '{self.id}' engine.", exc_info=True)
            if isinstance(e, (ApiResponseError, EngineError)):
                 raise
            raise EngineError(_("An unknown error occurred during translation.")) from e

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict, auth_token: str) -> dict:
        """
        Builds the request dictionary for the actual translation API call.
        """
        # Map our standard language codes to Microsoft's specific codes
        lang_map = {
            'zh-CN': 'zh-Hans',
            'zh-TW': 'zh-Hant',
        }
        final_lang_from = lang_map.get(lang_from, lang_from)
        final_lang_to = lang_map.get(lang_to, lang_to)

        query_params = {
            'from': final_lang_from,
            'to': final_lang_to,
            'api-version': '3.0',
        }
        url = f"https://api-edge.cognitive.microsofttranslator.com/translate?{urllib.parse.urlencode(query_params)}"

        body = [{"Text": text}]

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {auth_token}'
        }

        return {
            'url': url,
            'headers': headers,
            'data': json.dumps(body).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        """Parses the JSON response from the Microsoft Translator API."""
        try:
            data = json.loads(response_body)
        except json.JSONDecodeError:
            raise MicrosoftApiError(_("Failed to parse response from Microsoft Translator."))

        try:
            # The response is a list of translation results
            first_result = data[0]
            translation_obj = first_result['translations'][0]

            translated_text = translation_obj['text']
            detected_lang_obj = first_result.get('detectedLanguage')

            detected_lang = None
            if detected_lang_obj:
                detected_lang = detected_lang_obj.get('language')

            return {
                'translation': translated_text,
                'lang_detected': detected_lang
            }
        except (KeyError, IndexError, TypeError):
            if 'error' in data:
                error_msg = data['error'].get('message', 'Unknown API error')
                raise MicrosoftApiError(error_msg)

            log.error(f"Could not parse Microsoft Translator response. Raw: {response_body}")
            raise MicrosoftApiError(_("Invalid API response or no translation result included."))