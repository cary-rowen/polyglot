# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
import urllib.parse
import uuid

import addonHandler

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError, EngineError, NetworkConnectionError
from . import _vivoAuth as vivoAuth

addonHandler.initTranslation()


class VivoTranslateEngine(BaseHttpEngine):
	"""Translate text through Vivo using signatures issued by NVDACN."""

	id = "vivo"
	name = _("VIVO Translate")

	API_URL = "https://api-ai.vivo.com.cn/translation/query"
	ERROR_CODES = {
		10000: _("Server error"),
		20000: _("Invalid request parameters"),
	}

	@property
	def maxRequestLength(self) -> int:
		"""Return the 1,200-character limit documented by the Vivo endpoint."""
		return 1200

	@property
	def autoDetectCode(self) -> str | None:
		"""This engine does not support automatic language detection."""
		return None

	@property
	def fallbackSourceLanguage(self) -> str:
		return "en"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "zh-CHS"

	def getConfigSpec(self) -> list[dict]:
		spec = super().getConfigSpec()
		spec.extend(
			[
				{"id": "nvdacnUser", "label": _("NVDACN Username"), "type": "text", "default": ""},
				{"id": "nvdacnPass", "label": _("NVDACN Password"), "type": "password", "default": ""},
			],
		)
		return spec

	def getSupportedLanguages(self) -> dict:
		supportedCodes = ["zh-CHS", "en", "ja", "ko"]
		return languages.getLanguageDictForCodes(supportedCodes)

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		nvdacnUser = config.get("nvdacnUser")
		nvdacnPass = config.get("nvdacnPass")
		if not nvdacnUser or not nvdacnPass:
			raise AuthenticationError(_("NVDACN username and password must be provided in settings."))

		uri = "/translation/query"
		try:
			headers = vivoAuth.genSignHeaders(nvdacnUser, nvdacnPass, "POST", uri, {})
			headers["Content-Type"] = "application/x-www-form-urlencoded"
		except NetworkConnectionError as e:
			raise EngineError(
				_(
					"Could not connect to the NVDACN authentication server to get a signature. Please check your network connection or try again later.",
				),
			) from e
		except AuthenticationError as e:
			# Translators: Error message when authentication with the translation service fails. {error} is the detailed error description.
			raise EngineError(_("Authentication failed: {error}").format(error=str(e))) from e
		except Exception as e:
			raise EngineError(_("An unknown error occurred while generating authentication info.")) from e

		bodyParams = {
			"from": langFrom,
			"to": langTo,
			"text": text,
			"app": "accessible",
			"sysVer": "PD1709",
			"product": "PD1709",
			"model": "vivoX20",
			"appVer": "1.0",
			"fr": "vivo_translator",
			"userId": "accessible_NV",
			"requestId": str(uuid.uuid4()),
		}
		return {
			"method": "POST",
			"url": self.API_URL,
			"headers": headers,
			"data": urllib.parse.urlencode(bodyParams).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict:
		result = json.loads(responseBody)
		if result.get("code") == 0 and "data" in result:
			translatedText = result["data"].get("translation")
			if translatedText is None:
				raise ApiResponseError(_("API response successful but did not contain a translation result."))
			return {"translation": translatedText, "langDetected": None}
		else:
			errorCode = result.get("code")
			errorMessage = self.ERROR_CODES.get(errorCode, result.get("msg", _("Unknown API error")))
			raise ApiResponseError(f"{errorMessage} (Code: {errorCode or 'N/A'})")
