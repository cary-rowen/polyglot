# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
import urllib.parse
import uuid

import addonHandler

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError

addonHandler.initTranslation()


class YandexTranslateEngine(BaseHttpEngine):
	"""
	An engine that uses the public Yandex Translate API.
	This mimics the behavior of their Android client and requires no API key.
	"""

	id = "yandex"
	name = _("Yandex Translate")

	@property
	def maxRequestLength(self) -> int:
		"""
		Empirical testing (EN->ZH) revealed a limit of 10,240 characters.
		Because this engine uses 'application/x-www-form-urlencoded', non-ASCII characters
		(like Chinese) will inflate the payload size by up to 9x after URL encoding.
		We strictly limit it to 5,000 to prevent gateway rejection.
		"""
		return 5000

	@property
	def autoDetectCode(self) -> str | None:
		return ""

	@property
	def fallbackTargetLanguage(self) -> str:
		return "zh"

	@property
	def doesReportDetectedLanguage(self) -> bool:
		# The API response does not include the detected source language.
		return False

	def getSupportedLanguages(self) -> dict:
		supportedCodes = [
			"",
			"zh",
			"en",
			"ja",
			"ko",
			"fr",
			"es",
			"ru",
			"de",
			"it",
			"tr",
			"pt",
			"vi",
			"id",
			"th",
			"ms",
			"ar",
			"hi",
			"no",
			"fa",
			"sv",
			"pl",
			"nl",
			"uk",
			"he",
		]
		return languages.getLanguageDictForCodes(supportedCodes)

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		"""Build request parameters for the Yandex API."""
		baseUrl = "https://translate.yandex.net/api/v1/tr.json/translate"

		# Build query parameters for the URL
		queryParams = {
			"id": str(uuid.uuid4()).replace("-", "") + "-0-0",
			"srv": "android",
		}
		fullUrl = f"{baseUrl}?{urllib.parse.urlencode(queryParams)}"

		# Build the form data for the request body
		formData = {
			"source_lang": langFrom,
			"target_lang": langTo,
			"text": text,
		}

		return {
			"method": "POST",
			"url": fullUrl,
			"headers": {"Content-Type": "application/x-www-form-urlencoded"},
			"data": urllib.parse.urlencode(formData).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict:
		"""Parse a Yandex API response into the common translation result."""
		data = json.loads(responseBody)

		translatedTextList = data.get("text")

		if translatedTextList and isinstance(translatedTextList, list) and translatedTextList[0]:
			return {
				"translation": translatedTextList[0],
				"langDetected": None,  # API doesn't provide this
			}
		else:
			# Handle potential API errors if they are structured differently
			errorCode = data.get("code")
			errorMessage = data.get("message", "Unknown API error")
			if errorCode:
				raise ApiResponseError(f"{errorMessage} (Code: {errorCode})")
			raise ApiResponseError(_("Invalid API response or no translation result included."))
