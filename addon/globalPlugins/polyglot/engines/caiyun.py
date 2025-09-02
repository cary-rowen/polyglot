# -*- coding: utf-8 -*-

import json
from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError, AuthenticationError
from .. import languages
import addonHandler

addonHandler.initTranslation()

class CaiyunApiError(ApiResponseError):
    """Custom exception for Caiyun-specific API errors."""
    pass

class CaiyunTranslateEngine(BaseHttpEngine):
    """
    An engine for Caiyun AI Translation.
    Requires a token for authentication.
    """
    id = "caiyun"
    name = _("Caiyun")

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh'

    def get_supported_languages(self) -> dict:
        supported_codes = [
            "auto", "zh", "zh-Hant", "en", "ja", "ko", "de", "es",
            "fr", "it", "pt", "ru", "tr", "vi"
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        """Defines the configuration options for this engine."""
        spec = super().get_config_spec()
        spec.extend([
            {'id': 'token', 'label': _('Authentication Token'), 'type': 'password', 'default': ''},
        ])
        return spec

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        """Builds the request dictionary for the Caiyun API call."""
        token = config.get('token', '').strip()
        if not token:
            raise AuthenticationError(_("Authentication Token for Caiyun is not configured."))

        url = 'https://api.interpreter.caiyunai.com/v1/translator'

        body = {
            "source": [text], # API expects a list of strings
            "trans_type": f"{lang_from}2{lang_to}",
            "request_id": "translate-nvda-add-on",
            "detect": True if lang_from == 'auto' else False
        }

        headers = {
            'Content-Type': 'application/json',
            'x-authorization': f'token {token}'
        }

        return {
            'method': 'POST',
            'url': url,
            'headers': headers,
            'data': json.dumps(body).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        """Parses the JSON response from the Caiyun API."""
        data = json.loads(response_body)

        # Check for business logic errors first
        if 'message' in data:
            raise CaiyunApiError(data['message'])
        translated_list = data.get('target')
        if translated_list and isinstance(translated_list, list) and translated_list[0] is not None:
            detected_lang = None
            # Parse the detected source language from the trans_type field
            trans_type = data.get('trans_type')
            if trans_type and '2' in trans_type:
                # E.g. "en2zh" -> "en"
                detected_lang = trans_type.split('2')[0]

            return {
                'translation': translated_list[0],
                'lang_detected': detected_lang
            }
        else:
            raise CaiyunApiError(_("Invalid API response or no translation result included."))
