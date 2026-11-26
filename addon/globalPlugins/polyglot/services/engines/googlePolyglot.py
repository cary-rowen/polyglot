# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import html
import json

import addonHandler

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError

addonHandler.initTranslation()


class GoogleHQTranslateEngine(BaseHttpEngine):
	"""Translate text through the authenticated Polyglot Google endpoint."""

	id = "googlePolyglot"
	name = _("Google Translate (Polyglot)")

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "zh-CN"

	def getSupportedLanguages(self) -> dict:
		return languages.getLanguageDictForCodes(languages.GOOGLE_TRANSLATE_CODES)

	def getConfigSpec(self) -> list[dict]:
		spec = super().getConfigSpec()
		spec.extend(
			[
				{
					"id": "apiKey",
					"label": _("API Key"),
					"type": "password",
					"default": "3a64ad20-724b-41dc-ba23-cf64185dbfa3",
				},
				{
					"id": "customUrl",
					"label": _("Endpoint URL"),
					"type": "text",
					"default": "https://translate.googleapis.mirror.nvdadr.com/polyglotGoogle",
				},
			],
		)
		return spec

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		apiKey = config.get("apiKey", "3a64ad20-724b-41dc-ba23-cf64185dbfa3").strip()
		if not apiKey:
			raise AuthenticationError(_("API Key for Google Translate (HQ) is not configured."))
		url = config.get("customUrl", "https://translate.googleapis.mirror.nvdadr.com/polyglotGoogle").strip()
		bodyData = [[[text], langFrom, langTo], "wt_lib"]

		if "mirror.nvdadr.com" in url:
			headers = {
				"Content-Type": "application/json+protobuf",
				"User-Agent": "NVDAPolyglot/1.0",
				"X-Mirror-Token": apiKey,
			}
			finalUrl = url
		else:
			headers = {
				"Content-Type": "application/json+protobuf",
				"User-Agent": "Mozilla/5.0",
			}
			finalUrl = f"{url}?key={apiKey}"

		return {
			"method": "POST",
			"url": finalUrl,
			"headers": headers,
			"data": json.dumps(bodyData).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict:
		"""
		Parse the nested array response returned by the endpoint
		when receiving a protobuf-style request.
		Expected format: [["Translated text..."], ["detected_lang_code"]]
		"""
		try:
			data = json.loads(responseBody)
		except json.JSONDecodeError:
			raise ApiResponseError(_("Failed to parse API response.")) from None
		try:
			rawTranslatedText = data[0][0]
			translatedText = html.unescape(rawTranslatedText)
		except (IndexError, TypeError):
			if isinstance(data, dict) and "error" in data:
				errorMsg = data["error"].get("message", "Unknown API error")
				raise ApiResponseError(errorMsg)
			raise ApiResponseError(_("Invalid API response or no translation text included."))
		detectedLang = None
		if len(data) > 1 and isinstance(data[1], list) and data[1]:
			detectedLang = data[1][0]
		return {"translation": translatedText, "langDetected": detectedLang}
