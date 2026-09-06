# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for the LibreTranslate HTTP engine."""

import builtins
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if not hasattr(builtins, "_"):
	setattr(builtins, "_", lambda message: message)
for moduleName in ("config", "nvwave", "queueHandler", "tones", "ui"):
	sys.modules.setdefault(moduleName, ModuleType(moduleName))
globalVars = ModuleType("globalVars")
setattr(globalVars, "appArgs", Mock(configPath=str(PROJECT_ROOT)))
sys.modules.setdefault("globalVars", globalVars)
extensionPoints = ModuleType("extensionPoints")
setattr(extensionPoints, "Action", Mock)
sys.modules.setdefault("extensionPoints", extensionPoints)
addonHandler = ModuleType("addonHandler")
setattr(addonHandler, "initTranslation", Mock())
sys.modules.setdefault("addonHandler", addonHandler)
logHandler = ModuleType("logHandler")
setattr(logHandler, "log", Mock())
sys.modules.setdefault("logHandler", logHandler)
polyglotPackage = ModuleType("polyglot")
setattr(polyglotPackage, "__path__", [str(PROJECT_ROOT / "addon" / "globalPlugins" / "polyglot")])
sys.modules.setdefault("polyglot", polyglotPackage)

from polyglot.common.exceptions import ApiResponseError  # noqa: E402
from polyglot.services.engines.libretranslate import LibreTranslateEngine  # noqa: E402


class LibreTranslateEngineTest(unittest.TestCase):
	"""Check LibreTranslate request construction and response parsing."""

	def setUp(self) -> None:
		"""Create the engine and a minimal HTTP configuration."""
		self.engine = LibreTranslateEngine()
		self.config = {"proxyMode": "none", "timeout": 15}

	def test_exposesConfiguredLibreTranslateLanguages(self) -> None:
		"""The language list includes the configured LibreTranslate codes."""
		availableLanguages = self.engine.getSupportedLanguages()
		for code in ("auto", "en", "zh-Hans", "zh-Hant", "pt-BR", "ur"):
			with self.subTest(code=code):
				self.assertIn(code, availableLanguages)
		self.assertEqual(self.engine.maxRequestLength, 2000)

	def test_buildsLocalRequestWithoutOptionalApiKey(self) -> None:
		"""The default request targets the standard local server and omits an empty key."""
		params = self.engine._buildRequestParams("Hello", "auto", "zh-Hans", self.config)

		self.assertEqual(params["url"], "http://localhost:5000/translate")
		payload = json.loads(params["data"].decode("utf-8"))
		self.assertEqual(payload, {"q": "Hello", "source": "auto", "target": "zh-Hans", "format": "text"})

	def test_buildsPrefixedServerRequestWithApiKey(self) -> None:
		"""A server path prefix and API key are preserved in the request."""
		config = {"serverUrl": "https://example.test/lt/", "apiKey": "secret"}
		params = self.engine._buildRequestParams("Hello", "en", "de", config)

		self.assertEqual(params["url"], "https://example.test/lt/translate")
		self.assertEqual(json.loads(params["data"].decode("utf-8"))["api_key"], "secret")
		config["serverUrl"] = "https://example.test/lt/translate/"
		self.assertEqual(
			self.engine._buildRequestParams("Hello", "en", "de", config)["url"],
			"https://example.test/lt/translate",
		)

	def test_rejectsInvalidServerUrl(self) -> None:
		"""Malformed server settings fail before a network request is attempted."""
		for serverUrl in ("ftp://example.test", "http://[::1"):
			with self.subTest(serverUrl=serverUrl), self.assertRaises(ApiResponseError):
				self.engine._buildRequestParams("Hello", "en", "de", {"serverUrl": serverUrl})

	def test_parsesTranslationAndDetectedLanguage(self) -> None:
		"""The common result includes translated text and normalized detection."""
		responseBody = json.dumps(
			{
				"translatedText": "\u4f60\u597d",
				"detectedLanguage": {"confidence": 99.0, "language": "zh"},
			},
		)

		self.assertEqual(
			self.engine._parseResponse(responseBody),
			{"translation": "\u4f60\u597d", "langDetected": "zh-Hans"},
		)

	def test_parsesServiceError(self) -> None:
		"""An API error response becomes a user-facing engine error."""
		with self.assertRaisesRegex(ApiResponseError, "API key"):
			self.engine._parseResponse('{"error":"Invalid API key"}')

	def test_usesSharedBaseHttpRequestFlow(self) -> None:
		"""Translation uses the existing HTTP request, retry, and proxy flow."""
		with patch(
			"polyglot.services.engine.sendRequest", return_value='{"translatedText":"Hallo"}'
		) as sendRequest:
			result = self.engine._translateChunk("hello", "en", "de", self.config)

		sendRequest.assert_called_once()
		self.assertEqual(result, {"translation": "Hallo", "langDetected": None})
		self.assertEqual(sendRequest.call_args.kwargs["proxies"], {"http": None, "https": None})


if __name__ == "__main__":
	unittest.main()
