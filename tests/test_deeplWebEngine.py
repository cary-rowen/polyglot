# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for DeepL's anonymous oneshot translation endpoint."""

import json
import unittest
from unittest.mock import Mock, patch

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from polyglot.common.exceptions import ApiResponseError  # noqa: E402
from polyglot.services.engines.deeplWeb import DeepLWebTranslateEngine  # noqa: E402


class DeepLWebTranslateEngineTest(unittest.TestCase):
	"""Check request construction, chunking, and response parsing for DeepL Web."""

	def setUp(self) -> None:
		"""Create the engine used by each check."""
		self.engine = DeepLWebTranslateEngine()

	def test_buildsMappedRequest(self) -> None:
		"""Generic and regional codes become valid oneshot codes."""
		params = self.engine._buildRequestParams("a &lt; b", "en", "zh-Hant", {})

		self.assertEqual(params["method"], "POST")
		self.assertEqual(params["url"], self.engine.API_URL)
		self.assertEqual(params["headers"]["Authorization"], "None")
		self.assertEqual(
			json.loads(params["data"].decode("utf-8")),
			{
				"text": ["a &lt; b"],
				"target_lang": "zh-Hant",
				"source_lang": "en",
				"usage_type": "Translate",
			},
		)

	def test_omitsSourceForAutomaticDetection(self) -> None:
		"""Automatic detection omits source_lang and maps generic targets."""
		params = self.engine._buildRequestParams("hello", "auto", "en", {})
		payload = json.loads(params["data"].decode("utf-8"))

		self.assertEqual(payload["target_lang"], "en-US")
		self.assertNotIn("source_lang", payload)

	def test_rejectsUnknownLanguage(self) -> None:
		"""Unsupported codes fail before a request reaches the endpoint."""
		for target in ("xx", "auto"):
			with self.subTest(target=target), self.assertRaises(ApiResponseError):
				self.engine._buildRequestParams("hello", "auto", target, {})

	def test_countsUtf16UnitsWhenChunking(self) -> None:
		"""Supplementary characters consume two UTF-16 units against the 1,500 limit."""
		text = "😀" * 751
		translateChunk = Mock(side_effect=lambda chunk, *args: {"translation": chunk, "langDetected": "en"})
		with (
			patch.object(self.engine, "_translateChunk", translateChunk),
			patch("polyglot.services.engine.Beep.reportProgress"),
			patch("polyglot.services.engine.time.sleep"),
		):
			result = self.engine.translate(text, "auto", "en", {})

		self.assertEqual(result["translation"], text)
		self.assertEqual(
			[len(call.args[0].encode("utf-16-le")) // 2 for call in translateChunk.call_args_list],
			[1500, 2],
		)

	def test_matchesOnlyBaseDetectionForRegionalTargets(self) -> None:
		"""Base detection matches a regional target without merging dialects."""
		self.assertTrue(self.engine.areLanguagesEquivalent("en", "en-US"))
		self.assertTrue(self.engine.areLanguagesEquivalent("zh", "zh-Hans"))
		self.assertFalse(self.engine.areLanguagesEquivalent("pt-BR", "pt-PT"))
		self.assertFalse(self.engine.areLanguagesEquivalent("zh-Hans", "zh-Hant"))

	def test_parsesResponseAndRejectsMissingTranslation(self) -> None:
		"""Valid responses extract text and detection; empty results raise an API error."""
		responseBody = json.dumps({"translations": [{"detected_source_language": "en", "text": "Hallo"}]})
		self.assertEqual(
			self.engine._parseResponse(responseBody),
			{"translation": "Hallo", "langDetected": "en"},
		)
		with self.assertRaises(ApiResponseError):
			self.engine._parseResponse('{"translations": []}')


if __name__ == "__main__":
	unittest.main()
