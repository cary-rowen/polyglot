# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import functools
import json
import random
import time
from abc import ABC, abstractmethod
from typing import Any
from collections.abc import Callable

import addonHandler
from logHandler import log

from ..common import languages
from ..common.exceptions import EngineError, ResponseParsingError
from ..common.network import sendRequest
from ..common.textUtils import splitText
from ..common.cues import Beep

addonHandler.initTranslation()


class TranslationEngine(ABC):
	"""Defines the abstract interface that all translation engines must implement."""

	@property
	@abstractmethod
	def id(self) -> str:
		"""Return the stable internal engine identifier."""
		pass

	@property
	@abstractmethod
	def name(self) -> str:
		"""Return the translated engine name shown to users."""
		pass

	@property
	@abstractmethod
	def autoDetectCode(self) -> str | None:
		"""
		Return the language code this engine uses for automatic detection.

		Subclasses must return None if not supported.
		"""
		pass

	@property
	def fallbackSourceLanguage(self) -> str | None:
		"""Return the preferred source language when automatic detection is unavailable."""
		return None

	@property
	@abstractmethod
	def fallbackTargetLanguage(self) -> str:
		"""Return the fallback target language used when NVDA's language is unsupported."""
		pass

	# Cached: NVDA's interface language only changes after a restart.
	@functools.cached_property
	def defaultTargetLanguage(self) -> str:
		"""Return the default target language, preferring NVDA's interface language."""
		autoCode = self.autoDetectCode
		return languages.resolveTargetLanguage(
			self.getSupportedLanguages(),
			fallback=self.fallbackTargetLanguage,
			excludeCodes=() if autoCode is None else (autoCode,),
		)

	@functools.cached_property
	def defaultSourceLanguage(self) -> str:
		"""Return the default source language without colliding with the default target."""
		if self.autoDetectCode is not None:
			return self.autoDetectCode
		target = self.defaultTargetLanguage
		supported = self.getSupportedLanguages()
		for candidate in (self.fallbackSourceLanguage, self.fallbackTargetLanguage, *supported):
			if candidate and candidate in supported and candidate != target:
				return candidate
		raise NotImplementedError(
			f"Translation engine '{self.id}' does not support auto language detection and has no valid default source language.",
		)

	@property
	def doesSupportLanguageDetection(self) -> bool:
		"""Return whether the engine accepts an automatic-detection source code."""
		return self.autoDetectCode is not None

	@property
	def doesReportDetectedLanguage(self) -> bool:
		"""Return whether translation results include the detected source language."""
		return self.doesSupportLanguageDetection

	def areLanguagesEquivalent(self, detectedLanguage: str, targetLanguage: str) -> bool:
		"""Return whether a detected source and target language are equivalent for auto-swap."""
		return detectedLanguage == targetLanguage

	@property
	def enabledConfigLabel(self) -> str:
		"""Return the label for the common engine enable checkbox."""
		return _("Enable this engine")

	def getEnabledConfigSpec(self) -> dict[str, Any]:
		"""Return the common configuration item controlling engine availability."""
		return {
			"id": "enabled",
			"label": self.enabledConfigLabel,
			"type": "checkbox",
			"default": True,
		}

	def isEnabled(self, engineConfig: dict[str, Any]) -> bool:
		"""Return whether the engine is enabled by its configuration."""
		return engineConfig.get("enabled", True) is not False

	@abstractmethod
	def getConfigSpec(self) -> list[dict[str, Any]]:
		"""Return configuration-control specifications for this engine."""
		pass

	@abstractmethod
	def getSupportedLanguages(self) -> dict[str, str]:
		"""Return supported language codes mapped to translated names."""
		pass

	@abstractmethod
	def translate(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
		isCancelled: Callable[[], bool] | None = None,
	) -> dict[str, Any]:
		"""Translate text and return a common translation-result dictionary."""
		pass

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, Any]:
		"""Return dynamic control properties derived from current configuration."""
		return {}


class ChunkedTranslationMixin(TranslationEngine):
	"""
	Provides automatic text chunking and sequential translation capabilities.
	Subclasses must implement `_translateChunk` to handle the actual translation of each chunk.
	"""

	@property
	def maxRequestLength(self) -> int:
		"""
		Return the maximum number of characters allowed per request.

		Returns 0 or less if there is no limit.
		"""
		return 0

	def _getRequestLength(self, text: str) -> int:
		"""Return the request length according to this engine's endpoint rules."""
		return len(text)

	@property
	def requestDelayRange(self) -> tuple[float, float] | None:
		"""
		Return the random delay range between chunked requests.

		Returns (min, max) or None to disable. Default is a gentle range.
		"""
		return (0.4, 1.2)

	@abstractmethod
	def _translateChunk(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
	) -> dict[str, Any]:
		pass

	def translate(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
		isCancelled: Callable[[], bool] | None = None,
	) -> dict[str, Any]:
		"""Translate text sequentially in bounded chunks while preserving whitespace."""
		limit = self.maxRequestLength
		if limit <= 0 or self._getRequestLength(text) <= limit:
			return self._translateChunk(text, langFrom, langTo, config)

		chunks = splitText(text, limit, self._getRequestLength)
		totalChunks = len(chunks)
		delayRange = self.requestDelayRange

		translatedChunks = []
		detectedLang = None
		for chunkIndex, chunk in enumerate(chunks):
			if isCancelled and isCancelled():
				log.debug("Chunked translation cancelled mid-way.")
				break

			if not chunk.strip():
				translatedChunks.append(chunk)
				continue

			if chunkIndex > 0 and delayRange:
				time.sleep(random.uniform(*delayRange))

			leadingWhitespaceLength = len(chunk) - len(chunk.lstrip())
			trailingWhitespaceLength = len(chunk) - len(chunk.rstrip())

			leadingWhitespace = chunk[:leadingWhitespaceLength] if leadingWhitespaceLength > 0 else ""
			trailingWhitespace = chunk[-trailingWhitespaceLength:] if trailingWhitespaceLength > 0 else ""

			strippedChunk = chunk.strip()
			chunkResult = self._translateChunk(strippedChunk, langFrom, langTo, config)
			translatedText = chunkResult.get("translation", "").strip()

			translatedChunks.append(leadingWhitespace + translatedText + trailingWhitespace)

			if totalChunks > 1:
				Beep.reportProgress(chunkIndex + 1, totalChunks)

			if detectedLang is None and "langDetected" in chunkResult:
				detectedLang = chunkResult["langDetected"]

		return {
			"translation": "".join(translatedChunks),
			"langDetected": detectedLang,
		}


class BaseHttpEngine(ChunkedTranslationMixin):
	"""Provides a common framework and rules for HTTP-based engines."""

	@property
	@abstractmethod
	def autoDetectCode(self) -> str | None:
		"""
		This method remains abstract in BaseHttpEngine,
		forcing all concrete HTTP engines to implement it explicitly.
		"""
		raise NotImplementedError(
			f"""Translation engine '{self.id}' must explicitly implement the 'autoDetectCode' property in a subclass (return None if not supported).""",
		)

	def getConfigSpec(self) -> list[dict[str, Any]]:
		"""Return common HTTP, language, and auto-swap configuration controls."""
		allLangs = self.getSupportedLanguages()
		autoCode = self.autoDetectCode

		fromChoices = allLangs.copy()

		toChoices = allLangs.copy()
		if autoCode is not None:
			_unused = toChoices.pop(autoCode, None)

		spec: list[dict[str, Any]] = [
			self.getEnabledConfigSpec(),
			{
				"id": "langFrom",
				"label": _("Source language:"),
				"type": "choice",
				"choices": fromChoices,
				"default": self.defaultSourceLanguage,
			},
			{
				"id": "langTo",
				"label": _("Target language:"),
				"type": "choice",
				"choices": toChoices,
				"default": self.defaultTargetLanguage,
			},
		]

		spec.extend(
			[
				{
					"id": "proxyMode",
					"label": _("Proxy mode:"),
					"type": "choice",
					"choices": {
						"system": _("Use system proxy settings"),
						"none": _("Do not use proxy"),
					},
					"default": "system",
				},
				{
					"id": "timeout",
					"label": _("Request timeout:"),
					"type": "spinctrl",
					"default": 15,
					"min": 1,
					"max": 60,
				},
			],
		)

		if self.doesReportDetectedLanguage:
			swapChoices = toChoices.copy()
			spec.extend(
				[
					{
						"id": "enableAutoSwap",
						"label": _(
							"Auto-swap if detected source matches target (source must be 'Auto-detect')",
						),
						"type": "checkbox",
						"default": False,
					},
					{
						"id": "swapLanguage",
						"label": _("Swap to language:"),
						"type": "choice",
						"choices": swapChoices,
						"default": "",
					},
				],
			)
		return spec

	def _getFilteredChoices(
		self,
		allLangs: dict[str, str],
		excludeCode: str | None = None,
		shouldRemoveAuto: bool = False,
	) -> dict[str, str]:
		"""Filter language choices according to the supplied inclusion rules."""
		choices = allLangs.copy()
		if shouldRemoveAuto and self.autoDetectCode is not None:
			_unused = choices.pop(self.autoDetectCode, None)
		if excludeCode:
			_unused = choices.pop(excludeCode, None)
		return choices

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, dict[str, Any]]:
		"""Return language and auto-swap choices valid for the current selections."""
		states = super().getUiStates(allConfigs)
		allLangs = self.getSupportedLanguages()
		autoCode = self.autoDetectCode
		selectedFrom = allConfigs.get("langFrom")
		selectedTo = allConfigs.get("langTo")
		# --- Generate language lists using the helper function ---
		# Target language (langTo): Always remove "auto-detect" and exclude the currently selected source language.
		validToLangs = self._getFilteredChoices(
			allLangs,
			excludeCode=selectedFrom,
			shouldRemoveAuto=True,
		)
		# Source language (langFrom): Exclude the currently selected target language.
		validFromLangs = self._getFilteredChoices(allLangs, excludeCode=selectedTo)
		states["langFrom"] = {"choices": validFromLangs}
		states["langTo"] = {"choices": validToLangs}
		# --- Logic for auto-swap related controls ---
		if self.doesReportDetectedLanguage:
			isAutoFrom = selectedFrom == autoCode
			states["enableAutoSwap"] = {"visible": isAutoFrom}
			isSwapLangVisible = isAutoFrom and allConfigs.get("enableAutoSwap", False)
			# Swap-to language (swapLanguage): Rules are the same as for target language; exclude current target and "auto-detect".
			validSwapLangs = self._getFilteredChoices(
				allLangs,
				excludeCode=selectedTo,
				shouldRemoveAuto=True,
			)
			states["swapLanguage"] = {"visible": isSwapLangVisible, "choices": validSwapLangs}
		return states

	@abstractmethod
	def _buildRequestParams(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
	) -> dict[str, Any]:
		pass

	@abstractmethod
	def _parseResponse(self, responseBody: str) -> dict[str, Any]:
		pass

	def _translateChunk(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
	) -> dict[str, Any]:
		try:
			params = self._buildRequestParams(text, langFrom, langTo, config)
			log.debug("Engine '%s' is sending a %s request.", self.id, params.get("method", "GET"))
			proxyMode = config.get("proxyMode", "system")
			proxiesDict: dict[str, str | None] | None = (
				None  # Default is None, which makes requests use system proxy settings.
			)
			if proxyMode == "none":
				proxiesDict = {"http": None, "https": None}
			timeoutInt = int(config.get("timeout", "15"))
			responseBody = sendRequest(
				method=params.get("method", "GET"),
				url=params["url"],
				headers=params.get("headers"),
				data=params.get("data"),
				timeout=timeoutInt,
				proxies=proxiesDict,
			)
			return self._parseResponse(responseBody)
		except json.JSONDecodeError as e:
			log.exception("Failed to parse JSON response from '%s'.", self.id)
			raise ResponseParsingError(_("Failed to parse response from translation service.")) from e
		except EngineError:
			raise
		except Exception as e:
			log.exception("An unexpected error occurred in '%s' engine.", self.id)
			raise EngineError(_("An unknown error occurred during translation.")) from e
