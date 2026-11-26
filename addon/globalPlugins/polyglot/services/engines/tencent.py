# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import hashlib
import hmac
import json
import time
from datetime import datetime

import addonHandler

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError

addonHandler.initTranslation()


class TencentTranslateEngine(BaseHttpEngine):
	"""Translate text through Tencent Cloud's signed translation API."""

	id = "tencent"
	name = _("Tencent Translate")

	@property
	def maxRequestLength(self) -> int:
		return 6000

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
			"zh-TW",
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
		]
		return languages.getLanguageDictForCodes(supportedCodes)

	def getConfigSpec(self) -> list[dict]:
		spec = super().getConfigSpec()
		spec.extend(
			[
				{"id": "secretId", "label": _("Secret ID"), "type": "text", "default": ""},
				{"id": "secretKey", "label": _("Secret Key"), "type": "password", "default": ""},
				{
					"id": "region",
					"label": _("Region:"),
					"type": "choice",
					"choices": {
						"ap-beijing": _("North China (Beijing)"),
						"ap-guangzhou": _("South China (Guangzhou)"),
						"ap-shanghai": _("East China (Shanghai)"),
						"ap-hongkong": _("Hong Kong, Macao and Taiwan (Hong Kong, China)"),
						"ap-singapore": _("Southeast Asia-Pacific (Singapore)"),
						"na-ashburn": _("US East (Ashburn)"),
					},
					"default": "ap-beijing",
				},
			],
		)
		return spec

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		secretId = config.get("secretId")
		secretKey = config.get("secretKey")
		if not secretId or not secretKey:
			raise AuthenticationError(_("Secret ID and Secret Key must be provided."))

		region = config.get("region", "ap-beijing")
		endpoint = f"tmt.{region}.tencentcloudapi.com"
		service = "tmt"
		action = "TextTranslate"
		version = "2018-03-21"
		timestamp = int(time.time())
		date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

		body = {
			"SourceText": text,
			"Source": langFrom,
			"Target": langTo,
			"ProjectId": 0,
		}
		payloadStr = json.dumps(body)
		hashedRequestPayload = hashlib.sha256(payloadStr.encode("utf-8")).hexdigest()
		httpRequestMethod = "POST"
		canonicalUri = "/"
		canonicalQueryString = ""
		canonicalHeaders = f"content-type:application/json\nhost:{endpoint}\n"
		signedHeaders = "content-type;host"

		canonicalRequest = (
			f"{httpRequestMethod}\n{canonicalUri}\n{canonicalQueryString}\n"
			f"{canonicalHeaders}\n{signedHeaders}\n{hashedRequestPayload}"
		)

		algorithm = "TC3-HMAC-SHA256"
		hashedCanonicalRequest = hashlib.sha256(canonicalRequest.encode("utf-8")).hexdigest()
		credentialScope = f"{date}/{service}/tc3_request"
		stringToSign = f"{algorithm}\n{timestamp}\n{credentialScope}\n{hashedCanonicalRequest}"

		def sha256Hmac(message, secret):
			return hmac.new(secret, message, digestmod=hashlib.sha256).digest()

		secretDate = sha256Hmac(date.encode("utf-8"), ("TC3" + secretKey).encode("utf-8"))
		secretService = sha256Hmac(service.encode("utf-8"), secretDate)
		secretSigning = sha256Hmac(b"tc3_request", secretService)
		signature = hmac.new(
			secretSigning,
			stringToSign.encode("utf-8"),
			digestmod=hashlib.sha256,
		).hexdigest()

		authorization = (
			f"{algorithm} Credential={secretId}/{credentialScope}, "
			f"SignedHeaders={signedHeaders}, Signature={signature}"
		)

		headers = {
			"Authorization": authorization,
			"Content-Type": "application/json",
			"Host": endpoint,
			"X-TC-Action": action,
			"X-TC-Timestamp": str(timestamp),
			"X-TC-Version": version,
			"X-TC-Region": region,
		}

		return {
			"method": "POST",
			"url": f"https://{endpoint}",
			"headers": headers,
			"data": payloadStr.encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict:
		data = json.loads(responseBody)
		response = data.get("Response", {})

		if "Error" in response and response["Error"]:
			error = response["Error"]
			errorCode = error.get("Code", "N/A")
			errorMessage = error.get("Message", _("Unknown API error"))
			if "AuthFailure" in errorCode:
				raise AuthenticationError(
					f"{_('Authentication failed')}: {errorMessage} (Code: {errorCode})",
				)
			else:
				raise ApiResponseError(f"{errorMessage} (Code: {errorCode})")

		translatedText = response.get("TargetText")
		detectedLang = response.get("Source")

		if translatedText is None:
			raise ApiResponseError(_("Invalid API response or no translation result included."))

		return {"translation": translatedText, "langDetected": detectedLang}
