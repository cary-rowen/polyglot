# -*- coding: utf-8 -*-

from ..engine import BaseHttpEngine
from ..exceptions import EngineError
from .. import languages
import urllib.parse
import json
import random
import hashlib
import addonHandler
from logHandler import log

addonHandler.initTranslation()

class BaiduApiError(EngineError):
    pass

class BaiduTranslateEngine(BaseHttpEngine):
    id = "baidu"
    name = _("Baidu Translate")

    API_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    ERROR_CODES = {
        "52001": _("Request timed out"), "52002": _("System error"),
        "52003": _("Unauthorized user. Please check your App ID or if the service is enabled."),
        "54000": _("Required parameter is missing"), "54001": _("Signature error. Please check your App Secret."),
        "54003": _("Access frequency limited"), "54004": _("Insufficient account balance"),
        "54005": _("Frequent long query requests"), "58000": _("Invalid client IP"),
        "58001": _("Translation direction not supported (may be due to insufficient permissions)"),
        "58002": _("Service is currently disabled"), "58003": _("IP has been blocked"),
        "90107": _("Authentication failed or has not taken effect"), "20003": _("Request content poses a security risk"),
    }

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh'

    def get_config_spec(self) -> list[dict]:
        spec = super().get_config_spec()
        # Add engine-specific settings.
        spec.extend([
            {'id': 'appId', 'label': 'App ID', 'type': 'text', 'default': ''},
            {'id': 'appSecret', 'label': 'App Secret', 'type': 'password', 'default': ''},
            {
                'id': 'useTermbase',
                'label': _("Use custom terminology (requires authentication and configuration on the platform)"),
                'type': 'checkbox',
                'default': False
            },
        ])
        return spec

    def get_supported_languages(self) -> dict:
        supported_codes = [
            "auto", "zh", "en", "yue", "wyw", "jp", "kor", "fra", "spa", "th",
            "ara", "ru", "pt", "de", "it", "el", "nl", "pl", "bul", "est",
            "dan", "fin", "cs", "rom", "slo", "swe", "hu", "cht", "vie"
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def _make_sign(self, text, salt, app_id, app_secret):
        sign_str = app_id + text + str(salt) + app_secret
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        app_id = config.get('appId')
        app_secret = config.get('appSecret')
        if not app_id or not app_secret:
            raise BaiduApiError(_("App ID and App Secret are required."))

        salt = random.randint(32768, 65536)
        sign = self._make_sign(text, salt, app_id, app_secret)

        if lang_from in ("zh-CN", "zh-TW"): lang_from = "zh"
        if lang_to == "zh-CN": lang_to = "zh"
        if lang_to == "zh-TW": lang_to = "cht"

        params = {
            'q': text, 'from': lang_from, 'to': lang_to, 'appid': app_id,
            'salt': salt, 'sign': sign
        }
        if config.get('useTermbase', False):
            params['needIntervene'] = 1

        return {
            'method': 'POST',
            'url': self.API_URL,
            'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
            'data': urllib.parse.urlencode(params).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        result = json.loads(response_body)

        if 'error_code' in result:
            error_code = result['error_code']
            message = self.ERROR_CODES.get(error_code, result.get('error_msg', _('Unknown API error')))
            raise BaiduApiError(f"{message} (Code: {error_code})")

        translated_text = "\n".join(item['dst'] for item in result['trans_result'])
        detected_lang = result.get('from')

        return {
            'translation': translated_text,
            'lang_detected': detected_lang
        }