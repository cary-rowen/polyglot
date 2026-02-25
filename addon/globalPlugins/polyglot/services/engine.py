# -*- coding: utf-8 -*-

import json
import random
import time
from abc import ABC, abstractmethod
from typing import Any
from collections.abc import Callable

import addonHandler
from logHandler import log

from ..common.exceptions import EngineError, ResponseParsingError
from ..common.network import sendRequest
from ..common.textUtils import splitText
from ..common.cues import Beep

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
	def autoDetectCode(self) -> str | None:
		"""
		Returns the language code this engine uses for "auto-detect".
		Subclasses must return None if not supported.
		"""
		pass

	@property
	def supportsLanguageDetection(self) -> bool:
		"""A convenience property for readability, its behavior is derived from autoDetectCode."""
		return self.autoDetectCode is not None

	@property
	def reportsDetectedLanguage(self) -> bool:
		"""Reports the ability to detect the source language. Defaults to whether language detection is supported."""
		return self.supportsLanguageDetection

	@abstractmethod
	def getConfigSpec(self) -> list[dict[str, Any]]:
		pass

	@abstractmethod
	def getSupportedLanguages(self) -> dict[str, str]:
		pass

	@abstractmethod
	def translate(self, text: str, langFrom: str, langTo: str, config: dict[str, Any], isCancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
		pass

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, Any]:
		return {}


class BaseHttpEngine(TranslationEngine):
	"""
	Provides a common framework and rules for HTTP-based engines.
	"""

	@property
	def maxRequestLength(self) -> int:
		"""
		Returns the maximum number of characters allowed per request.
		Returns 0 or less if there is no limit.
		"""
		return 0

	@property
	def requestDelayRange(self) -> tuple[float, float] | None:
		"""
		Defines a range of random delay (in seconds) between chunked requests.
		Returns (min, max) or None to disable. Default is a gentle range.
		"""
		return (0.4, 1.2)

	@property
	@abstractmethod
	def autoDetectCode(self) -> str | None:
		"""
		This method remains abstract in BaseHttpEngine,
		forcing all concrete HTTP engines to implement it explicitly.
		"""
		raise NotImplementedError(
			f"""Translation engine '{self.id}' must explicitly implement the 'autoDetectCode' property in a subclass (return None if not supported)."""
		)

	@property
	def defaultSourceLanguage(self) -> str:
		"""
		Provides an intelligent, conditional default source language.
		- If the engine supports language detection, it automatically uses its autoDetectCode.
		- If not, the subclass is forced to override this property and provide a specific language.
		"""
		autoCode = self.autoDetectCode
		if self.supportsLanguageDetection and autoCode is not None:
			return autoCode
		raise NotImplementedError(
			f"""Translation engine '{self.id}' does not support auto language detection, and must therefore explicitly override the 'defaultSourceLanguage' property in a subclass."""
		)

	@property
	@abstractmethod
	def defaultTargetLanguage(self) -> str:
		"""
		Forces all concrete HTTP engines to explicitly define their default target language.
		"""
		raise NotImplementedError(
			f"Translation engine '{self.id}' must explicitly implement the 'defaultTargetLanguage' property."
		)

	def getConfigSpec(self) -> list[dict[str, Any]]:
		allLangs = self.getSupportedLanguages()
		autoCode = self.autoDetectCode

		fromChoices = allLangs.copy()
		if not self.supportsLanguageDetection and autoCode:
			_unused = fromChoices.pop(autoCode, None)

		toChoices = allLangs.copy()
		if autoCode is not None:
			_unused = toChoices.pop(autoCode, None)

		spec: list[dict[str, Any]] = [
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
			]
		)

		if self.reportsDetectedLanguage:
			swapChoices = toChoices.copy()
			spec.extend(
				[
					{
						"id": "enableAutoSwap",
						"label": _(
							"Auto-swap if detected source matches target (source must be 'Auto-detect')"
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
				]
			)
		return spec

	def _getFilteredChoices(
		self, allLangs: dict[str, str], excludeCode: str | None = None, removeAuto: bool = False
	) -> dict[str, str]:
		"""A helper function to create a filtered dictionary of language options based on rules."""
		choices = allLangs.copy()
		if removeAuto and self.autoDetectCode is not None:
			_unused = choices.pop(self.autoDetectCode, None)
		if excludeCode:
			_unused = choices.pop(excludeCode, None)
		return choices

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, dict[str, Any]]:
		states = super().getUiStates(allConfigs)
		allLangs = self.getSupportedLanguages()
		autoCode = self.autoDetectCode
		selectedFrom = allConfigs.get("langFrom")
		selectedTo = allConfigs.get("langTo")
		# --- Generate language lists using the helper function ---
		# Target language (langTo): Always remove "auto-detect" and exclude the currently selected source language.
		validToLangs = self._getFilteredChoices(allLangs, excludeCode=selectedFrom, removeAuto=True)
		# Source language (langFrom): Exclude the currently selected target language.
		validFromLangs = self._getFilteredChoices(allLangs, excludeCode=selectedTo)
		# Special handling for the source list: only remove "auto-detect" if the engine does not support it.
		if not self.supportsLanguageDetection and autoCode:
			_unused = validFromLangs.pop(autoCode, None)
		states["langFrom"] = {"choices": validFromLangs}
		states["langTo"] = {"choices": validToLangs}
		# --- Logic for auto-swap related controls ---
		if self.reportsDetectedLanguage:
			isAutoFrom = selectedFrom == autoCode
			states["enableAutoSwap"] = {"visible": isAutoFrom}
			isSwapLangVisible = isAutoFrom and allConfigs.get("enableAutoSwap", False)
			# Swap-to language (swapLanguage): Rules are the same as for target language; exclude current target and "auto-detect".
			validSwapLangs = self._getFilteredChoices(
				allLangs, excludeCode=selectedTo, removeAuto=True
			)
			states["swapLanguage"] = {"visible": isSwapLangVisible, "choices": validSwapLangs}
		return states

	@abstractmethod
	def _buildRequestParams(
		self, text: str, langFrom: str, langTo: str, config: dict[str, Any]
	) -> dict[str, Any]:
		pass

	@abstractmethod
	def _parseResponse(self, responseBody: str) -> dict[str, Any]:
		pass

	def translate(self, text: str, langFrom: str, langTo: str, config: dict[str, Any], isCancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
		limit = self.maxRequestLength
		if limit <= 0 or len(text) <= limit:
			return self._translateChunk(text, langFrom, langTo, config)
		
		chunks = splitText(text, limit)
		totalChunks = len(chunks)
		delayRange = self.requestDelayRange

		translatedChunks = []
		detectedLang = None
		for i, chunk in enumerate(chunks):
			if isCancelled and isCancelled():
				log.debug("Chunked translation cancelled mid-way.")
				break
				
			if not chunk.strip():
				translatedChunks.append(chunk)
				continue
				
			if i > 0 and delayRange:
				time.sleep(random.uniform(*delayRange))

			leadingWs = len(chunk) - len(chunk.lstrip())
			trailingWs = len(chunk) - len(chunk.rstrip())
			
			leadingStr = chunk[:leadingWs] if leadingWs > 0 else ""
			trailingStr = chunk[-trailingWs:] if trailingWs > 0 else ""
			
			strippedChunk = chunk.strip()
			if not strippedChunk:
				translatedChunks.append(chunk)
				continue

			res = self._translateChunk(strippedChunk, langFrom, langTo, config)
			translatedText = res.get("translation", "").strip()
			
			translatedChunks.append(leadingStr + translatedText + trailingStr)
			
			if totalChunks > 1:
				Beep.reportProgress(i + 1, totalChunks)

			if detectedLang is None and "langDetected" in res:
				detectedLang = res["langDetected"]
		
		return {
			"translation": "".join(translatedChunks),
			"langDetected": detectedLang
		}

	def _translateChunk(self, text: str, langFrom: str, langTo: str, config: dict[str, Any]) -> dict[str, Any]:
		try:
			params = self._buildRequestParams(text, langFrom, langTo, config)
			log.debug(f"Engine '{self.id}' built request params: {params.get('method')} {params.get('url')}")
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
			log.debug(f"Engine '{self.id}' raw response: {responseBody}")
			return self._parseResponse(responseBody)
		except json.JSONDecodeError as e:
			log.error(f"Failed to parse JSON response from '{self.id}'.", exc_info=True)
			raise ResponseParsingError(_("Failed to parse response from translation service.")) from e
		except EngineError:
			raise
		except Exception as e:
			log.error(f"An unexpected error occurred in '{self.id}' engine.", exc_info=True)
			raise EngineError(_("An unknown error occurred during translation.")) from e
