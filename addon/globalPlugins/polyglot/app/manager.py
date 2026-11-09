# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

from collections.abc import Callable
from typing import Any

import addonHandler
import api
import queueHandler
from logHandler import log

from ..common import config
from ..common.cache import TranslationCache
from ..common.exceptions import EngineError
from ..common import languages
from ..common.wordDictionary import (
	EnglishChineseDictionary,
	ItalianChineseDictionary,
	formatWordLookupResult,
)
from ..services import engineManager
from .task import TranslationTask
from ..common import cues
from ..common.cues import CueType


addonHandler.initTranslation()


OnSuccessCallback = Callable[[str], None] | None
OnErrorCallback = Callable[[str], None] | None

_CHINESE_DICTIONARY_TARGET_CODES = frozenset(
	("cht", "zh", "zh-cn", "zh-chs", "zh-hans", "zh-hant", "zh-hk", "zh-tw"),
)


def _normalizeLanguageCode(language: str | None) -> str:
	"""Normalize language-code spelling for local dictionary direction checks."""
	return (language or "").strip().replace("_", "-").casefold()


def _isEnglishLanguage(language: str | None) -> bool:
	"""Return whether a language code identifies English."""
	return _normalizeLanguageCode(language).partition("-")[0] == "en"


def _isChineseLanguage(language: str | None) -> bool:
	"""Return whether a language code identifies a Chinese source language."""
	normalizedLanguage = _normalizeLanguageCode(language)
	return normalizedLanguage in ("cht", "yue", "wyw") or normalizedLanguage.partition("-")[0] == "zh"


def _isItalianLanguage(language: str | None) -> bool:
	"""Return whether a language code identifies Italian."""
	return _normalizeLanguageCode(language).partition("-")[0] == "it"


def _isChineseDictionaryTarget(language: str | None) -> bool:
	"""Return whether a language code identifies a supported Chinese dictionary target."""
	return _normalizeLanguageCode(language) in _CHINESE_DICTIONARY_TARGET_CODES


def _isAutoDetectedLanguage(language: str | None, autoDetectCode: str | None) -> bool:
	"""Return whether a selected source code is this engine's auto-detect code."""
	return (
		language is not None
		and autoDetectCode is not None
		and _normalizeLanguageCode(language) == _normalizeLanguageCode(autoDetectCode)
	)


class TranslationManager:
	"""Coordinate engines, cache, dictionary lookup, and translation task lifecycle."""

	# Annotations for instance variables defined and managed by this class
	cache: TranslationCache
	wordDictionary: EnglishChineseDictionary
	italianDictionary: ItalianChineseDictionary
	lastTranslation: str | None
	consecutiveFailures: int
	_currentTask: TranslationTask | None
	isAutoTranslateEnabled: bool

	def __init__(self) -> None:
		"""Initialize shared translation state with no active request."""
		super().__init__()
		self.cache = TranslationCache()
		self.wordDictionary = EnglishChineseDictionary()
		self.italianDictionary = ItalianChineseDictionary()
		self.lastTranslation = None
		self.consecutiveFailures = 0
		self._currentTask = None
		self.isAutoTranslateEnabled = False

	def clearCache(self) -> None:
		"""Clear all cached translation entries."""
		self.cache.clear()

	def toggleAutoTranslate(self) -> bool:
		"""Toggles auto-translation on or off and returns the new state."""
		self.resetConsecutiveFailures()
		self.isAutoTranslateEnabled = not self.isAutoTranslateEnabled
		log.debug("Runtime auto-translate state changed to %s.", self.isAutoTranslateEnabled)
		return self.isAutoTranslateEnabled

	def swapLanguages(self) -> tuple[bool, str]:
		"""
		Swap the source and target languages in the configuration.

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
		log.debug("Languages swapped for engine '%s'.", engineId)
		# Translators: A message indicating that the source and target languages have been swapped. {source} is the new source language, {target} is the new target language.
		message = _("Languages swapped: from {source} to {target}").format(
			source=currentTo,
			target=currentFrom,
		)
		return (True, message)

	def cycleLanguage(self, target: str, isForward: bool) -> tuple[bool, str]:
		"""
		Cycles the source or target language for the current engine.
		The other side's language is excluded from the candidate list
		to prevent source and target from being set to the same language.

		Args:
			target: "source" or "target", indicating which language to cycle.
			isForward: True to cycle forward, False to cycle backward.

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
		step = 1 if isForward else -1
		newIndex = (currentIndex + step) % len(langCodes)
		newCode = langCodes[newIndex]
		engineConf[configKey] = newCode
		newName = languages.getLanguageName(newCode)
		return (True, newName)

	def cycleEngine(self, isForward: bool) -> tuple[bool, str]:
		"""
		Cycles the active translation engine.

		Args:
			isForward: True to cycle forward, False to cycle backward.

		Returns:
			A tuple containing a boolean for success and a user-facing message.
		"""
		allEngines = engineManager.getAllEngines()
		if not allEngines:
			return (False, _("No translation engines available."))
		conf = config.getConfig()
		currentId = conf["engine"]
		newEngine = engineManager.getNextEnabledEngine(currentId, isForward=isForward)
		if not newEngine:
			return (False, _("No enabled translation engines available."))
		conf["engine"] = newEngine.id
		return (True, newEngine.name)

	def getCurrentEngineAndLanguageInfo(self) -> str:
		"""Format the current engine and language pair for announcement."""
		conf = config.getConfig()
		engineId = conf["engine"]
		engineConf = conf["engines"].get(engineId, {})
		try:
			currentEngine = engineManager.getEngineById(engineId)
			langFromCode = engineConf.get("langFrom", currentEngine.defaultSourceLanguage)
			langToCode = engineConf.get("langTo", currentEngine.defaultTargetLanguage)
			langFromDesc = languages.getLanguageName(langFromCode)
			langToDesc = languages.getLanguageName(langToCode)
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
		"""Cancel the active translation task, if any, and stop periodic cues."""
		if self._currentTask and self._currentTask.is_alive():
			log.debug("Terminating active translation task.")
			self._currentTask.cancel()
		cues.stopPeriodicCue()
		self._currentTask = None

	def resetConsecutiveFailures(self) -> None:
		"""Reset the consecutive failure counter to zero."""
		log.debug("Consecutive failure count has been reset manually.")
		self.consecutiveFailures = 0

	def getCurrentLanguages(self) -> tuple[str | None, str | None]:
		"""
		Get the currently configured source and target languages.

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
		Return the reversed language pair when the current direction permits it.

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
		shouldShowStatus: bool = True,
		shouldAllowCopy: bool = True,
		onSuccess: OnSuccessCallback = None,
		onError: OnErrorCallback = None,
		langFrom: str | None = None,
		langTo: str | None = None,
		shouldPreferLocalDictionary: bool = False,
	) -> None:
		"""Start a translation using configured fallback, dictionary, and cache behavior."""
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
		shouldUseLocalDictionary = (
			isManual and shouldPreferLocalDictionary and conf.get("enableLocalDictionaryForTranslation", True)
		)
		isCurrentEngineEnabled = currentEngine.isEnabled(engineConfig)
		localTranslation = None
		if shouldUseLocalDictionary and not isCurrentEngineEnabled:
			# A disabled engine still provides the configured direction for an offline lookup.
			try:
				dictionaryAutoDetectCode = currentEngine.autoDetectCode
				dictionaryLangFrom = (
					langFrom
					if langFrom is not None
					else engineConfig.get("langFrom", currentEngine.defaultSourceLanguage)
				)
				dictionaryLangTo = (
					langTo
					if langTo is not None
					else engineConfig.get("langTo", currentEngine.defaultTargetLanguage)
				)
			except NotImplementedError:
				pass
			else:
				localTranslation = self._getLocalDictionaryTranslation(
					text,
					dictionaryLangFrom,
					dictionaryLangTo,
					dictionaryAutoDetectCode,
				)
		if localTranslation is None and not isCurrentEngineEnabled:
			fallbackEngine = engineManager.getNextEnabledEngine(engineId)
			if not fallbackEngine:
				log.warning(
					f"Selected engine '{engineId}' is disabled and no enabled fallback engine is available.",
				)
				error = EngineError(_("No enabled translation engines available."))
				self._onTranslationComplete(
					{"translation": None, "error": error},
					isManual=isManual,
					shouldAllowCopy=shouldAllowCopy,
					onSuccess=onSuccess,
					onError=onError,
				)
				return
			log.debug("Selected engine '%s' is disabled; switching to '%s'.", engineId, fallbackEngine.id)
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
		if isManual and shouldShowStatus:
			cues.Sound.play(CueType.START)
		if self._currentTask and self._currentTask.is_alive():
			log.debug("A new translation request is overriding the previous one; cancelling it.")
			self._currentTask.cancel()
			cues.stopPeriodicCue()
		if shouldUseLocalDictionary and localTranslation is None:
			localTranslation = self._getLocalDictionaryTranslation(
				text,
				langFrom,
				langTo,
				currentEngine.autoDetectCode,
			)
		if localTranslation is not None:
			log.debug("Local dictionary matched a manual translation request; skipping translation engine.")
			self._onTranslationComplete(
				{"translation": localTranslation, "error": None},
				isManual=isManual,
				shouldAllowCopy=shouldAllowCopy,
				onSuccess=onSuccess,
				onError=onError,
			)
			return
		cacheKey = self.cache.buildKey(langFrom, langTo, text)
		cachedResult = self.cache.get(cacheKey)
		if cachedResult:
			log.debug("Translation cache hit.")
			self._onTranslationComplete(
				{"translation": cachedResult, "error": None},
				isManual=isManual,
				shouldAllowCopy=shouldAllowCopy,
				onSuccess=onSuccess,
				onError=onError,
			)
			return
		if isManual and shouldShowStatus:
			cues.Sound.startPeriodic(
				CueType.WAITING,
				intervalMs=1200,
				delayMs=600,
			)

		def callback(result: dict[str, Any]) -> None:
			self._onTranslationComplete(
				result,
				isManual=isManual,
				shouldAllowCopy=shouldAllowCopy,
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

	def _getLocalDictionaryTranslation(
		self,
		text: str,
		langFrom: str | None,
		langTo: str | None,
		autoDetectCode: str | None,
	) -> str | None:
		"""Return a local definition when the manual request has a supported language direction."""
		isSourceEnglish = _isEnglishLanguage(langFrom) or _isAutoDetectedLanguage(langFrom, autoDetectCode)
		isEnglishToChinese = isSourceEnglish and _isChineseDictionaryTarget(langTo)
		isChineseToEnglish = _isChineseLanguage(langFrom) and _isEnglishLanguage(langTo)
		# Italian is only used when the user explicitly selects it as the source
		# language: auto-detect stays English-only so the two dictionaries can
		# never answer for each other.
		isItalianToChinese = _isItalianLanguage(langFrom) and _isChineseDictionaryTarget(langTo)

		if isItalianToChinese:
			dictionary = self.italianDictionary
		elif isEnglishToChinese or isChineseToEnglish:
			dictionary = self.wordDictionary
		else:
			return None

		lookupResult = dictionary.lookup(text)
		if lookupResult is None or not lookupResult.matches:
			return None
		return formatWordLookupResult(lookupResult)

	def _onTranslationComplete(
		self,
		result: dict[str, Any],
		isManual: bool,
		shouldAllowCopy: bool,
		onSuccess: OnSuccessCallback,
		onError: OnErrorCallback = None,
	) -> None:
		cues.stopPeriodicCue()
		if result.get("cancelled"):
			return

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
				log.debug("Translation completed successfully.")
				self.lastTranslation = translation
				if onSuccess:
					onSuccess(translation)
				else:
					cues.Speech.message(translation)
				if isManual and shouldAllowCopy and config.getConfig()["copyResult"]:
					api.copyToClip(translation)

		queueHandler.queueFunction(queueHandler.eventQueue, task)
