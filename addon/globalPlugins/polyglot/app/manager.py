# -*- coding: utf-8 -*-

from collections.abc import Callable
from typing import Any

import api
import queueHandler
from logHandler import log

from ..common import config
from ..common.cache import TranslationCache
from ..common.exceptions import EngineError
from ..common import languages
from ..services import engineManager
from .task import TranslationTask
from ..common import cues
from ..common.cues import CueType

OnSuccessCallback = Callable[[str], None] | None
OnErrorCallback = Callable[[str], None] | None


class TranslationManager:
	# Annotations for instance variables defined and managed by this class
	cache: TranslationCache
	lastTranslation: str | None
	consecutiveFailures: int
	_currentTask: TranslationTask | None
	isAutoTranslateEnabled: bool

	def __init__(self) -> None:
		super().__init__()
		self.cache = TranslationCache()
		self.lastTranslation = None
		self.consecutiveFailures = 0
		self._currentTask = None
		self.isAutoTranslateEnabled = False

	def clearCache(self) -> None:
		"""Clears all cached translation entries."""
		log.info("Clearing cache via TranslationManager.")
		self.cache.clear()

	def toggleAutoTranslate(self) -> bool:
		"""Toggles auto-translation on or off and returns the new state."""
		self.resetConsecutiveFailures()
		self.isAutoTranslateEnabled = not self.isAutoTranslateEnabled
		log.info(f"Runtime auto-translate toggled to: {self.isAutoTranslateEnabled}")
		return self.isAutoTranslateEnabled

	def swapLanguages(self) -> tuple[bool, str]:
		"""
		Swaps the source and target languages in the configuration.

		Returns:
			A tuple containing a boolean for success and a user-facing message.
		"""
		conf = config.getConfig()
		engineId = conf["engine"]
		try:
			currentEngine = engineManager.getEngineById(engineId)
		except (ValueError, NotImplementedError):
			return (False, _("Invalid engine configuration."))
		if engineId not in conf["engines"]:
			conf["engines"][engineId] = {}
		engineConf = conf["engines"][engineId]
		currentFrom = engineConf.get("langFrom", currentEngine.defaultSourceLanguage)
		currentTo = engineConf.get("langTo", currentEngine.defaultTargetLanguage)
		autoDetectCode = currentEngine.autoDetectCode
		if currentFrom == autoDetectCode:
			log.warning(f"Language swap aborted. Cannot set '{autoDetectCode}' as target language.")
			return (False, _("Swap failed: 'Auto-detect' cannot be the target language."))
		engineConf["langFrom"] = currentTo
		engineConf["langTo"] = currentFrom
		log.info(
			f"Languages swapped for engine '{engineId}'. New config: From={currentTo}, To={currentFrom}",
		)
		# Translators: A message indicating that the source and target languages have been swapped. {source} is the new source language, {target} is the new target language.
		message = _("Languages swapped: from {source} to {target}").format(
			source=currentTo,
			target=currentFrom,
		)
		return (True, message)

	def cycleLanguage(self, target: str, forward: bool) -> tuple[bool, str]:
		"""
		Cycles the source or target language for the current engine.
		The other side's language is excluded from the candidate list
		to prevent source and target from being set to the same language.

		Args:
			target: "source" or "target", indicating which language to cycle.
			forward: True to cycle forward, False to cycle backward.

		Returns:
			A tuple containing a boolean for success and a user-facing message.
		"""
		conf = config.getConfig()
		engineId = conf["engine"]
		try:
			currentEngine = engineManager.getEngineById(engineId)
		except (ValueError, NotImplementedError):
			return (False, _("Invalid engine configuration."))
		if engineId not in conf["engines"]:
			conf["engines"][engineId] = {}
		engineConf = conf["engines"][engineId]
		allLangs = currentEngine.getSupportedLanguages()
		autoCode = currentEngine.autoDetectCode
		if target == "source":
			configKey = "langFrom"
			defaultVal = currentEngine.defaultSourceLanguage
			otherCode = engineConf.get("langTo", currentEngine.defaultTargetLanguage)
			langCodes = [code for code in allLangs.keys() if code != otherCode]
		else:
			configKey = "langTo"
			defaultVal = currentEngine.defaultTargetLanguage
			otherCode = engineConf.get("langFrom", currentEngine.defaultSourceLanguage)
			exclude = {autoCode} if autoCode else set()
			if otherCode != autoCode:
				exclude.add(otherCode)
			langCodes = [code for code in allLangs.keys() if code not in exclude]
		if not langCodes:
			return (False, _("No languages available for cycling."))
		currentCode = engineConf.get(configKey, defaultVal)
		try:
			currentIndex = langCodes.index(currentCode)
		except ValueError:
			currentIndex = 0
		step = 1 if forward else -1
		newIndex = (currentIndex + step) % len(langCodes)
		newCode = langCodes[newIndex]
		engineConf[configKey] = newCode
		newName = languages.ALL_LANGUAGES.get(newCode, newCode)
		return (True, newName)

	def cycleEngine(self, forward: bool) -> tuple[bool, str]:
		"""
		Cycles the active translation engine.

		Args:
			forward: True to cycle forward, False to cycle backward.

		Returns:
			A tuple containing a boolean for success and a user-facing message.
		"""
		allEngines = engineManager.getAllEngines()
		if not allEngines:
			return (False, _("No translation engines available."))
		conf = config.getConfig()
		currentId = conf["engine"]
		newEngine = engineManager.getNextEnabledEngine(currentId, forward=forward)
		if not newEngine:
			return (False, _("No enabled translation engines available."))
		conf["engine"] = newEngine.id
		return (True, newEngine.name)

	def getCurrentEngineAndLanguageInfo(self) -> str:
		"""
		Gets a formatted string of the current engine and languages for announcement,
		"""
		conf = config.getConfig()
		engineId = conf["engine"]
		engineConf = conf["engines"].get(engineId, {})
		try:
			currentEngine = engineManager.getEngineById(engineId)
			langFromCode = engineConf.get("langFrom", currentEngine.defaultSourceLanguage)
			langToCode = engineConf.get("langTo", currentEngine.defaultTargetLanguage)
			langFromDesc = languages.ALL_LANGUAGES.get(langFromCode, langFromCode)
			langToDesc = languages.ALL_LANGUAGES.get(langToCode, langToCode)
			# Translators: Announcement of the current translation engine and languages. {engine} is the engine name, {source} is the source language, {target} is the target language.
			return _("{engine}, from {source} to {target}").format(
				engine=currentEngine.name,
				source=langFromDesc,
				target=langToDesc,
			)
		except (ValueError, NotImplementedError):
			log.warning(
				f"Could not get language announcement. Engine '{engineId}' may be invalid or not fully implemented.",
			)
			return _("Languages not configured or current engine is invalid")

	def terminateAllTasks(self) -> None:
		"""Cancels the active translation task, if any, and stops periodic cues."""
		if self._currentTask and self._currentTask.is_alive():
			log.info("Terminating active translation task.")
			self._currentTask.cancel()
		cues.stopPeriodicCue()
		self._currentTask = None

	def resetConsecutiveFailures(self) -> None:
		"""Resets the consecutive failure counter to zero."""
		log.debug("Consecutive failure count has been reset manually.")
		self.consecutiveFailures = 0

	def getCurrentLanguages(self) -> tuple[str | None, str | None]:
		"""
		Gets the currently configured source and target languages.

		Returns:
			A tuple of (langFrom, langTo), or (None, None) on error.
		"""
		conf = config.getConfig()
		engineId = conf["engine"]
		engineConf = conf["engines"].get(engineId, {})
		try:
			currentEngine = engineManager.getEngineById(engineId)
			langFrom = engineConf.get("langFrom", currentEngine.defaultSourceLanguage)
			langTo = engineConf.get("langTo", currentEngine.defaultTargetLanguage)
			return (langFrom, langTo)
		except (ValueError, NotImplementedError):
			log.warning(f"Could not get current languages. Engine '{engineId}' may be invalid.")
			return (None, None)

	def getReverseLanguages(self) -> tuple[str | None, str | None, str | None]:
		"""
		Checks if languages can be reversed and returns them if possible.

		Returns:
			A tuple of (new_lang_from, new_lang_to, errorMessage).
			On success, errorMessage will be None.
			On failure, the languages will be None.
		"""
		sourceLang, targetLang = self.getCurrentLanguages()
		if not sourceLang or not targetLang:
			return None, None, _("Languages not configured, cannot reverse.")
		conf = config.getConfig()
		engineId = conf["engine"]
		try:
			currentEngine = engineManager.getEngineById(engineId)
			if sourceLang == currentEngine.autoDetectCode:
				return None, None, _("Reverse failed: 'Auto-detect' cannot be the target language.")
			return targetLang, sourceLang, None
		except (ValueError, NotImplementedError):
			return None, None, _("Current translation engine is invalid.")

	def requestTranslation(
		self,
		text: str | None,
		isManual: bool = True,
		showStatus: bool = True,
		allowCopy: bool = True,
		onSuccess: OnSuccessCallback = None,
		onError: OnErrorCallback = None,
		langFrom: str | None = None,
		langTo: str | None = None,
	) -> None:
		if not text or not text.strip():
			if isManual:
				cues.Speech.message(_("Nothing to translate"))
			return
		conf = config.getConfig()
		engineId = conf["engine"]
		try:
			currentEngine = engineManager.getEngineById(engineId)
		except (ValueError, NotImplementedError):
			log.error(
				f"Selected engine '{engineId}' is not available or not fully implemented.",
				exc_info=True,
			)
			if isManual:
				# Translators: Error message when the selected translation engine is not available or not configured. {engine} is the internal ID of the engine.
				cues.Speech.message(
					_("Error: Selected engine '{engine}' is unavailable or not configured.").format(
						engine=engineId,
					),
				)
			return
		if engineId not in conf["engines"]:
			conf["engines"][engineId] = {}
		engineConfig = conf["engines"][engineId].dict()
		if not currentEngine.isEnabled(engineConfig):
			fallbackEngine = engineManager.getNextEnabledEngine(engineId)
			if not fallbackEngine:
				log.info(f"Selected engine '{engineId}' is disabled and no enabled fallback engine is available.")
				error = EngineError(_("No enabled translation engines available."))
				self._onTranslationComplete(
					{"translation": None, "error": error},
					isManual=isManual,
					allowCopy=allowCopy,
					onSuccess=onSuccess,
					onError=onError,
				)
				return
			log.info(f"Selected engine '{engineId}' is disabled; switching to '{fallbackEngine.id}'.")
			conf["engine"] = fallbackEngine.id
			engineId = fallbackEngine.id
			currentEngine = fallbackEngine
			if engineId not in conf["engines"]:
				conf["engines"][engineId] = {}
			engineConfig = conf["engines"][engineId].dict()
			langFrom = None
			langTo = None
		try:
			if langFrom is None:
				langFrom = engineConfig.get("langFrom", currentEngine.defaultSourceLanguage)
			if langTo is None:
				langTo = engineConfig.get("langTo", currentEngine.defaultTargetLanguage)
		except NotImplementedError:
			log.error(
				f"Engine '{engineId}' is missing required default language implementations.",
				exc_info=True,
			)
			if isManual:
				# Translators: Error message when the selected translation engine is not configured properly. {engine} is the internal ID of the engine.
				cues.Speech.message(_("Error: Engine '{engine}' is not configured.").format(engine=engineId))
			return
		if isManual and showStatus:
			cues.Sound.play(CueType.START)
		if self._currentTask and self._currentTask.is_alive():
			log.info("A new translation request is overriding the previous one. Cancelling.")
			self._currentTask.cancel()
			cues.stopPeriodicCue()
		cacheKey = self.cache.buildKey(langFrom, langTo, text)
		cachedResult = self.cache.get(cacheKey)
		if cachedResult:
			log.info(f"Cache hit for key {cacheKey}. Returning cached result.")
			self._onTranslationComplete(
				{"translation": cachedResult, "error": None},
				isManual=isManual,
				allowCopy=allowCopy,
				onSuccess=onSuccess,
				onError=onError,
			)
			return
		if isManual and showStatus:
			cues.Sound.startPeriodic(
				CueType.WAITING,
				intervalMs=1200,
				delayMs=600,
			)

		def callback(result: dict[str, Any]) -> None:
			self._onTranslationComplete(
				result,
				isManual=isManual,
				allowCopy=allowCopy,
				onSuccess=onSuccess,
				onError=onError,
			)

		task = TranslationTask(
			engineId=engineId,
			text=text,
			langFrom=langFrom,
			langTo=langTo,
			cache=self.cache,
			onComplete=callback,
			isManual=isManual,
			engineConfig=engineConfig,
		)
		self._currentTask = task
		task.start()

	def _onTranslationComplete(
		self,
		result: dict[str, Any],
		isManual: bool,
		allowCopy: bool,
		onSuccess: OnSuccessCallback,
		onError: OnErrorCallback = None,
	) -> None:
		cues.stopPeriodicCue()

		def task() -> None:
			error = result.get("error")
			if error:
				prefix = _("Translation failed: ")
				errorMessage = (
					f"{prefix}{error}"
					if isinstance(error, EngineError)
					else f"{prefix}{_('An unknown error occurred')}"
				)
				cues.Speech.message(errorMessage)
				if onError:
					onError(errorMessage)
				if not isManual:
					self.consecutiveFailures += 1
					if self.consecutiveFailures >= 3:
						log.warning("Disabling auto-translation due to 3 consecutive failures.")
						self.isAutoTranslateEnabled = False
						self.consecutiveFailures = 0
						queueHandler.queueFunction(
							queueHandler.eventQueue,
							cues.Speech.message,
							_("Auto-translation disabled due to repeated failures."),
						)
			else:
				self.consecutiveFailures = 0
				translation = result["translation"]
				log.info(f"Translation successful. Result: '{translation[:50]}...'")
				self.lastTranslation = translation
				if onSuccess:
					onSuccess(translation)
				else:
					cues.Speech.message(translation)
				if isManual and allowCopy and config.getConfig()["copyResult"]:
					api.copyToClip(translation)

		queueHandler.queueFunction(queueHandler.eventQueue, task)
