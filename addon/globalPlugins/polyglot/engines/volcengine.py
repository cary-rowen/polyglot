# -*- coding: utf-8 -*-

import json
from ..engine import BaseHttpEngine
from .. import languages
from ..exceptions import ApiResponseError
import addonHandler

addonHandler.initTranslation()

class VolcengineApiError(ApiResponseError):
    pass

class VolcengineTranslateEngine(BaseHttpEngine):
    id = "volcengine"
    name = _("Volcengine (key-free)")

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh'

    def get_supported_languages(self) -> dict:
        supported_codes = [
            'auto', 'zh', 'en', 'ja', 'ko', 'fr', 'es', 'ru', 'de', 'it',
            'pt', 'vi', 'id', 'th'
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        return super().get_config_spec()

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        url = "https://translate.volcengine.com/crx/translate/v1"

        source_language = lang_from if lang_from else 'auto'

        body = {
            "text": text,
            "source_language": source_language,
            "target_language": lang_to,
        }

        headers = {
            'Content-Type': 'application/json',
            'Referer': 'https://translate.volcengine.com/'
        }

        return {
            'method': 'POST',
            'url': url,
            'headers': headers,
            'data': json.dumps(body).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        data = json.loads(response_body)

        translated_text = data.get('translation')

        if translated_text is not None:
            detected_lang = data.get('detected_language')
            return {
                'translation': translated_text,
                'lang_detected': detected_lang
            }
        else:
            error_message = data.get('message', _("Invalid API response or no translation result included."))
            raise VolcengineApiError(error_message)