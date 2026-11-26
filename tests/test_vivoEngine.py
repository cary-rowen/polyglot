# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for Vivo's translation request format."""

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from polyglot.services.engines.vivo import VivoTranslateEngine  # noqa: E402


class VivoTranslateEngineTest(unittest.TestCase):
	"""Check the required fields of Vivo's current translation endpoint."""

	def test_buildsNewApiRequest(self) -> None:
		"""The request uses the current endpoint, signature URI, and identity fields."""
		engine = VivoTranslateEngine()
		with patch(
			"polyglot.services.engines.vivo.vivoAuth.genSignHeaders",
			return_value={"X-AI-GATEWAY-SIGNATURE": "signature"},
		) as genSignHeaders:
			params = engine._buildRequestParams(
				"hello",
				"en",
				"zh-CHS",
				{"nvdacnUser": "user", "nvdacnPass": "pass"},
			)

		genSignHeaders.assert_called_once_with("user", "pass", "POST", "/translation/query", {})
		body = {key: values[0] for key, values in parse_qs(params["data"].decode("utf-8")).items()}
		requestId = body.pop("requestId", "")
		self.assertTrue(requestId)
		self.assertEqual(params["url"], "https://api-ai.vivo.com.cn/translation/query")
		self.assertEqual(
			body,
			{
				"from": "en",
				"to": "zh-CHS",
				"text": "hello",
				"app": "accessible",
				"sysVer": "PD1709",
				"product": "PD1709",
				"model": "vivoX20",
				"appVer": "1.0",
				"fr": "vivo_translator",
				"userId": "accessible_NV",
			},
		)
		self.assertEqual(engine.maxRequestLength, 1200)


if __name__ == "__main__":
	unittest.main()
