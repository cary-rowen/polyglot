# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
import hashlib
import time
import urllib.parse
from typing import Any

import addonHandler
from logHandler import log

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError, EngineError, ResponseParsingError

addonHandler.initTranslation()


class NiutransTranslateEngine(BaseHttpEngine):
	"""
	An engine for the Niutrans v2.0 API.
	It supports 'auto' for the source language but does not report the detected language.
	It also supports an optional bilingual alignment mode with configurable output order.
	"""

	id = "niutrans"
	name = _("Niutrans")

	API_URL_STANDARD = "https://api.niutrans.com/v2/text/translate"
	API_URL_BILINGUAL = "https://api.niutrans.com/v2/text/translate/bilingual"

	ERROR_CODES = {
		"404": _("Request address does not exist"),
		"10001": _("Request is too frequent, exceeding QPS limit"),
		"10003": _("Request string length exceeds the limit"),
		"10005": _("Source language encoding is not UTF-8"),
		"13001": _("Insufficient character allowance or no access permission"),
		"13003": _("Content filtering exception"),
		"13005": _("Source and target languages are the same"),
		"13007": _("Language not supported"),
		"13008": _("Request processing timeout"),
		"20001": _("Authentication failed"),
		"20002": _("Parameters do not conform to specifications"),
		"20003": _(
			"Parameter validation exception (e.g., from/to/srcText/appId/authStr/timestamp cannot be empty)",
		),
		"000000": _("Incorrect request parameters"),
		"000001": _("Unsupported parameter passing method"),
	}

	@property
	def maxRequestLength(self) -> int:
		return 5000

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "en"

	@property
	def doesReportDetectedLanguage(self) -> bool:
		return False

	def getSupportedLanguages(self) -> dict:
		supportedCodes = [
			"auto",
			"zh",
			"en",
			"sq",
			"ar",
			"am",
			"acu",
		]
		return languages.getLanguageDictForCodes(supportedCodes)

	def getConfigSpec(self) -> list[dict]:
		spec = super().getConfigSpec()
		spec.extend(
			[
				{"id": "appId", "label": _("App ID"), "type": "text", "default": ""},
				{"id": "apikey", "label": _("API Key (for signing)"), "type": "password", "default": ""},
				{
					"id": "enableBilingual",
					"label": _("Enable bilingual alignment mode"),
					"type": "checkbox",
					"default": False,
				},
				# Add a choice for the bilingual output order.
				{
					"id": "bilingualOrder",
					"label": _("Bilingual output order:"),
					"type": "choice",
					"choices": {
						"src_first": _("Source -> Target"),
						"tgt_first": _("Target -> Source"),
					},
					"default": "src_first",
				},
			],
		)
		return spec

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, Any]:
		"""Control bilingual-order visibility from the bilingual-mode setting."""
		states = super().getUiStates(allConfigs)
		isBilingualEnabled = allConfigs.get("enableBilingual", False)
		# The bilingual order dropdown is only visible if bilingual mode is enabled.
		states["bilingualOrder"] = {"visible": isBilingualEnabled}
		return states

	def _generateAuthStr(self, params: dict, apikey: str) -> str:
		"""Generate the authentication signature required by the v2.0 API."""
		paramsWithApikey = params.copy()
		paramsWithApikey["apikey"] = apikey

		sortedParams = sorted(paramsWithApikey.items(), key=lambda x: x[0])

		paramStr = "&".join([f"{key}={value}" for key, value in sortedParams])

		md5 = hashlib.md5()
		md5.update(paramStr.encode("utf-8"))
		authStr = md5.hexdigest()

		return authStr

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		"""Build request parameters for the Niutrans v2.0 API."""
		appId = config.get("appId", "").strip()
		apiKey = config.get("apikey", "").strip()
		if not appId or not apiKey:
			raise AuthenticationError(_("App ID and API Key for Niutrans must be configured."))

		useBilingualMode = config.get("enableBilingual", False)
		url = self.API_URL_BILINGUAL if useBilingualMode else self.API_URL_STANDARD

		timestamp = str(int(time.time()))
		paramsForSigning = {
			"from": langFrom,
			"to": langTo,
			"appId": appId,
			"srcText": text,
			"timestamp": timestamp,
		}

		authStr = self._generateAuthStr(paramsForSigning, apiKey)

		finalPayload = paramsForSigning.copy()
		finalPayload["authStr"] = authStr

		return {
			"method": "POST",
			"url": url,
			"headers": {"Content-Type": "application/x-www-form-urlencoded"},
			"data": urllib.parse.urlencode(finalPayload).encode("utf-8"),
		}

	def _translateChunk(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		"""Translate a chunk while passing configuration to the response parser."""
		try:
			params = self._buildRequestParams(text, langFrom, langTo, config)
			log.debug("Engine '%s' is sending a %s request.", self.id, params.get("method", "GET"))

			proxyMode = config.get("proxyMode", "system")
			proxiesDict = None
			if proxyMode == "none":
				proxiesDict = {"http": None, "https": None}
			timeoutInt = int(config.get("timeout", "15"))

			from ...common.network import sendRequest

			responseBody = sendRequest(
				method=params.get("method", "GET"),
				url=params["url"],
				headers=params.get("headers"),
				data=params.get("data"),
				timeout=timeoutInt,
				proxies=proxiesDict,
			)
			return self._parseResponse(responseBody, config)
		except json.JSONDecodeError as e:
			log.exception("Failed to parse JSON response from '%s'.", self.id)
			raise ResponseParsingError(_("Failed to parse response from translation service.")) from e
		except EngineError:
			raise
		except Exception as e:
			log.exception("An unexpected error occurred in '%s' engine.", self.id)
			raise EngineError(_("An unknown error occurred during translation.")) from e

	def _parseResponse(self, responseBody: str, config: dict) -> dict:
		"""Parse a Niutrans v2.0 response into the common result."""
		try:
			data = json.loads(responseBody)
		except json.JSONDecodeError:
			raise ApiResponseError(_("Failed to parse API response. Response was not valid JSON."))

		if "errorCode" in data:
			errorCode = data.get("errorCode")
			errorMsg = self.ERROR_CODES.get(errorCode, data.get("errorMsg", "Unknown API error"))
			raise ApiResponseError(f"{errorMsg} (Code: {errorCode})")

		useBilingualMode = config.get("enableBilingual", False)

		if useBilingualMode:
			alignData = data.get("align")
			if alignData:
				bilingualOrder = config.get("bilingualOrder", "src_first")
				bilingualPairs = []
				for paraKey in sorted(alignData.keys()):
					paragraph = alignData[paraKey]
					if not isinstance(paragraph, dict):
						continue
					for sentKey in sorted(paragraph.keys()):
						sentencePair = paragraph[sentKey]
						srcText = sentencePair.get("src", "")
						tgtText = sentencePair.get("tgt", "")
						# Conditionally format the output based on the user's choice.
						if bilingualOrder == "tgt_first":
							bilingualPairs.append(f"{tgtText}\n{srcText}")
						else:  # Default to source first.
							bilingualPairs.append(f"{srcText}\n{tgtText}")

				finalText = "\n\n".join(bilingualPairs)
				return {"translation": finalText.strip(), "langDetected": None}
			else:
				log.warning("Bilingual mode enabled, but 'align' field was not found in the response.")
				translatedText = data.get("tgtText", "")
				return {"translation": translatedText.strip(), "langDetected": None}

		translatedText = data.get("tgtText")
		if translatedText is not None:
			return {"translation": translatedText.strip(), "langDetected": None}
		else:
			raise ApiResponseError(_("Invalid API response or no translation result included."))
