# -*- coding: utf-8 -*-

from ..engine import BaseHttpEngine
from .. import languages
from ..exceptions import EngineError, ApiResponseError, AuthenticationError, NetworkConnectionError
from .import _vivo_auth as vivo_auth
import urllib.parse
import json
import uuid
import addonHandler
from logHandler import log

addonHandler.initTranslation()

class VivoTranslateEngine(BaseHttpEngine):
    id = "vivo"
    name = _("VIVO Translate")

    API_URL = "https://api-ai.vivo.com.cn/translation/query/self"
    ERROR_CODES = {
        10000: _("Server error"),
        20000: _("Invalid request parameters"),
    }

    @property
    def auto_detect_code(self) -> str | None:
        """This engine does not support automatic language detection."""
        return None

    @property
    def default_source_language(self) -> str:
        return 'en'

    @property
    def default_target_language(self) -> str:
        return 'zh-CHS'

    def get_config_spec(self) -> list[dict]:
        spec = super().get_config_spec()
        spec.extend([
            {'id': 'nvdacnUser', 'label': _('NVDACN Username'), 'type': 'text', 'default': ''},
            {'id': 'nvdacnPass', 'label': _('NVDACN Password'), 'type': 'password', 'default': ''},
        ])
        return spec

    def get_supported_languages(self) -> dict:
        supported_codes = ["zh-CHS", "en", "ja", "ko"]
        return languages.get_language_dict_for_codes(supported_codes)

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        nvdacn_user = config.get('nvdacnUser')
        nvdacn_pass = config.get('nvdacnPass')
        if not nvdacn_user or not nvdacn_pass:
            raise AuthenticationError(_("NVDACN username and password must be provided in settings."))

        uri = '/translation/query/self'
        try:
            headers = vivo_auth.gen_sign_headers(nvdacn_user, nvdacn_pass, 'POST', uri, {})
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        except NetworkConnectionError as e:
            log.error("Failed to connect to NVDACN authentication server.", exc_info=True)
            raise EngineError(_("Could not connect to the NVDACN authentication server to get a signature. Please check your network connection or try again later.")) from e
        except AuthenticationError as e:
            raise EngineError(_("Authentication failed: {error}").format(error=str(e))) from e
        except Exception as e:
            raise EngineError(_("An unknown error occurred while generating authentication info.")) from e

        body_params = {
            'from': lang_from, 'to': lang_to, 'text': text, 'app': 'test',
            'requestId': str(uuid.uuid4())
        }
        return {
            'method': 'POST',
            'url': self.API_URL,
            'headers': headers,
            'data': urllib.parse.urlencode(body_params).encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        result = json.loads(response_body)
        if result.get('code') == 0 and 'data' in result:
            translated_text = result['data'].get('translation')
            if translated_text is None:
                raise ApiResponseError(_("API response successful but did not contain a translation result."))
            return {
                'translation': translated_text,
                'lang_detected': None
            }
        else:
            error_code = result.get('code')
            error_message = self.ERROR_CODES.get(error_code, result.get('msg', _('Unknown API error')))
            raise ApiResponseError(f"{error_message} (Code: {error_code or 'N/A'})")