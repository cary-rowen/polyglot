# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import threading

from collections.abc import Callable
from typing import Any

from logHandler import log

from ..common import config
from ..common.cache import TranslationCache
from ..common.exceptions import EngineError, SilentTranslationCancel
from ..services import engineManager


class TranslationTask(threading.Thread):
	"""Run one cancellable translation request and cache its successful result."""

	# Annotating instance variables at the class level
	engineId: str
	text: str
	langFrom: str
	langTo: str
	cache: TranslationCache
	onComplete: Callable[[dict[str, Any]], None]
	isManual: bool
	engineConfig: dict[str, Any]
	_isCancelled: bool
	_lock: threading.Lock

	def __init__(
		self,
		engineId: str,
		text: str,
		langFrom: str,
		langTo: str,
		cache: TranslationCache,
		onComplete: Callable[[dict[str, Any]], None],
		isManual: bool,
		engineConfig: dict[str, Any],
	) -> None:
		"""Initialize a daemon task for one engine, language pair, and source text."""
		super().__init__(daemon=True)
		self.engineId = engineId
		self.text = text
		self.langFrom = langFrom
		self.langTo = langTo
		self.cache = cache
		self.onComplete = onComplete
		self.isManual = isManual
		self.engineConfig = engineConfig
		self._isCancelled = False
		self._lock = threading.Lock()
		log.debug(f"TranslationTask created for engine '{self.engineId}', isManual={self.isManual}.")

	def cancel(self) -> None:
		"""Mark the task for cooperative cancellation."""
		with self._lock:
			log.debug("Cancelling translation task.")
			self._isCancelled = True

	def isCancelled(self) -> bool:
		"""Return whether cancellation has been requested."""
		with self._lock:
			return self._isCancelled

	def run(self) -> None:
		"""Execute translation, optional auto-swap, caching, and completion callback."""
		result: dict[str, str | Exception | None] = {"translation": None, "error": None}
		try:
			if self.isCancelled():
				return
			engine = engineManager.getEngineById(self.engineId)
			engineConfig = config.decryptConfigSecrets(
				self.engineId,
				self.engineConfig,
				engine.getConfigSpec(),
			)
			autoDetectCode = engine.autoDetectCode
			firstResult = engine.translate(
				self.text,
				self.langFrom,
				self.langTo,
				engineConfig,
				isCancelled=self.isCancelled,
			)
			if self.isCancelled():
				return
			langDetected = firstResult.get("langDetected")
			result.update(firstResult)
			shouldSwap = (
				self.isManual
				and engineConfig.get("enableAutoSwap")
				and self.langFrom == autoDetectCode
				and isinstance(langDetected, str)
				and engine.areLanguagesEquivalent(langDetected, self.langTo)
			)
			finalTargetLang = self.langTo
			if shouldSwap:
				swapLang = engineConfig.get("swapLanguage")
				if swapLang and swapLang != self.langTo:
					finalTargetLang = swapLang
					assert langDetected is not None
					secondResult = engine.translate(
						self.text,
						langDetected,
						swapLang,
						engineConfig,
						isCancelled=self.isCancelled,
					)
					if self.isCancelled():
						return
					result.update(secondResult)
			finalTranslation = result.get("translation")
			if finalTranslation and isinstance(finalTranslation, str) and not result.get("noCache"):
				sourceLangForCache = langDetected or self.langFrom
				if sourceLangForCache != autoDetectCode:
					if isinstance(sourceLangForCache, str):
						specificKey = self.cache.buildKey(
							sourceLangForCache,
							finalTargetLang,
							self.text,
						)
						self.cache.set(specificKey, finalTranslation)
				if autoDetectCode is not None and self.langFrom == autoDetectCode:
					autoKey = self.cache.buildKey(autoDetectCode, self.langTo, self.text)
					self.cache.set(autoKey, finalTranslation)
		except EngineError as e:
			result["error"] = e
		except SilentTranslationCancel:
			result["cancelled"] = True
		except Exception as e:
			log.error("An unexpected error occurred inside TranslationTask.run.", exc_info=True)
			result["error"] = e
		if not self.isCancelled():
			self.onComplete(result)
