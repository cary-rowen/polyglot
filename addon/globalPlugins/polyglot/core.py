# -*- coding: utf-8 -*-

import ui
import api
import queueHandler
from . import config
from .exceptions import EngineError
from logHandler import log
import threading
from . import engine_manager
from .engine import EngineError
from .cache import TranslationCache
from logHandler import log

class TranslationTask(threading.Thread):
    def __init__(self, engine_id, text, lang_from, lang_to, cache, on_complete, is_manual, engine_config):
        super().__init__(daemon=True)
        self.engine_id = engine_id
        self.text = text
        self.lang_from = lang_from
        self.lang_to = lang_to
        self.cache = cache
        self.on_complete = on_complete
        self.is_manual = is_manual
        self.engine_config = engine_config
        self._is_cancelled = False
        self._lock = threading.Lock()
        log.debug(f"TranslationTask created for engine '{self.engine_id}', is_manual={self.is_manual}.")

    def cancel(self):
        with self._lock:
            log.info(f"Cancelling translation task for text: '{self.text[:50]}...'")
            self._is_cancelled = True

    def is_cancelled(self):
        with self._lock:
            return self._is_cancelled

    def run(self):
        result = {'translation': None, 'error': None}
        try:
            if self.is_cancelled(): return
            engine = engine_manager.get_engine_by_id(self.engine_id)
            engine_config = self.engine_config
            auto_detect_code = engine.auto_detect_code
            first_result = engine.translate(self.text, self.lang_from, self.lang_to, engine_config)
            if self.is_cancelled(): return
            lang_detected = first_result.get('lang_detected')
            result.update(first_result)
            should_swap = (
                self.is_manual and
                engine_config.get('enableAutoSwap') and
                self.lang_from == auto_detect_code and
                lang_detected is not None and
                lang_detected == self.lang_to
            )
            final_target_lang = self.lang_to
            if should_swap:
                swap_lang = engine_config.get('swapLanguage')
                if swap_lang and swap_lang != self.lang_to:
                    final_target_lang = swap_lang
                    second_result = engine.translate(self.text, lang_detected, swap_lang, engine_config)
                    if self.is_cancelled(): return
                    result.update(second_result)
            final_translation = result.get('translation')
            if final_translation:
                source_lang_for_cache = lang_detected or self.lang_from
                if source_lang_for_cache != auto_detect_code:
                    specific_key = self.cache.build_key(source_lang_for_cache, final_target_lang, self.text)
                    self.cache.set(specific_key, final_translation)
                if self.lang_from == auto_detect_code:
                    auto_key = self.cache.build_key(auto_detect_code, self.lang_to, self.text)
                    self.cache.set(auto_key, final_translation)
        except EngineError as e:
            result['error'] = e
        except Exception as e:
            log.error("An unexpected error occurred inside TranslationTask.run.", exc_info=True)
            result['error'] = e
        if not self.is_cancelled():
            self.on_complete(result)


class TranslationManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self.cache = TranslationCache()
        self.last_translation = None
        self.consecutive_failures = 0
        self._current_task = None
        self.auto_translate_enabled = False
        self._initialized = True

    def clear_cache(self):
        log.info("Clearing cache via TranslationManager.")
        self.cache.clear()

    def toggle_auto_translate(self):
        self.reset_consecutive_failures()
        self.auto_translate_enabled = not self.auto_translate_enabled
        log.info(f"Runtime auto-translate toggled to: {self.auto_translate_enabled}")
        return self.auto_translate_enabled
    
    def swap_languages(self):
        conf = config.get_config()
        engine_id = conf['engine']
        try:
            current_engine = engine_manager.get_engine_by_id(engine_id)
        except (ValueError, NotImplementedError):
             return (False, _("Invalid engine configuration."))
        if engine_id not in conf['engines']:
            return (False, _("The current engine has no swappable languages."))
        engine_conf = conf['engines'][engine_id]
        current_from = engine_conf.get('langFrom', current_engine.default_source_language)
        current_to = engine_conf.get('langTo', current_engine.default_target_language)
        auto_detect_code = current_engine.auto_detect_code
        if current_from == auto_detect_code:
            log.warning(f"Language swap aborted. Cannot set '{auto_detect_code}' as target language.")
            return (False, _("Swap failed: 'Auto-detect' cannot be the target language."))
        engine_conf['langFrom'] = current_to
        engine_conf['langTo'] = current_from
        log.info(f"Languages swapped for engine '{engine_id}'. New config: From={current_to}, To={current_from}")
        message = _("Languages swapped: from {source} to {target}").format(source=current_to, target=current_from)
        return (True, message)

    def get_current_language_announcement(self):
        """
        Gets a formatted string of the current source and target languages for announcement.
        """
        conf = config.get_config()
        engine_id = conf['engine']
        engine_conf = conf['engines'].get(engine_id, {})
        try:
            current_engine = engine_manager.get_engine_by_id(engine_id)
            lang_from = engine_conf.get('langFrom', current_engine.default_source_language)
            lang_to = engine_conf.get('langTo', current_engine.default_target_language)
            return _("From {source} to {target}").format(source=lang_from, target=lang_to)
        except (ValueError, NotImplementedError):
            log.warning(f"Could not get language announcement. Engine '{engine_id}' may be invalid or not fully implemented.")
            return _("Languages not configured or current engine is invalid")

    def terminate_all_tasks(self):
        if self._current_task and self._current_task.is_alive():
            log.info("Terminating active translation task.")
            self._current_task.cancel()
        self._current_task = None

    def reset_consecutive_failures(self):
        log.debug("Consecutive failure count has been reset manually.")
        self.consecutive_failures = 0

    def request_translation(self, text, is_manual=True, show_status=True, allow_copy=True, on_success=None):
        if not text or not text.strip():
            if is_manual: ui.message(_("Nothing to translate"))
            return
        conf = config.get_config()
        engine_id = conf['engine']
        try:
            current_engine = engine_manager.get_engine_by_id(engine_id)
        except (ValueError, NotImplementedError):
            log.error(f"Selected engine '{engine_id}' is not available or not fully implemented.", exc_info=True)
            if is_manual:
                ui.message(_("Error: Selected engine '{engine}' is unavailable or not configured.").format(engine=engine_id))
            return
        engine_config = conf['engines'][engine_id].dict()
        try:
            lang_from = engine_config.get('langFrom', current_engine.default_source_language)
            lang_to = engine_config.get('langTo', current_engine.default_target_language)
        except NotImplementedError:
             log.error(f"Engine '{engine_id}' is missing required default language implementations.", exc_info=True)
             if is_manual: ui.message(_("Error: Engine '{engine}' is not configured.").format(engine=engine_id))
             return
        if is_manual and show_status:
            ui.message(_("Translating..."))
        if self._current_task and self._current_task.is_alive():
            log.info("A new translation request is overriding the previous one. Cancelling.")
            self._current_task.cancel()
        cache_key = self.cache.build_key(lang_from, lang_to, text)
        cached_result = self.cache.get(cache_key)
        if cached_result:
            log.info(f"Cache hit for key {cache_key}. Returning cached result.")
            self._on_translation_complete(
                {'translation': cached_result, 'error': None},
                is_manual=is_manual,
                allow_copy=allow_copy,
                on_success=on_success
            )
            return
        callback = lambda result: self._on_translation_complete(
            result, is_manual=is_manual, allow_copy=allow_copy, on_success=on_success
        )
        task = TranslationTask(
            engine_id=engine_id, text=text, lang_from=lang_from, lang_to=lang_to,
            cache=self.cache, on_complete=callback, is_manual=is_manual, engine_config=engine_config
        )
        self._current_task = task
        task.start()

    def _on_translation_complete(self, result, is_manual, allow_copy, on_success):
        def task():
            error = result.get('error')
            if error:
                prefix = _("Translation failed: ")
                error_message = f"{prefix}{error}" if isinstance(error, EngineError) else f"{prefix}{_('An unknown error occurred')}"
                ui.message(error_message)
                if not is_manual:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= 3:
                        log.warning("Disabling auto-translation due to 3 consecutive failures.")
                        self.auto_translate_enabled = False
                        self.consecutive_failures = 0
                        queueHandler.queueFunction(queueHandler.eventQueue, ui.message, _("Auto-translation disabled due to repeated failures."))
            else:
                self.consecutive_failures = 0
                translation = result['translation']
                log.info(f"Translation successful. Result: '{translation[:50]}...'")
                self.last_translation = translation
                if on_success:
                    on_success(translation)
                else:
                    ui.message(translation)
                if is_manual and allow_copy and config.get_config()['copyResult']:
                    api.copyToClip(translation)
        queueHandler.queueFunction(queueHandler.eventQueue, task)

manager = TranslationManager()