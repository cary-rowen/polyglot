# -*- coding: utf-8 -*-

import json
import urllib.parse
import uuid
from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError
from .. import languages
import addonHandler

addonHandler.initTranslation()

class YandexApiError(ApiResponseError):
    """Custom exception for Yandex-specific API errors."""
    pass

class YandexTranslateEngine(BaseHttpEngine):
    """
    An engine that uses the public Yandex Translate API.
    This mimics the behavior of their Android client and requires no API key.
    """
    id = "yandex"
    name = _("Yandex Translate")

    @property
    def auto_detect_code(self) -> str | None:
        return ''

    @property
    def default_target_language(self) -> str:
        return 'zh'

    @property
    def reports_detected_language(self) -> bool:
        # The API response does not include the detected source language.
        return False

    def get_supported_languages(self) -> dict:
        supported_codes = [
            '', 'zh', 'en', 'ja', 'ko', 'fr', 'es', 'ru', 'de', 'it',
            'tr', 'pt', 'vi', 'id', 'th', 'ms', 'ar', 'hi', 'no', 'fa',
            'sv', 'pl', 'nl', 'uk', 'he'
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        """This engine does not require any specific configuration."""
        return super().get_config_spec()

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        """Builds the request dictionary for the Yandex API call."""
        base_url = 'https://translate.yandex.net/api/v1/tr.json/translate'

        # Build query parameters for the URL
        query_params = {
            'id': str(uuid.uuid4()).replace('-', '') + '-0-0',
            'srv': 'android',
        }
        full_url = f"{base_url}?{urllib.parse.urlencode(query_params)}"

        # Build the form data for the request body
        form_data = {
            'source_lang': lang_from,
            'target_lang': lang_to,
            'text': text,
        }

        return {
            'method': 'POST',
            'url': full_url,
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
            'data': urllib.parse.urlencode(form_data).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        """Parses the JSON response from the Yandex API."""
        data = json.loads(response_body)

        translated_text_list = data.get('text')

        if translated_text_list and isinstance(translated_text_list, list) and translated_text_list[0]:
            return {
                'translation': translated_text_list[0],
                'lang_detected': None  # API doesn't provide this
            }
        else:
            # Handle potential API errors if they are structured differently
            error_code = data.get('code')
            error_message = data.get('message', 'Unknown API error')
            if error_code:
                raise YandexApiError(f"{error_message} (Code: {error_code})")
            raise YandexApiError(_("Invalid API response or no translation result included."))