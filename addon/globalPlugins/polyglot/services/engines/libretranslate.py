# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
import urllib.parse
from typing import Any, cast

import addonHandler

from ...common import languages
from ...common.exceptions import ApiResponseError
from ..engine import BaseHttpEngine

addonHandler.initTranslation()


class LibreTranslateEngine(BaseHttpEngine):
	"""Translate text through a LibreTranslate-compatible HTTP server."""

	id = "libretranslate"
	# Translators: Name of the LibreTranslate translation engine.
	name = _("LibreTranslate")

	DEFAULT_SERVER_URL = "http://localhost:5000"
	MAX_REQUEST_LENGTH = 2000
	SUPPORTED_CODES = (
		"auto",
		"en",
		"sq",
		"ar",
		"az",
		"eu",
		"bn",
		"bg",
		"ca",
		"zh-Hans",
		"zh-Hant",
		"cs",
		"da",
		"nl",
		"eo",
		"et",
		"fi",
		"fr",
		"gl",
		"de",
		"el",
		"he",
		"hi",
		"hu",
		"id",
		"ga",
		"it",
		"ja",
		"ko",
		"ky",
		"lv",
		"lt",
		"ms",
		"nb",
		"fa",
		"pl",
		"pt",
		"pt-BR",
		"ro",
		"ru",
		"sr",
		"sk",
		"sl",
		"es",
		"sw",
		"sv",
		"tl",
		"th",
		"tr",
		"uk",
		"ur",
		"vi",
	)
	_LANGUAGE_ALIASES = {
		"pb": "pt-BR",
		"pt-br": "pt-BR",
		"zh": "zh-Hans",
		"zh-hans": "zh-Hans",
		"zh-hant": "zh-Hant",
		"zt": "zh-Hant",
	}

	@property
	def maxRequestLength(self) -> int:
		"""Return a conservative request size for public and self-hosted servers."""
		return self.MAX_REQUEST_LENGTH

	@property
	def autoDetectCode(self) -> str | None:
		"""Return the source code used by LibreTranslate for auto-detection."""
		return "auto"

	@property
	def defaultTargetLanguage(self) -> str:
		"""Return Simplified Chinese as the default target language."""
		return "zh-Hans"

	def getSupportedLanguages(self) -> dict[str, str]:
		"""Return the language codes supported by the current LibreTranslate models."""
		return languages.getLanguageDictForCodes(list(self.SUPPORTED_CODES))

	def getConfigSpec(self) -> list[dict[str, Any]]:
		"""Return common controls plus the LibreTranslate server settings."""
		spec = super().getConfigSpec()
		spec.extend(
			[
				{
					"id": "serverUrl",
					"label": _("LibreTranslate server URL:"),
					"type": "text",
					"default": self.DEFAULT_SERVER_URL,
				},
				{
					"id": "apiKey",
					"label": _("API key (optional):"),
					"type": "password",
					"default": "",
				},
			],
		)
		return spec

	def areLanguagesEquivalent(self, detectedLanguage: str, targetLanguage: str) -> bool:
		"""Treat an unqualified detected code as equivalent to a regional target."""
		detectedCode = self._normalizeLanguageCode(detectedLanguage)
		targetCode = self._normalizeLanguageCode(targetLanguage)
		return detectedCode.casefold() == targetCode.casefold() or (
			"-" not in detectedCode
			and languages.getLanguageFamily(detectedCode) == languages.getLanguageFamily(targetCode)
		)

	def _normalizeLanguageCode(self, code: str) -> str:
		"""Convert LibreTranslate and Argos aliases to Polyglot language codes."""
		return self._LANGUAGE_ALIASES.get(code.casefold(), code)

	def _getTranslateUrl(self, config: dict[str, Any]) -> str:
		"""Build and validate the translation endpoint URL from user settings."""
		serverUrl = str(config.get("serverUrl", self.DEFAULT_SERVER_URL) or "").strip()
		try:
			parsedUrl = urllib.parse.urlsplit(serverUrl)
		except ValueError as error:
			# Translators: Error shown when the configured LibreTranslate server address is invalid.
			raise ApiResponseError(
				_("LibreTranslate server URL must be a valid HTTP or HTTPS URL without a query or fragment."),
			) from error
		if (
			parsedUrl.scheme.casefold() not in {"http", "https"}
			or not parsedUrl.netloc
			or parsedUrl.query
			or parsedUrl.fragment
		):
			# Translators: Error shown when the configured LibreTranslate server address is invalid.
			raise ApiResponseError(
				_("LibreTranslate server URL must be a valid HTTP or HTTPS URL without a query or fragment."),
			)

		serverUrl = serverUrl.rstrip("/")
		return serverUrl if parsedUrl.path.rstrip("/").endswith("/translate") else f"{serverUrl}/translate"

	def _buildRequestParams(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
	) -> dict[str, Any]:
		"""Build a JSON request for the LibreTranslate translation endpoint."""
		payload: dict[str, Any] = {
			"q": text,
			"source": self._normalizeLanguageCode(langFrom),
			"target": self._normalizeLanguageCode(langTo),
			"format": "text",
		}
		apiKey = str(config.get("apiKey", "") or "").strip()
		if apiKey:
			payload["api_key"] = apiKey

		return {
			"method": "POST",
			"url": self._getTranslateUrl(config),
			"headers": {
				"Accept": "application/json",
				"Content-Type": "application/json",
			},
			"data": json.dumps(payload, ensure_ascii=False).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict[str, Any]:
		"""Parse LibreTranslate's translated text and optional detected language."""
		rawData: Any = json.loads(responseBody)
		if not isinstance(rawData, dict):
			# Translators: Error shown when LibreTranslate returns an unexpected JSON structure.
			raise ApiResponseError(_("Invalid LibreTranslate response."))
		data = cast(dict[str, Any], rawData)

		error = data.get("error")
		if isinstance(error, dict):
			error = cast(dict[str, Any], error).get("message")
		if isinstance(error, str) and error.strip():
			raise ApiResponseError(error.strip())

		translatedText = data.get("translatedText")
		if not isinstance(translatedText, str):
			# Translators: Error shown when LibreTranslate omits the translated text.
			raise ApiResponseError(_("Invalid LibreTranslate response or no translation result included."))

		detectedLanguage: Any = data.get("detectedLanguage")
		if isinstance(detectedLanguage, dict):
			detectedLanguage = cast(dict[str, Any], detectedLanguage).get("language")
		if isinstance(detectedLanguage, str):
			detectedLanguage = self._normalizeLanguageCode(detectedLanguage)
		else:
			detectedLanguage = None

		return {"translation": translatedText, "langDetected": detectedLanguage}
