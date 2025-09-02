# -*- coding: utf-8 -*-

import addonHandler
import html
import json
from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError, AuthenticationError
from .. import languages
from logHandler import log

addonHandler.initTranslation()

class GoogleHQApiError(ApiResponseError):
    pass

class GoogleHQTranslateEngine(BaseHttpEngine):
    id = "google_hq"
    name = _("Google Translate (HQ)")

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh-CN'

    def get_supported_languages(self) -> dict:
        supported_codes = [
            "auto", "af", "sq", "ar", "hy", "az", "eu", "be", "bn", "bs", "bg",
            "ca", "ceb", "ny", "zh-CN", "zh-TW", "co", "hr", "cs", "da", "nl",
            "en", "eo", "et", "tl", "fi", "fr", "fy", "gl", "ka", "de", "el",
            "gu", "ht", "ha", "haw", "he", "hi", "hmn", "hu", "is", "ig", "id",
            "ga", "it", "ja", "jw", "kn", "kk", "km", "ko", "ku", "ky", "lo",
            "la", "lv", "lt", "lb", "mk", "mg", "ms", "ml", "mt", "mi", "mr",
            "mn", "my", "ne", "no", "ps", "fa", "pl", "pt", "pa", "ro", "ru",
            "sm", "gd", "sr", "st", "sn", "sd", "si", "sk", "sl", "so", "es",
            "su", "sw", "sv", "tg", "ta", "te", "th", "tr", "uk", "ur", "uz",
            "vi", "cy", "xh", "yi", "yo", "zu"
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        spec = super().get_config_spec()
        spec.extend([
            {'id': 'apiKey', 'label': _('API Key'), 'type': 'password', 'default': ''},
            {
                'id': 'custom_url',
                'label': _('Endpoint URL'),
                'type': 'text',
                'default': 'https://translate-pa.googleapis.com/v1/translateHtml'
            }
        ])
        return spec

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        api_key = config.get('apiKey', '').strip()
        if not api_key:
            raise AuthenticationError(_("API Key for Google Translate (HQ) is not configured."))

        url = config.get('custom_url', 'https://translate-pa.googleapis.com/v1/translateHtml').strip()

        body_data = [
            [[text], lang_from, lang_to],
            "wt_lib"
        ]

        final_url = f"{url}?key={api_key}"

        headers = {
            'Content-Type': 'application/json+protobuf',
            'User-Agent': 'Mozilla/5.0'
        }

        return {
            'method': 'POST',
            'url': final_url,
            'headers': headers,
            'data': json.dumps(body_data).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        """
        Parses the simple, nested array response returned by the endpoint
        when receiving a protobuf-style request.
        Expected format: [["Translated text..."], ["detected_lang_code"]]
        """
        try:
            data = json.loads(response_body)
        except json.JSONDecodeError:
            raise GoogleHQApiError(_("Failed to parse API response."))

        try:
            raw_translated_text = data[0][0]
            translated_text = html.unescape(raw_translated_text)
        except (IndexError, TypeError):
            if isinstance(data, dict) and 'error' in data:
                error_msg = data['error'].get('message', 'Unknown API error')
                raise GoogleHQApiError(error_msg)
            log.error(f"Could not parse Google HQ response. Raw: {response_body}")
            raise GoogleHQApiError(_("Invalid API response or no translation text included."))
        detected_lang = None
        if len(data) > 1 and isinstance(data[1], list) and data[1]:
            detected_lang = data[1][0]
        return {
            'translation': translated_text,
            'lang_detected': detected_lang
        }