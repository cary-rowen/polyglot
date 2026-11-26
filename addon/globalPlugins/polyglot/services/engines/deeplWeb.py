# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""DeepL's anonymous Web translation engine."""

import json
from typing import Any

import addonHandler

from ...common import languages
from ...common.exceptions import ApiResponseError
from ..engine import BaseHttpEngine

addonHandler.initTranslation()


class DeepLWebTranslateEngine(BaseHttpEngine):
	"""Translate text through DeepL's anonymous oneshot Web endpoint."""

	# This is an unofficial endpoint with no SLA; use the API-key engine when guarantees are required.
	id = "deeplWeb"
	# Translators: Name of the anonymous DeepL Web translation engine.
	name = _("DeepL Web (key-free)")

	API_URL = "https://oneshot-free.www.deepl.com/v1/translate"
	MAX_REQUEST_LENGTH = 1500
	SUPPORTED_CODES = [
		"auto",
		"ar",
		"bg",
		"cs",
		"da",
		"de",
		"el",
		"en",
		"en-GB",
		"en-US",
		"es",
		"es-419",
		"et",
		"fi",
		"fr",
		"he",
		"hu",
		"id",
		"it",
		"ja",
		"ko",
		"lt",
		"lv",
		"nb",
		"nl",
		"pl",
		"pt",
		"pt-BR",
		"pt-PT",
		"ro",
		"ru",
		"sk",
		"sl",
		"sv",
		"tr",
		"uk",
		"vi",
		"zh",
		"zh-Hans",
		"zh-Hant",
	]
	TARGET_LANG_MAP = {
		"AR": "ar",
		"BG": "bg",
		"CS": "cs",
		"DA": "da",
		"DE": "de",
		"EL": "el",
		"EN": "en-US",
		"EN-GB": "en-GB",
		"EN-US": "en-US",
		"ES": "es",
		"ES-419": "es-419",
		"ET": "et",
		"FI": "fi",
		"FR": "fr",
		"HE": "he",
		"HU": "hu",
		"ID": "id",
		"IT": "it",
		"JA": "ja",
		"KO": "ko",
		"LT": "lt",
		"LV": "lv",
		"NB": "nb",
		"NL": "nl",
		"PL": "pl",
		"PT": "pt-BR",
		"PT-BR": "pt-BR",
		"PT-PT": "pt-PT",
		"RO": "ro",
		"RU": "ru",
		"SK": "sk",
		"SL": "sl",
		"SV": "sv",
		"TR": "tr",
		"UK": "uk",
		"VI": "vi",
		"ZH": "zh-Hans",
		"ZH-HANS": "zh-Hans",
		"ZH-HANT": "zh-Hant",
	}
	SOURCE_LANG_MAP = {code: wireCode.split("-", 1)[0] for code, wireCode in TARGET_LANG_MAP.items()}
	_DETECTED_LANG_ALIASES = {
		"en-us": "en-US",
		"en-gb": "en-GB",
		"es-419": "es-419",
		"pt-br": "pt-BR",
		"pt-pt": "pt-PT",
		"zh-hans": "zh-Hans",
		"zh-hant": "zh-Hant",
	}

	@property
	def maxRequestLength(self) -> int:
		"""Return the anonymous endpoint's per-request character limit."""
		return self.MAX_REQUEST_LENGTH

	def _getRequestLength(self, text: str) -> int:
		"""Count UTF-16 code units, which the anonymous endpoint uses for its limit."""
		return len(text.encode("utf-16-le")) // 2

	def areLanguagesEquivalent(self, detectedLanguage: str, targetLanguage: str) -> bool:
		"""Treat an unqualified detected code as equivalent to its regional target."""
		if detectedLanguage.casefold() == targetLanguage.casefold():
			return True
		return "-" not in detectedLanguage and languages.getLanguageFamily(
			detectedLanguage,
		) == languages.getLanguageFamily(targetLanguage)

	@property
	def autoDetectCode(self) -> str | None:
		"""Return the source code used to request automatic detection."""
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		"""Return Simplified Chinese as the fallback target language."""
		return "zh-Hans"

	def getSupportedLanguages(self) -> dict[str, str]:
		"""Return the language codes accepted by the DeepL Web endpoint."""
		return languages.getLanguageDictForCodes(self.SUPPORTED_CODES)

	def _resolveLanguage(self, code: str, isTarget: bool) -> str:
		"""Resolve a Polyglot language code to the Web endpoint's wire code."""
		languageMap = self.TARGET_LANG_MAP if isTarget else self.SOURCE_LANG_MAP
		wireCode = languageMap.get(code.upper())
		if wireCode is None:
			kind = _("target") if isTarget else _("source")
			# Translators: Error shown when a configured language is not accepted by DeepL Web. {kind} is source or target; {code} is the configured code.
			raise ApiResponseError(
				_("Unsupported DeepL Web {kind} language: {code}").format(kind=kind, code=code),
			)
		return wireCode

	def _buildRequestParams(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
	) -> dict[str, Any]:
		"""Build a minimal JSON request for the anonymous oneshot endpoint."""
		targetLanguage = self._resolveLanguage(langTo, isTarget=True)
		payload: dict[str, Any] = {
			"text": [text],
			"target_lang": targetLanguage,
			"usage_type": "Translate",
		}
		if langFrom.lower() != self.autoDetectCode:
			payload["source_lang"] = self._resolveLanguage(langFrom, isTarget=False)

		return {
			"method": "POST",
			"url": self.API_URL,
			"headers": {
				"Authorization": "None",
				"Content-Type": "application/json",
			},
			"data": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
		}

	def _normalizeDetectedLanguage(self, code: str) -> str:
		"""Normalize the endpoint's lower-case detection code for Polyglot."""
		return self._DETECTED_LANG_ALIASES.get(code.lower(), code.lower())

	def _parseResponse(self, responseBody: str) -> dict[str, Any]:
		"""Parse the translation and detected source language from a Web response."""
		data = json.loads(responseBody)
		if not isinstance(data, dict):
			raise ApiResponseError(_("Invalid DeepL Web response."))

		message = data.get("message")
		if isinstance(message, str) and message:
			raise ApiResponseError(message)

		translations = data.get("translations")
		if not isinstance(translations, list) or not translations:
			raise ApiResponseError(_("Invalid API response or no translation result included."))

		translatedTexts: list[str] = []
		for item in translations:
			if not isinstance(item, dict) or not isinstance(item.get("text"), str):
				raise ApiResponseError(_("Invalid API response or no translation result included."))
			translatedTexts.append(item["text"])
		if not any(translatedTexts):
			raise ApiResponseError(_("Invalid API response or no translation result included."))

		firstResult = translations[0]
		detectedLanguage = firstResult.get("detected_source_language")
		if isinstance(detectedLanguage, str):
			detectedLanguage = self._normalizeDetectedLanguage(detectedLanguage)
		else:
			detectedLanguage = None
		return {
			"translation": "\n".join(translatedTexts),
			"langDetected": detectedLanguage,
		}
