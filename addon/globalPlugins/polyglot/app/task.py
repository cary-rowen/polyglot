# -*- coding: utf-8 -*-

import threading

from collections.abc import Callable
from typing import Any

from logHandler import log

from ..common.cache import TranslationCache
from ..common.exceptions import EngineError
from ..services import engine_manager


class TranslationTask(threading.Thread):
	# Annotating instance variables at the class level
	engine_id: str
	text: str
	lang_from: str
	lang_to: str
	cache: TranslationCache
	on_complete: Callable[[dict[str, Any]], None]
	is_manual: bool
	engine_config: dict[str, Any]
	_is_cancelled: bool
	_lock: threading.Lock

	def __init__(
		self,
		engine_id: str,
		text: str,
		lang_from: str,
		lang_to: str,
		cache: TranslationCache,
		on_complete: Callable[[dict[str, Any]], None],
		is_manual: bool,
		engine_config: dict[str, Any],
	) -> None:
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

	def cancel(self) -> None:
		with self._lock:
			log.info(f"Cancelling translation task for text: '{self.text[:50]}...'")
			self._is_cancelled = True

	def is_cancelled(self) -> bool:
		with self._lock:
			return self._is_cancelled

	def run(self) -> None:
		result: dict[str, str | Exception | None] = {"translation": None, "error": None}
		try:
			if self.is_cancelled():
				return
			engine = engine_manager.get_engine_by_id(self.engine_id)
			engine_config = self.engine_config
			auto_detect_code = engine.auto_detect_code
			first_result = engine.translate(self.text, self.lang_from, self.lang_to, engine_config)
			if self.is_cancelled():
				return
			lang_detected = first_result.get("lang_detected")
			result.update(first_result)
			should_swap = (
				self.is_manual
				and engine_config.get("enableAutoSwap")
				and self.lang_from == auto_detect_code
				and lang_detected is not None
				and lang_detected == self.lang_to
			)
			final_target_lang = self.lang_to
			if should_swap:
				swap_lang = engine_config.get("swapLanguage")
				if swap_lang and swap_lang != self.lang_to:
					final_target_lang = swap_lang
					assert lang_detected is not None
					second_result = engine.translate(self.text, lang_detected, swap_lang, engine_config)
					if self.is_cancelled():
						return
					result.update(second_result)
			final_translation = result.get("translation")
			if final_translation and isinstance(final_translation, str):
				source_lang_for_cache = lang_detected or self.lang_from
				if source_lang_for_cache != auto_detect_code:
					if isinstance(source_lang_for_cache, str):
						specific_key = self.cache.build_key(
							source_lang_for_cache, final_target_lang, self.text
						)
						self.cache.set(specific_key, final_translation)
				if self.lang_from == auto_detect_code:
					# Fix: Ensure `auto_detect_code` is a string before passing it to `build_key`.
					# This handles cases where an engine might not support auto-detection (`auto_detect_code` is None).
					if isinstance(auto_detect_code, str):
						auto_key = self.cache.build_key(auto_detect_code, self.lang_to, self.text)
						self.cache.set(auto_key, final_translation)
		except EngineError as e:
			result["error"] = e
		except Exception as e:
			log.error("An unexpected error occurred inside TranslationTask.run.", exc_info=True)
			result["error"] = e
		if not self.is_cancelled():
			self.on_complete(result)
