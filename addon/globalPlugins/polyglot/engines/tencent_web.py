# -*- coding: utf-8 -*-

import json
from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError
from .. import languages
import addonHandler

addonHandler.initTranslation()

class TencentWebApiError(ApiResponseError):
    pass

class TencentWebTranslateEngine(BaseHttpEngine):
    id = "tencent_web"
    name = _("Tencent Translate (Web, key-free)")

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh'

    @property
    def reports_detected_language(self) -> bool:
        """
        This engine does not support source language detection.
        """
        return False

    def get_supported_languages(self) -> dict:
        supported_codes = [
            'auto', 'zh', 'en', 'ja', 'ko', 'fr', 'es', 'ru', 'de', 'it',
            'ms', 'th', 'vi'
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        return super().get_config_spec()

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        url = "https://transmart.qq.com/api/imt"

        body = {
            "header": {
                "fn": "auto_translation",
                "client_key": "browser-chrome-110.0.0-Mac OS-df4bd4c5-a65d-44b2-a40f-42f34f3535f2-1677486696487"
            },
            "type": "plain",
            "model_category": "normal",
            "source": { "text_list": [text], "lang": lang_from },
            "target": { "lang": lang_to }
        }

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
            'Referer': 'https://transmart.qq.com/zh-CN/index'
        }

        return {
            'method': 'POST',
            'url': url,
            'headers': headers,
            'data': json.dumps(body).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        """Parses the JSON response from the Tencent Transmart API."""
        data = json.loads(response_body)
        if 'auto_translation' in data and data['auto_translation'] and isinstance(data['auto_translation'], list):
            translated_text = data['auto_translation'][0]
            return {
                'translation': translated_text,
                'lang_detected': None
            }
        else:
            if 'header' in data and 'ret_code' in data['header'] and data['header']['ret_code'] != 'succ':
                error_msg = data['header'].get('msg', 'Unknown API error')
                raise TencentWebApiError(error_msg)
            raise TencentWebApiError(_("Invalid API response or no translation result included."))