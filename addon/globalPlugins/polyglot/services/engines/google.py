# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
import urllib.parse
import addonHandler

from ...common import languages
from ..engine import BaseHttpEngine

addonHandler.initTranslation()


class GoogleTranslateEngine(BaseHttpEngine):
	"""Translate text through Google's key-free endpoint or configured mirror."""

	id = "google"
	name = _("Google Translate (key-free)")

	BASE_URL = "https://translate.googleapis.com"
	MIRROR_URL = "https://translate.googleapis.mirror.nvdadr.com"

	@property
	def maxRequestLength(self) -> int:
		"""
		Empirical testing (EN->ZH) revealed a limit of 11,440 characters for the gtx endpoint.
		Even with POST requests, we maintain this limit as a safe threshold to prevent
		'413 Payload Too Large' errors from Google's gateway.
		"""
		return 11440

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "zh-CN"

	def getConfigSpec(self) -> list[dict]:
		spec = super().getConfigSpec()
		spec.extend(
			[
				{
					"id": "useMirror",
					"label": _("Use mirror server (translate.googleapis.mirror.nvdadr.com)"),
					"type": "checkbox",
					"default": False,
				},
			],
		)
		return spec

	def getSupportedLanguages(self) -> dict:
		return languages.getLanguageDictForCodes(languages.GOOGLE_TRANSLATE_CODES)

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		baseUrl = self.MIRROR_URL if config.get("useMirror", False) else self.BASE_URL
		url = f"{baseUrl}/translate_a/single?client=gtx&sl={langFrom}&tl={langTo}&dt=t"
		data = urllib.parse.urlencode({"q": text}).encode("utf-8")
		return {
			"method": "POST",
			"url": url,
			"headers": {"Content-Type": "application/x-www-form-urlencoded"},
			"data": data,
		}

	def _parseResponse(self, responseBody: str) -> dict:
		data = json.loads(responseBody)
		if not data or not data[0]:
			raise ValueError("No translation found in response.")
		translatedText = "".join(item[0] for item in data[0] if item[0])
		detectedLang = data[2] if len(data) > 2 and isinstance(data[2], str) else None
		return {"translation": translatedText, "langDetected": detectedLang}
