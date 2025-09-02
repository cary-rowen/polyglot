# -*- coding: utf-8 -*-

from ..engine import BaseHttpEngine
from ..exceptions import ApiResponseError, AuthenticationError
import addonHandler
import json
from logHandler import log
from typing import Dict, Any

addonHandler.initTranslation()

class DeepLApiError(ApiResponseError):
    pass

class DeepLEngine(BaseHttpEngine):
    id = "deepl"
    name = _("DeepL")

    BASE_URL_FREE = "https://api-free.deepl.com/v2/translate"
    BASE_URL_PRO = "https://api.deepl.com/v2/translate"
    FORMALITY_SUPPORTED_LANGUAGES = {"DE", "IT", "ES", "PL", "RU", "FR", "PT-PT", "NL", "JA", "PT-BR"}

    @property
    def auto_detect_code(self) -> str | None:
        return 'auto'

    @property
    def default_target_language(self) -> str:
        return 'ZH'

    def get_config_spec(self) -> list[dict]:
        spec = super().get_config_spec()
        spec.extend([
            {'id': 'apiKey', 'label': _('API Key (Auth Key)'), 'type': 'password', 'default': ''},
            {'id': 'useFreeApi', 'label': _('Use Free API'), 'type': 'checkbox', 'default': True},
            {'id': 'context', 'label': _('Context (optional):'), 'type': 'text', 'default': ''},
            {
                'id': 'splitSentences', 'label': _('Sentence splitting mode:'), 'type': 'choice',
                'choices': {'on': _("On (split at punctuation and newlines)"), 'off': _("Off (no splitting)"), 'nonewlines': _("Only at punctuation"),},
                'default': 'on'
            },
            { 'id': 'preserveFormatting', 'label': _('Preserve formatting'), 'type': 'checkbox', 'default': False },
            {
                'id': 'formality', 'label': _('Formality (for supported languages):'), 'type': 'choice',
                'choices': {'default': _("Default"), 'more': _("More formal"), 'less': _("Less formal"),},
                'default': 'default'
            },
            {
                'id': 'modelType', 'label': _('Model type:'), 'type': 'choice',
                'choices': { 'latency_optimized': _("Speed-optimized (default)"), 'quality_optimized': _("Quality-optimized"), 'prefer_quality_optimized': _("Prefer quality-optimized model"),},
                'default': 'latency_optimized'
            },
        ])
        return spec

    def get_ui_states(self, all_configs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        states = super().get_ui_states(all_configs)
        target_lang = all_configs.get('langTo', '')
        is_formality_supported = target_lang.upper() in self.FORMALITY_SUPPORTED_LANGUAGES
        states['formality'] = {'enabled': is_formality_supported}
        return states

    def get_supported_languages(self) -> dict:
        return {
            "auto": "Auto-detect", "BG": "Bulgarian", "CS": "Czech", "DA": "Danish", "DE": "German", "EL": "Greek", "EN": "English", "ES": "Spanish", "ET": "Estonian",
            "FI": "Finnish", "FR": "French", "HU": "Hungarian", "ID": "Indonesian", "IT": "Italian", "JA": "Japanese", "KO": "Korean", "LT": "Lithuanian",
            "LV": "Latvian", "NB": "Norwegian (Bokmål)", "NL": "Dutch", "PL": "Polish", "PT": "Portuguese", "RO": "Romanian", "RU": "Russian", "SK": "Slovak",
            "SL": "Slovenian", "SV": "Swedish", "TR": "Turkish", "UK": "Ukrainian", "ZH": "Chinese"
        }

    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        api_key = config.get('apiKey', '').strip()
        if not api_key: raise AuthenticationError(_("DeepL API Key (Auth Key) is not configured."))
        use_free_api = config.get('useFreeApi', True)
        if not use_free_api and api_key.endswith(":fx"):
            raise AuthenticationError(_("You have selected the Pro API, but the provided key is for the Free API. Please check 'Use Free API' in settings."))

        base_url = self.BASE_URL_FREE if use_free_api else self.BASE_URL_PRO
        headers = {'Authorization': f'DeepL-Auth-Key {api_key}', 'Content-Type': 'application/json', 'User-Agent': 'NVDA-ModernTranslate-Plugin/1.0'}
        lines = [line for line in text.splitlines() if line.strip()] or [text]
        payload = { 'text': lines, 'target_lang': lang_to.upper() }

        if lang_from != 'auto': payload['source_lang'] = lang_from.upper()
        if config.get('context', '').strip(): payload['context'] = config['context']

        split_map = {'on': '1', 'off': '0', 'nonewlines': 'nonewlines'}
        payload['split_sentences'] = split_map.get(config.get('splitSentences', 'nonewlines'))

        if config.get('preserveFormatting'): payload['preserve_formatting'] = True

        formality = config.get('formality')
        if formality and formality != 'default':
            if lang_to.upper() in self.FORMALITY_SUPPORTED_LANGUAGES: payload['formality'] = formality
            else: log.warning(f"DeepL: Formality '{formality}' not supported for target '{lang_to}'. Ignoring.")

        model_type = config.get('modelType')
        if model_type and model_type != 'latency_optimized': payload['model_type'] = model_type

        return {'method': 'POST', 'url': base_url, 'headers': headers, 'data': json.dumps(payload).encode('utf-8')}

    def _parse_response(self, response_body: str) -> dict:
        data = json.loads(response_body)
        if 'message' in data: raise DeepLApiError(data['message'])
        if not data.get('translations'): raise ApiResponseError(_("Invalid API response or no translation result included."))

        translated_text = "\n".join(item.get('text', '') for item in data['translations'])
        detected_lang = data['translations'][0].get('detected_source_language') if data['translations'] else None

        return {'translation': translated_text, 'lang_detected': detected_lang}