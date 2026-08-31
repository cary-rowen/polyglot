# -*- coding: utf-8 -*-

# Copyright (C) 2025-2026 cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
import time
import urllib.parse

import addonHandler
import requests
from logHandler import log

from ...common import languages
from ...common.network import getSession
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError, EngineError

addonHandler.initTranslation()


class MicrosoftTranslateEngine(BaseHttpEngine):
	"""
	An engine for Microsoft Translator, simulating requests from the Edge browser.
	This engine does not require a user-provided API key. It fetches a temporary
	authentication token automatically.
	"""

	id = "microsoft"
	name = _("Microsoft Translator (key-free)")

	# Class-level cache for the authentication token
	_tokenCache = {"token": None, "expiry": 0}

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
	def defaultTargetLanguage(self) -> str:
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

	def _getAuthToken(self, config: dict) -> str:
		"""
		Fetch or return a cached token from Microsoft's authentication service.
		The token is typically valid for 10 minutes.
		"""
		# Check if we have a valid, non-expired token
		if self._tokenCache["token"] and self._tokenCache["expiry"] > time.time():
			return self._tokenCache["token"]

		url = "https://edge.microsoft.com/translate/auth"
		headers = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
		}

		proxyMode = config.get("proxyMode", "system")
		proxiesDict = {"http": None, "https": None} if proxyMode == "none" else None
		timeoutInt = int(config.get("timeout", "15"))

		try:
			response = getSession().get(
				url,
				headers=headers,
				proxies=proxiesDict,
				timeout=timeoutInt,
			)
			response.raise_for_status()
			token = response.text

			# Cache the token and set its expiry time (e.g., 9 minutes to be safe)
			self._tokenCache["token"] = token
			self._tokenCache["expiry"] = time.time() + 9 * 60

			return token
		except Exception as e:
			log.error("Failed to fetch Microsoft Translator auth token (%s).", type(e).__name__)
			# Clear cache on failure
			self._tokenCache["token"] = None
			self._tokenCache["expiry"] = 0
			raise AuthenticationError(_("Could not get Microsoft Translator authentication token.")) from None

	def _translateChunk(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		"""Translate a chunk using Microsoft's two-step token authentication."""
		try:
			# Step 1: Get the authentication token
			authToken = self._getAuthToken(config)

			# Step 2: Build and send the translation request
			params = self._buildRequestParams(text, langFrom, langTo, config, authToken)

			proxyMode = config.get("proxyMode", "system")
			proxiesDict = {"http": None, "https": None} if proxyMode == "none" else None
			timeoutInt = int(config.get("timeout", "15"))

			# Use the shared session directly to avoid complexity with our network wrapper for
			# this flow, while still reusing the pooled connection.
			response = getSession().post(
				url=params["url"],
				headers=params["headers"],
				data=params["data"],
				proxies=proxiesDict,
				timeout=timeoutInt,
			)
			response.raise_for_status()
			responseBody = response.text

			return self._parseResponse(responseBody)
		except requests.exceptions.HTTPError as e:
			# If the error is 401 Unauthorized, our token has likely expired. Clear it.
			if e.response.status_code == 401:
				log.warning("Microsoft Translator returned 401 Unauthorized. Clearing token cache.")
				self._tokenCache["token"] = None
				self._tokenCache["expiry"] = 0
			# Re-raise as our custom exception type
			raise ApiResponseError(f"HTTP Error: {e.response.status_code}") from None
		except (ApiResponseError, EngineError):
			raise
		except Exception as e:
			log.error("An unexpected error occurred in '%s' engine (%s).", self.id, type(e).__name__)
			raise EngineError(_("An unknown error occurred during translation.")) from None

	def _buildRequestParams(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict,
		authToken: str,
	) -> dict:
		"""Build request parameters for the Microsoft translation API."""
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
			"api-version": "3.0",
		}
		url = f"https://api-edge.cognitive.microsofttranslator.com/translate?{urllib.parse.urlencode(queryParams)}"

		body = [{"Text": text}]

		headers = {"Content-Type": "application/json", "Authorization": f"Bearer {authToken}"}

		return {"url": url, "headers": headers, "data": json.dumps(body).encode("utf-8")}

	def _parseResponse(self, responseBody: str) -> dict:
		"""Parse a Microsoft Translator response into the common result."""
		try:
			data = json.loads(responseBody)
		except json.JSONDecodeError:
			raise ApiResponseError(_("Failed to parse response from Microsoft Translator.")) from None

		try:
			# The response is a list of translation results
			firstResult = data[0]
			translationObj = firstResult["translations"][0]

			translatedText = translationObj["text"]
			detectedLangObj = firstResult.get("detectedLanguage")

			detectedLang = None
			if detectedLangObj:
				detectedLang = detectedLangObj.get("language")

			return {"translation": translatedText, "langDetected": detectedLang}
		except (KeyError, IndexError, TypeError):
			if "error" in data:
				errorMsg = data["error"].get("message", "Unknown API error")
				raise ApiResponseError(errorMsg)

			raise ApiResponseError(_("Invalid API response or no translation result included."))
