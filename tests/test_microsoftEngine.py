# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for Microsoft's key-free Edge translation endpoint."""

import json
import unittest
from unittest.mock import patch

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from polyglot.common.exceptions import ApiResponseError  # noqa: E402
from polyglot.services.engines.microsoft import MicrosoftTranslateEngine  # noqa: E402


class MicrosoftTranslateEngineTest(unittest.TestCase):
	"""Check request construction and response parsing for the Edge endpoint."""

	def setUp(self) -> None:
		"""Create the engine and a minimal HTTP configuration."""
		self.engine = MicrosoftTranslateEngine()
		self.config = {"proxyMode": "none", "timeout": 15}

	def test_buildsUnauthenticatedStringArrayRequest(self) -> None:
		"""The endpoint maps Chinese codes and sends a bare JSON string array."""
		params = self.engine._buildRequestParams("a &lt; b", "zh-CN", "zh-TW", self.config)

		self.assertEqual(params["method"], "POST")
		self.assertEqual(
			params["url"],
			"https://edge.microsoft.com/translate/translatetext?from=zh-Hans&to=zh-Hant&isEnterpriseClient=false",
		)
		self.assertEqual(json.loads(params["data"].decode("utf-8")), ["a &lt; b"])
		self.assertEqual(params["headers"], {"Content-Type": "application/json"})

	def test_translateChunkUsesSharedHttpFlowAndAutoDetect(self) -> None:
		"""BaseHttpEngine forwards auto-detect requests and proxyMode='none' to sendRequest."""
		responseBody = '[{"translations":[{"text":"translated"}]}]'
		with patch("polyglot.services.engine.sendRequest", return_value=responseBody) as sendRequest:
			result = self.engine._translateChunk("hello", "", "zh-Hans", self.config)

		sendRequest.assert_called_once()
		self.assertEqual(result, {"translation": "translated", "langDetected": None})
		self.assertIn(
			"/translate/translatetext?from=&to=zh-Hans&isEnterpriseClient=false",
			sendRequest.call_args.kwargs["url"],
		)
		self.assertEqual(sendRequest.call_args.kwargs["proxies"], {"http": None, "https": None})

	def test_parsesResponseAndRejectsMalformedBody(self) -> None:
		"""Detected language is retained without HTML unescaping; invalid payloads raise."""
		responseBody = '[{"detectedLanguage":{"language":"en"},"translations":[{"text":"Compare &lt; B"}]}]'
		self.assertEqual(
			self.engine._parseResponse(responseBody),
			{"translation": "Compare &lt; B", "langDetected": "en"},
		)
		with self.assertRaises(ApiResponseError):
			self.engine._parseResponse("{}")


if __name__ == "__main__":
	unittest.main()
