# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json

import addonHandler

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError

addonHandler.initTranslation()


class CaiyunTranslateEngine(BaseHttpEngine):
	"""
	An engine for Caiyun AI Translation.
	Requires a token for authentication.
	"""

	id = "caiyun"
	name = _("Caiyun")

	@property
	def maxRequestLength(self) -> int:
		return 5000

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "zh"

	def getSupportedLanguages(self) -> dict:
		supportedCodes = [
			"auto",
			"zh",
			"zh-Hant",
			"en",
			"ja",
			"ko",
			"de",
			"es",
			"fr",
			"it",
			"pt",
			"ru",
			"tr",
			"vi",
		]
		return languages.getLanguageDictForCodes(supportedCodes)

	def getConfigSpec(self) -> list[dict]:
		"""Define the configuration options for this engine."""
		spec = super().getConfigSpec()
		spec.extend(
			[
				{"id": "token", "label": _("Authentication Token"), "type": "password", "default": ""},
			],
		)
		return spec

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		"""Build request parameters for the Caiyun API."""
		token = config.get("token", "").strip()
		if not token:
			raise AuthenticationError(_("Authentication Token for Caiyun is not configured."))

		url = "https://api.interpreter.caiyunai.com/v1/translator"

		body = {
			"source": [text],  # API expects a list of strings
			"trans_type": f"{langFrom}2{langTo}",
			"request_id": "translate-nvda-add-on",
			"detect": True if langFrom == "auto" else False,
		}

		headers = {"Content-Type": "application/json", "x-authorization": f"token {token}"}

		return {"method": "POST", "url": url, "headers": headers, "data": json.dumps(body).encode("utf-8")}

	def _parseResponse(self, responseBody: str) -> dict:
		"""Parse a Caiyun API response into the common translation result."""
		data = json.loads(responseBody)

		# Check for business logic errors first
		if "message" in data:
			raise ApiResponseError(data["message"])
		translatedList = data.get("target")
		if translatedList and isinstance(translatedList, list) and translatedList[0] is not None:
			detectedLang = None
			# Parse the detected source language from the trans_type field
			transType = data.get("trans_type")
			if transType and "2" in transType:
				# E.g. "en2zh" -> "en"
				detectedLang = transType.split("2")[0]

			return {"translation": translatedList[0], "langDetected": detectedLang}
		else:
			raise ApiResponseError(_("Invalid API response or no translation result included."))
