# -*- coding: utf-8 -*-

from collections.abc import Callable
from typing import Any

import api
import queueHandler
import ui
from logHandler import log

from ..common import config
from ..common.cache import TranslationCache
from ..common.exceptions import EngineError
from ..services import engine_manager
from .task import TranslationTask
from ..common import cues
from ..common.cues import CueType

OnSuccessCallback = Callable[[str], None] | None


class TranslationManager:
	# Annotations for instance variables defined and managed by this class
	cache: TranslationCache
	last_translation: str | None
	consecutive_failures: int
	_current_task: TranslationTask | None
	auto_translate_enabled: bool

	def __init__(self) -> None:
		super().__init__()
		self.cache = TranslationCache()
		self.last_translation = None
		self.consecutive_failures = 0
		self._current_task = None
		self.auto_translate_enabled = False

	def clear_cache(self) -> None:
		log.info("Clearing cache via TranslationManager.")
		self.cache.clear()

	def toggle_auto_translate(self) -> bool:
		self.reset_consecutive_failures()
		self.auto_translate_enabled = not self.auto_translate_enabled
		log.info(f"Runtime auto-translate toggled to: {self.auto_translate_enabled}")
		return self.auto_translate_enabled

	def swap_languages(self) -> tuple[bool, str]:
		"""
		Swaps the source and target languages in the configuration.

		Returns:
			A tuple containing a boolean for success and a user-facing message.
		"""
		conf = config.get_config()
		engine_id = conf["engine"]
		try:
			current_engine = engine_manager.get_engine_by_id(engine_id)
		except (ValueError, NotImplementedError):
			return (False, _("Invalid engine configuration."))
		if engine_id not in conf["engines"]:
			conf["engines"][engine_id] = {}
		engine_conf = conf["engines"][engine_id]
		current_from = engine_conf.get("langFrom", current_engine.default_source_language)
		current_to = engine_conf.get("langTo", current_engine.default_target_language)
		auto_detect_code = current_engine.auto_detect_code
		if current_from == auto_detect_code:
			log.warning(f"Language swap aborted. Cannot set '{auto_detect_code}' as target language.")
			return (False, _("Swap failed: 'Auto-detect' cannot be the target language."))
		engine_conf["langFrom"] = current_to
		engine_conf["langTo"] = current_from
		log.info(
			f"Languages swapped for engine '{engine_id}'. New config: From={current_to}, To={current_from}"
		)
		message = _("Languages swapped: from {source} to {target}").format(
			source=current_to, target=current_from
		)
		return (True, message)

	def get_current_language_announcement(self) -> str:
		"""
		Gets a formatted string of the current source and target languages for announcement.
		"""
		conf = config.get_config()
		engine_id = conf["engine"]
		engine_conf = conf["engines"].get(engine_id, {})
		try:
			current_engine = engine_manager.get_engine_by_id(engine_id)
			lang_from = engine_conf.get("langFrom", current_engine.default_source_language)
			lang_to = engine_conf.get("langTo", current_engine.default_target_language)
			return _("From {source} to {target}").format(source=lang_from, target=lang_to)
		except (ValueError, NotImplementedError):
			log.warning(
				f"Could not get language announcement. Engine '{engine_id}' may be invalid or not fully implemented."
			)
			return _("Languages not configured or current engine is invalid")

	def terminate_all_tasks(self) -> None:
		if self._current_task and self._current_task.is_alive():
			log.info("Terminating active translation task.")
			self._current_task.cancel()
		cues.stop_periodic_cue()
		self._current_task = None

	def reset_consecutive_failures(self) -> None:
		log.debug("Consecutive failure count has been reset manually.")
		self.consecutive_failures = 0

	def get_current_languages(self) -> tuple[str | None, str | None]:
		"""
		Gets the currently configured source and target languages.

		Returns:
			A tuple of (lang_from, lang_to), or (None, None) on error.
		"""
		conf = config.get_config()
		engine_id = conf["engine"]
		engine_conf = conf["engines"].get(engine_id, {})
		try:
			current_engine = engine_manager.get_engine_by_id(engine_id)
			lang_from = engine_conf.get("langFrom", current_engine.default_source_language)
			lang_to = engine_conf.get("langTo", current_engine.default_target_language)
			return (lang_from, lang_to)
		except (ValueError, NotImplementedError):
			log.warning(f"Could not get current languages. Engine '{engine_id}' may be invalid.")
			return (None, None)

	def get_reverse_languages(self) -> tuple[str | None, str | None, str | None]:
		"""
		Checks if languages can be reversed and returns them if possible.

		Returns:
			A tuple of (new_lang_from, new_lang_to, error_message).
			On success, error_message will be None.
			On failure, the languages will be None.
		"""
		source_lang, target_lang = self.get_current_languages()
		if not source_lang or not target_lang:
			return None, None, _("Languages not configured, cannot reverse.")
		conf = config.get_config()  # Manager 内部使用自己的 config 是完全合理的
		engine_id = conf["engine"]
		try:
			current_engine = engine_manager.get_engine_by_id(engine_id)
			if source_lang == current_engine.auto_detect_code:
				return None, None, _("Reverse failed: 'Auto-detect' cannot be the target language.")
			return target_lang, source_lang, None
		except (ValueError, NotImplementedError):
			return None, None, _("Current translation engine is invalid.")

	def request_translation(
		self,
		text: str | None,
		is_manual: bool = True,
		show_status: bool = True,
		allow_copy: bool = True,
		on_success: OnSuccessCallback = None,
		lang_from: str | None = None,
		lang_to: str | None = None,
	) -> None:
		if not text or not text.strip():
			if is_manual:
				ui.message(_("Nothing to translate"))
			return
		conf = config.get_config()
		engine_id = conf["engine"]
		try:
			current_engine = engine_manager.get_engine_by_id(engine_id)
		except (ValueError, NotImplementedError):
			log.error(
				f"Selected engine '{engine_id}' is not available or not fully implemented.", exc_info=True
			)
			if is_manual:
				ui.message(
					_("Error: Selected engine '{engine}' is unavailable or not configured.").format(
						engine=engine_id
					)
				)
			return
		if engine_id not in conf["engines"]:
			conf["engines"][engine_id] = {}
		engine_config = conf["engines"][engine_id].dict()
		try:
			if lang_from is None:
				lang_from = engine_config.get("langFrom", current_engine.default_source_language)
			if lang_to is None:
				lang_to = engine_config.get("langTo", current_engine.default_target_language)
		except NotImplementedError:
			log.error(
				f"Engine '{engine_id}' is missing required default language implementations.", exc_info=True
			)
			if is_manual:
				ui.message(_("Error: Engine '{engine}' is not configured.").format(engine=engine_id))
			return
		if is_manual and show_status:
			cues.sound.play(CueType.START)
		if self._current_task and self._current_task.is_alive():
			log.info("A new translation request is overriding the previous one. Cancelling.")
			self._current_task.cancel()
			cues.stop_periodic_cue()
		cache_key = self.cache.build_key(lang_from, lang_to, text)
		cached_result = self.cache.get(cache_key)
		if cached_result:
			log.info(f"Cache hit for key {cache_key}. Returning cached result.")
			self._on_translation_complete(
				{"translation": cached_result, "error": None},
				is_manual=is_manual,
				allow_copy=allow_copy,
				on_success=on_success,
			)
			return
		if is_manual and show_status:
			cues.sound.start_periodic(
				CueType.WAITING,
				interval_ms=1200,
				delay_ms=600,
			)

		def callback(result: dict[str, Any]) -> None:
			self._on_translation_complete(
				result, is_manual=is_manual, allow_copy=allow_copy, on_success=on_success
			)

		task = TranslationTask(
			engine_id=engine_id,
			text=text,
			lang_from=lang_from,
			lang_to=lang_to,
			cache=self.cache,
			on_complete=callback,
			is_manual=is_manual,
			engine_config=engine_config,
		)
		self._current_task = task
		task.start()

	def _on_translation_complete(
		self, result: dict[str, Any], is_manual: bool, allow_copy: bool, on_success: OnSuccessCallback
	) -> None:
		cues.stop_periodic_cue()

		def task() -> None:
			error = result.get("error")
			if error:
				prefix = _("Translation failed: ")
				error_message = (
					f"{prefix}{error}"
					if isinstance(error, EngineError)
					else f"{prefix}{_('An unknown error occurred')}"
				)
				ui.message(error_message)
				if not is_manual:
					self.consecutive_failures += 1
					if self.consecutive_failures >= 3:
						log.warning("Disabling auto-translation due to 3 consecutive failures.")
						self.auto_translate_enabled = False
						self.consecutive_failures = 0
						queueHandler.queueFunction(
							queueHandler.eventQueue,
							ui.message,
							_("Auto-translation disabled due to repeated failures."),
						)
			else:
				self.consecutive_failures = 0
				translation = result["translation"]
				log.info(f"Translation successful. Result: '{translation[:50]}...'")
				self.last_translation = translation
				if on_success:
					on_success(translation)
				else:
					ui.message(translation)
				if is_manual and allow_copy and config.get_config()["copyResult"]:
					api.copyToClip(translation)

		queueHandler.queueFunction(queueHandler.eventQueue, task)
