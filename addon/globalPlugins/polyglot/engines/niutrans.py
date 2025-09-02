# -*- coding: utf-8 -*-

import json
from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError, AuthenticationError
from .. import languages
import addonHandler

addonHandler.initTranslation()

class NiutransApiError(ApiResponseError):
    """Custom exception for Niutrans-specific API errors."""
    pass

class NiutransTranslateEngine(BaseHttpEngine):
    """
    An engine for Niutrans.
    Requires an API key for authentication.
    """
    id = "niutrans"
    name = _("Niutrans")

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh'

    def get_supported_languages(self) -> dict:
        supported_codes = [
            'auto', 'zh', 'cht', 'yue', 'en', 'ja', 'ko', 'fr', 'es', 'ru',
            'de', 'it', 'tr', 'pt', 'vi', 'id', 'th', 'ms', 'ar', 'hi',
            'mn', 'mo', 'km', 'nb', 'nn', 'fa', 'sv', 'pl', 'nl', 'uk', 'he'
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        """Defines the configuration options for this engine."""
        spec = super().get_config_spec()
        spec.extend([
            {'id': 'apikey', 'label': _('API Key'), 'type': 'password', 'default': ''},
            {'id': 'https', 'label': _('Use HTTPS connection'), 'type': 'checkbox', 'default': True},
        ])
        return spec

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        """Builds the request dictionary for the Niutrans API call."""
        api_key = config.get('apikey', '').strip()
        if not api_key:
            raise AuthenticationError(_("API Key for Niutrans is not configured."))

        protocol = 'https' if config.get('https', True) else 'http'
        url = f"{protocol}://api.niutrans.com/NiuTransServer/translation"

        body = {
            "from": lang_from,
            "to": lang_to,
            "apikey": api_key,
            "src_text": text
        }

        return {
            'method': 'POST',
            'url': url,
            'headers': {'Content-Type': 'application/json'},
            'data': json.dumps(body).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        """Parses the JSON response from the Niutrans API."""
        data = json.loads(response_body)

        # Check for business logic errors first
        if 'error_code' in data:
            error_code = data.get('error_code')
            error_msg = data.get('error_msg', 'Unknown API error')
            raise NiutransApiError(f"{error_msg} (Code: {error_code})")

        translated_text = data.get('tgt_text')

        if translated_text is not None:
            # The API might also report the detected source language
            detected_lang = data.get('from')
            return {
                'translation': translated_text.strip(),
                'lang_detected': detected_lang
            }
        else:
            raise NiutransApiError(_("Invalid API response or no translation result included."))