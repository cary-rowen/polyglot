# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
import urllib.parse

import addonHandler

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError

addonHandler.initTranslation()


class MicrosoftTranslateEngine(BaseHttpEngine):
	"""Translate text through Microsoft's key-free Edge translation endpoint."""

	# No SLA; use official Azure when a contractual guarantee is required.

	id = "microsoft"
	name = _("Microsoft Translator (key-free)")

	@property
	def autoDetectCode(self) -> str | None:
		# The API expects an empty string for auto-detection
		return ""

	@property
	def maxRequestLength(self) -> int:
		"""
		The Microsoft Edge translation API has a character limit per request.
		Empirical testing (EN->ZH) revealed a hard limit of 50,000 characters.
		We set a safe buffer of 30,000 to prevent payload size bloat (when translating
		from multi-byte languages like Chinese) and to avoid network timeout issues.
		"""
		return 30000

	@property
	def fallbackTargetLanguage(self) -> str:
		return "zh-Hans"  # Microsoft's code for Simplified Chinese

	def getSupportedLanguages(self) -> dict:
		supportedCodes = [
			"",
			"zh-Hans",
			"zh-Hant",
			"en",
			"ja",
			"ko",
			"fr",
			"es",
			"ru",
			"de",
			"it",
			"pt",
			"ar",
			"th",
			"vi",
		]
		return languages.getLanguageDictForCodes(supportedCodes)

	def _buildRequestParams(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict,
	) -> dict:
		"""Build a request for Microsoft's unauthenticated Edge endpoint."""
		# Map our standard language codes to Microsoft's specific codes
		langMap = {
			"zh-CN": "zh-Hans",
			"zh-TW": "zh-Hant",
		}
		finalLangFrom = langMap.get(langFrom, langFrom)
		finalLangTo = langMap.get(langTo, langTo)

		queryParams = {
			"from": finalLangFrom,
			"to": finalLangTo,
			"isEnterpriseClient": "false",
		}
		url = f"https://edge.microsoft.com/translate/translatetext?{urllib.parse.urlencode(queryParams)}"
		body = [text]

		return {
			"method": "POST",
			"url": url,
			"headers": {"Content-Type": "application/json"},
			"data": json.dumps(body, ensure_ascii=False).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict:
		"""Parse a Microsoft Translator response into the common result."""
		try:
			data = json.loads(responseBody)
		except json.JSONDecodeError:
			raise ApiResponseError(_("Failed to parse response from Microsoft Translator.")) from None

		if not isinstance(data, list) or not data or not isinstance(data[0], dict):
			raise ApiResponseError(_("Invalid API response or no translation result included."))

		firstResult = data[0]
		translations = firstResult.get("translations")
		if not isinstance(translations, list) or not translations or not isinstance(translations[0], dict):
			raise ApiResponseError(_("Invalid API response or no translation result included."))

		translatedText = translations[0].get("text")
		if not isinstance(translatedText, str):
			raise ApiResponseError(_("Invalid API response or no translation result included."))

		detectedLangObj = firstResult.get("detectedLanguage")
		detectedLang = detectedLangObj.get("language") if isinstance(detectedLangObj, dict) else None
		return {"translation": translatedText, "langDetected": detectedLang}
