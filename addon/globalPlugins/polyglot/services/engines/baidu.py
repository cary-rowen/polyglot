# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import hashlib
import json
import random
import urllib.parse

import addonHandler

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import EngineError

addonHandler.initTranslation()


class BaiduTranslateEngine(BaseHttpEngine):
	"""Translate text through Baidu's authenticated translation API."""

	id = "baidu"
	name = _("Baidu Translate")

	API_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"
	ERROR_CODES = {
		"52001": _("Request timed out"),
		"52002": _("System error"),
		"52003": _("Unauthorized user. Please check your App ID or if the service is enabled."),
		"54000": _("Required parameter is missing"),
		"54001": _("Signature error. Please check your App Secret."),
		"54003": _("Access frequency limited"),
		"54004": _("Insufficient account balance"),
		"54005": _("Frequent long query requests"),
		"58000": _("Invalid client IP"),
		"58001": _("Translation direction not supported (may be due to insufficient permissions)"),
		"58002": _("Service is currently disabled"),
		"58003": _("IP has been blocked"),
		"90107": _("Authentication failed or has not taken effect"),
		"20003": _("Request content poses a security risk"),
	}

	@property
	def maxRequestLength(self) -> int:
		return 6000

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "zh"

	def getConfigSpec(self) -> list[dict]:
		spec = super().getConfigSpec()
		# Add engine-specific settings.
		spec.extend(
			[
				{"id": "appId", "label": "App ID", "type": "text", "default": ""},
				{"id": "appSecret", "label": "App Secret", "type": "password", "default": ""},
				{
					"id": "useTermbase",
					"label": _(
						"Use custom terminology (requires authentication and configuration on the platform)",
					),
					"type": "checkbox",
					"default": False,
				},
			],
		)
		return spec

	def getSupportedLanguages(self) -> dict:
		supportedCodes = [
			"auto",
			"zh",
			"en",
			"yue",
			"wyw",
			"jp",
			"kor",
			"fra",
			"spa",
			"th",
			"ara",
			"ru",
			"pt",
			"de",
			"it",
			"el",
			"nl",
			"pl",
			"bul",
			"est",
			"dan",
			"fin",
			"cs",
			"rom",
			"slo",
			"swe",
			"hu",
			"cht",
			"vie",
		]
		return languages.getLanguageDictForCodes(supportedCodes)

	def _makeSign(self, text, salt, appId, appSecret):
		signStr = appId + text + str(salt) + appSecret
		return hashlib.md5(signStr.encode("utf-8")).hexdigest()

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		appId = config.get("appId")
		appSecret = config.get("appSecret")
		if not appId or not appSecret:
			raise EngineError(_("App ID and App Secret are required."))

		salt = random.randint(32768, 65536)
		sign = self._makeSign(text, salt, appId, appSecret)

		if langFrom in ("zh-CN", "zh-TW"):
			langFrom = "zh"
		if langTo == "zh-CN":
			langTo = "zh"
		if langTo == "zh-TW":
			langTo = "cht"

		params = {"q": text, "from": langFrom, "to": langTo, "appid": appId, "salt": salt, "sign": sign}
		if config.get("useTermbase", False):
			params["needIntervene"] = 1

		return {
			"method": "POST",
			"url": self.API_URL,
			"headers": {"Content-Type": "application/x-www-form-urlencoded"},
			"data": urllib.parse.urlencode(params).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict:
		result = json.loads(responseBody)

		if "error_code" in result:
			errorCode = result["error_code"]
			message = self.ERROR_CODES.get(errorCode, result.get("error_msg", _("Unknown API error")))
			raise EngineError(f"{message} (Code: {errorCode})")

		translatedText = "\n".join(item["dst"] for item in result["trans_result"])
		detectedLang = result.get("from")

		return {"translation": translatedText, "langDetected": detectedLang}
