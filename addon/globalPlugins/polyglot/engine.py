# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
import json
from .exceptions import EngineError
from logHandler import log
import addonHandler
from typing import Dict, Any, OrderedDict

addonHandler.initTranslation()

class TranslationEngine(ABC):
    """
    Defines the abstract interface that all translation engines must implement.
    """
    @property
    @abstractmethod
    def id(self) -> str:
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def auto_detect_code(self) -> str | None:
        """
        Returns the language code this engine uses for "auto-detect".
        Subclasses must return None if not supported.
        """
        pass

    @property
    def supports_language_detection(self) -> bool:
        """A convenience property for readability, its behavior is derived from auto_detect_code."""
        return self.auto_detect_code is not None

    @property
    def reports_detected_language(self) -> bool:
        """Reports the ability to detect the source language. Defaults to whether language detection is supported."""
        return self.supports_language_detection

    @abstractmethod
    def get_config_spec(self) -> list[dict]:
        pass

    @abstractmethod
    def get_supported_languages(self) -> dict:
        pass

    @abstractmethod
    def translate(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        pass

    def get_ui_states(self, all_configs: Dict[str, Any]) -> Dict[str, Any]:
        return {}


class BaseHttpEngine(TranslationEngine):
    """
    Provides a common framework and rules for HTTP-based engines.
    """

    @property
    @abstractmethod
    def auto_detect_code(self) -> str | None:
        """
        This method remains abstract in BaseHttpEngine,
        forcing all concrete HTTP engines to implement it explicitly.
        """
        raise NotImplementedError(
            f"Translation engine '{self.id}' must explicitly implement the 'auto_detect_code' property in a subclass (return None if not supported)."
        )

    @property
    def default_source_language(self) -> str:
        """
        Provides an intelligent, conditional default source language.
        - If the engine supports language detection, it automatically uses its auto_detect_code.
        - If not, the subclass is forced to override this property and provide a specific language.
        """
        if self.supports_language_detection:
            return self.auto_detect_code
        raise NotImplementedError(
            f"Translation engine '{self.id}' does not support auto language detection, "
            "and must therefore explicitly override the 'default_source_language' property in a subclass."
        )
        
    @property
    @abstractmethod
    def default_target_language(self) -> str:
        """
        Forces all concrete HTTP engines to explicitly define their default target language.
        """
        raise NotImplementedError(
            f"Translation engine '{self.id}' must explicitly implement the 'default_target_language' property."
        )

    def get_config_spec(self) -> list[dict]:
        all_langs = self.get_supported_languages()
        auto_code = self.auto_detect_code
        
        from_choices = all_langs.copy()
        if not self.supports_language_detection and auto_code:
            from_choices.pop(auto_code, None)
            
        to_choices = all_langs.copy()
        if auto_code is not None:
            to_choices.pop(auto_code, None)
            
        spec = [
            {'id': 'langFrom', 'label': _("Source language:"), 'type': 'choice', 'choices': from_choices, 'default': self.default_source_language},
            {'id': 'langTo', 'label': _("Target language:"), 'type': 'choice', 'choices': to_choices, 'default': self.default_target_language}
        ]

        spec.extend([
            {
                'id': 'proxyMode',
                'label': _('Proxy mode:'),
                'type': 'choice',
                'choices': {
                    'system': _("Use system proxy settings"),
                    'none': _("Do not use proxy"),
                },
                'default': 'system'
            },
            {
                'id': 'timeout',
                'label': _('Request timeout:'),
                'type': 'spinctrl',
                'default': 15,
                'min': 1,
                'max': 60
            }
        ])

        if self.reports_detected_language:
            swap_choices = to_choices.copy()
            spec.extend([
                {'id': 'enableAutoSwap', 'label': _("Auto-swap if detected source matches target (source must be 'Auto-detect')"), 'type': 'checkbox', 'default': False},
                {'id': 'swapLanguage', 'label': _("Swap to language:"), 'type': 'choice', 'choices': swap_choices, 'default': ''}
            ])
        return spec

    def _get_filtered_choices(self, all_langs: dict, exclude_code: str = None, remove_auto: bool = False) -> dict:
        """A helper function to create a filtered dictionary of language options based on rules."""
        choices = all_langs.copy()
        if remove_auto and self.auto_detect_code is not None:
            choices.pop(self.auto_detect_code, None)
        if exclude_code:
            choices.pop(exclude_code, None)
        return choices

    def get_ui_states(self, all_configs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        states = super().get_ui_states(all_configs)
        all_langs = self.get_supported_languages()
        auto_code = self.auto_detect_code
        selected_from = all_configs.get('langFrom')
        selected_to = all_configs.get('langTo')
        # --- Generate language lists using the helper function ---
        # Target language (langTo): Always remove "auto-detect" and exclude the currently selected source language.
        valid_to_langs = self._get_filtered_choices(all_langs, exclude_code=selected_from, remove_auto=True)
        # Source language (langFrom): Exclude the currently selected target language.
        valid_from_langs = self._get_filtered_choices(all_langs, exclude_code=selected_to)
        # Special handling for the source list: only remove "auto-detect" if the engine does not support it.
        if not self.supports_language_detection and auto_code:
            valid_from_langs.pop(auto_code, None)
        states['langFrom'] = {'choices': valid_from_langs}
        states['langTo'] = {'choices': valid_to_langs}
        # --- Logic for auto-swap related controls ---
        if self.reports_detected_language:
            is_auto_from = selected_from == auto_code
            states['enableAutoSwap'] = {'visible': is_auto_from}
            is_swap_lang_visible = is_auto_from and all_configs.get('enableAutoSwap', False)
            # Swap-to language (swapLanguage): Rules are the same as for target language; exclude current target and "auto-detect".
            valid_swap_langs = self._get_filtered_choices(all_langs, exclude_code=selected_to, remove_auto=True)
            states['swapLanguage'] = {'visible': is_swap_lang_visible, 'choices': valid_swap_langs}
        return states

    @abstractmethod
    def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        pass

    @abstractmethod
    def _parse_response(self, response_body: str) -> dict:
        pass

    def translate(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
        from .network import send_request
        from .exceptions import ResponseParsingError
        try:
            params = self._build_request_params(text, lang_from, lang_to, config)
            log.debug(f"Engine '{self.id}' built request params: {params.get('method')} {params.get('url')}")
            proxy_mode = config.get('proxyMode', 'system')
            proxies_dict = None  # Default is None, which makes requests use system proxy settings.
            if proxy_mode == 'none':
                proxies_dict = {"http": None, "https": None}
            timeout_int = int(config.get('timeout', '15'))
            response_body = send_request(
                method=params.get('method', 'GET'), url=params['url'],
                headers=params.get('headers'), data=params.get('data'),
                timeout=timeout_int,
                proxies=proxies_dict
            )
            log.debug(f"Engine '{self.id}' raw response: {response_body}")
            return self._parse_response(response_body)
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON response from '{self.id}'.", exc_info=True)
            raise ResponseParsingError(_("Failed to parse response from translation service.")) from e
        except EngineError:
             raise
        except Exception as e:
            log.error(f"An unexpected error occurred in '{self.id}' engine.", exc_info=True)
            raise EngineError(_("An unknown error occurred during translation.")) from e