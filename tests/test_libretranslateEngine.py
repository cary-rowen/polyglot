# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for the LibreTranslate HTTP engine."""

import json
import unittest

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from polyglot.common.exceptions import ApiResponseError  # noqa: E402
from polyglot.services.engines.libretranslate import LibreTranslateEngine  # noqa: E402


class LibreTranslateEngineTest(unittest.TestCase):
	"""Check LibreTranslate request construction and response parsing."""

	def setUp(self) -> None:
		"""Create the engine and a minimal HTTP configuration."""
		self.engine = LibreTranslateEngine()
		self.config = {"proxyMode": "none", "timeout": 15}

	def test_buildsLocalRequestWithoutOptionalApiKey(self) -> None:
		"""The default request targets the standard local server and omits an empty key."""
		params = self.engine._buildRequestParams("Hello", "auto", "zh-Hans", self.config)

		self.assertEqual(params["url"], "http://localhost:5000/translate")
		self.assertEqual(
			json.loads(params["data"].decode("utf-8")),
			{"q": "Hello", "source": "auto", "target": "zh-Hans", "format": "text"},
		)

	def test_buildsPrefixedServerRequestWithApiKey(self) -> None:
		"""A server path prefix, trailing /translate, and API key are preserved."""
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

	def test_parsesResponseAndServiceErrors(self) -> None:
		"""Successful responses normalize detection; error payloads raise ApiResponseError."""
		responseBody = json.dumps(
			{
				"translatedText": "你好",
				"detectedLanguage": {"confidence": 99.0, "language": "zh"},
			},
		)
		self.assertEqual(
			self.engine._parseResponse(responseBody),
			{"translation": "你好", "langDetected": "zh-Hans"},
		)
		with self.assertRaisesRegex(ApiResponseError, "API key"):
			self.engine._parseResponse('{"error":"Invalid API key"}')


if __name__ == "__main__":
	unittest.main()
