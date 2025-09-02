# -*- coding: utf-8 -*-

import hmac
import hashlib
import json
import time
from datetime import datetime
import addonHandler
from logHandler import log

from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError, AuthenticationError
from .. import languages

addonHandler.initTranslation()

class TencentApiError(ApiResponseError):
    pass

class TencentTranslateEngine(BaseHttpEngine):
    id = "tencent"
    name = _("Tencent Translate")

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'zh'

    def get_supported_languages(self) -> dict:
        supported_codes = [
            "auto", "zh", "zh-TW", "en", "ja", "ko", "fr", "es", "ru", "de",
            "it", "tr", "pt", "vi", "id", "th", "ms", "ar", "hi"
        ]
        return languages.get_language_dict_for_codes(supported_codes)

    def get_config_spec(self) -> list[dict]:
        spec = super().get_config_spec()
        spec.extend([
            {'id': 'secretId', 'label': _('Secret ID'), 'type': 'text', 'default': ''},
            {'id': 'secretKey', 'label': _('Secret Key'), 'type': 'password', 'default': ''},
            {
                'id': 'region',
                'label': _('Region:'),
                'type': 'choice',
                'choices': {
                    'ap-beijing': _("North China (Beijing)"),
                    'ap-guangzhou': _("South China (Guangzhou)"),
                    'ap-shanghai': _("East China (Shanghai)"),
                    'ap-hongkong': _("Hong Kong, Macao and Taiwan (Hong Kong, China)"),
                    'ap-singapore': _("Southeast Asia-Pacific (Singapore)"),
                    'na-ashburn': _("US East (Ashburn)"),
                },
                'default': 'ap-beijing'
            },
        ])
        return spec

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        secret_id = config.get('secretId')
        secret_key = config.get('secretKey')
        if not secret_id or not secret_key:
            raise AuthenticationError(_("Secret ID and Secret Key must be provided."))

        region = config.get('region', 'ap-beijing')
        endpoint = f'tmt.{region}.tencentcloudapi.com'
        service = 'tmt'
        action = 'TextTranslate'
        version = '2018-03-21'
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')

        body = {
            'SourceText': text,
            'Source': lang_from,
            'Target': lang_to,
            'ProjectId': 0,
        }
        payload_str = json.dumps(body)
        hashed_request_payload = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
        http_request_method = 'POST'
        canonical_uri = '/'
        canonical_query_string = ''
        canonical_headers = f'content-type:application/json\nhost:{endpoint}\n'
        signed_headers = 'content-type;host'

        canonical_request = (
            f'{http_request_method}\n{canonical_uri}\n{canonical_query_string}\n'
            f'{canonical_headers}\n{signed_headers}\n{hashed_request_payload}'
        )

        algorithm = 'TC3-HMAC-SHA256'
        hashed_canonical_request = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        credential_scope = f'{date}/{service}/tc3_request'
        string_to_sign = f'{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}'

        def sha256_hmac(message, secret):
            return hmac.new(secret, message, digestmod=hashlib.sha256).digest()

        secret_date = sha256_hmac(date.encode('utf-8'), ('TC3' + secret_key).encode('utf-8'))
        secret_service = sha256_hmac(service.encode('utf-8'), secret_date)
        secret_signing = sha256_hmac(b'tc3_request', secret_service)
        signature = hmac.new(secret_signing, string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()

        authorization = (
            f'{algorithm} Credential={secret_id}/{credential_scope}, '
            f'SignedHeaders={signed_headers}, Signature={signature}'
        )

        headers = {
            'Authorization': authorization,
            'Content-Type': 'application/json',
            'Host': endpoint,
            'X-TC-Action': action,
            'X-TC-Timestamp': str(timestamp),
            'X-TC-Version': version,
            'X-TC-Region': region,
        }

        return {
            'method': 'POST',
            'url': f'https://{endpoint}',
            'headers': headers,
            'data': payload_str.encode('utf-8')
        }

    def _parse_response(self, response_body: str) -> dict:
        data = json.loads(response_body)
        response = data.get('Response', {})

        if 'Error' in response and response['Error']:
            error = response['Error']
            error_code = error.get('Code', 'N/A')
            error_message = error.get('Message', _('Unknown API error'))
            log.error(f"Tencent API Error: Code={error_code}, Message={error_message}")

            if "AuthFailure" in error_code:
                raise AuthenticationError(f"{_('Authentication failed')}: {error_message} (Code: {error_code})")
            else:
                raise TencentApiError(f"{error_message} (Code: {error_code})")

        translated_text = response.get('TargetText')
        detected_lang = response.get('Source')

        if translated_text is None:
            raise TencentApiError(_("Invalid API response or no translation result included."))

        return {
            'translation': translated_text,
            'lang_detected': detected_lang
        }