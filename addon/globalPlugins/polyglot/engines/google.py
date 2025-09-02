# -*- coding: utf-8 -*-

from ..engine import BaseHttpEngine
from ..exceptions import EngineError
from .. import languages
import urllib.request
import urllib.parse
import json
from logHandler import log
import addonHandler

addonHandler.initTranslation()

class GoogleTranslateEngine(BaseHttpEngine):
    id = "google"
    name = _("Google Translate (key-free)")

    BASE_URL = "https://translate.googleapis.com"
    MIRROR_URL = "https://translate.googleapis.mirror.nvdadr.com"

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh-CN'

    def get_config_spec(self) -> list[dict]:
        spec = super().get_config_spec()
        spec.extend([
            {'id': 'use_mirror', 'label': _('Use mirror server (translate.googleapis.mirror.nvdadr.com)'), 'type': 'checkbox', 'default': False}
        ])
        return spec

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

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        base_url = self.MIRROR_URL if config.get('use_mirror', False) else self.BASE_URL
        url = (f"{base_url}/translate_a/single?client=gtx&sl={lang_from}&tl={lang_to}&dt=t"
               f"&q={urllib.parse.quote(text)}")
        return {
            'method': 'GET',
            'url': url
        }

    def _parse_response(self, response_body: str) -> dict:
        data = json.loads(response_body)
        if not data or not data[0]:
            raise ValueError("No translation found in response.")
        translated_text = "".join(item[0] for item in data[0] if item[0])
        detected_lang = data[2] if len(data) > 2 and isinstance(data[2], str) else None
        return {
            'translation': translated_text,
            'lang_detected': detected_lang
        }