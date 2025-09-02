# -*- coding: utf-8 -*-

import json
import urllib.parse
from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError
from .. import languages
import addonHandler

addonHandler.initTranslation()

class LingvaApiError(ApiResponseError):
    """Custom exception for Lingva-specific API errors."""
    pass

class LingvaTranslateEngine(BaseHttpEngine):
    """
    An engine that uses the Lingva Translate public API.
    Lingva is an alternative front-end for Google Translate.
    """
    id = "lingva"
    name = _("Lingva Translate")

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh'

    @property
    def reports_detected_language(self) -> bool:
        # The API response does not include the detected source language.
        return False

    def get_supported_languages(self) -> dict:
        supported_codes = [
            'auto', 'zh', 'zh_HANT', 'en', 'ja', 'ko', 'fr', 'es', 'ru',
            'de', 'it', 'tr', 'pt', 'vi', 'id', 'th', 'ms', 'ar',
            'hi', 'mn', 'km', 'no', 'fa', 'sv', 'pl', 'nl', 'uk', 'he'
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        """This engine does not require any specific configuration."""
        return super().get_config_spec()

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        """Builds the request dictionary for the Lingva API call."""
        # The API has a quirk where forward slashes in the text cause issues.
        # The JS code replaces them with '@@' before encoding.
        processed_text = text.replace('/', '@@')
        encoded_text = urllib.parse.quote(processed_text)

        url = f"https://lingva.pot-app.com/api/v1/{lang_from}/{lang_to}/{encoded_text}"

        return {
            'method': 'GET',
            'url': url,
            # No headers or data needed for this GET request
        }

    def _parse_response(self, response_body: str) -> dict:
        """Parses the JSON response from the Lingva API."""
        try:
            data = json.loads(response_body)
        except json.JSONDecodeError:
            # Sometimes Lingva might return a non-JSON error for very long texts
            raise LingvaApiError(_("Service returned an invalid result (text may be too long)."))

        translation = data.get('translation')

        if translation:
            # Reverse the special character replacement from the request building step.
            final_translation = translation.replace('@@', '/')
            return {
                'translation': final_translation,
                'lang_detected': None # API doesn't provide this
            }
        else:
            error_info = data.get('error', 'Unknown API error')
            raise LingvaApiError(f"{error_info}")