# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Small runnable checks for OpenRouter model presets and prompt selection."""

import json
import unittest
from typing import Any

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from polyglot.services.engines.openRouter import OpenRouterTranslateEngine  # noqa: E402


class OpenRouterModelDefaultsTest(unittest.TestCase):
	"""Check the shipped presets and the prompt template chosen for them."""

	def setUp(self) -> None:
		"""Create the engine and a minimal working configuration."""
		self.engine = OpenRouterTranslateEngine()
		self.config: dict[str, Any] = {
			"apiUrl": "https://openrouter.ai/api/v1/chat/completions",
			"apiKey": "test-key",
			"modelNamePreset": OpenRouterTranslateEngine.DEFAULT_MODEL,
			"modelNameCustom": "",
			"promptMode": "simple",
		}

	def _getSpecItem(self, itemId: str) -> dict[str, Any]:
		"""Return the configuration specification entry with the given id."""
		for item in self.engine.getConfigSpec():
			if item["id"] == itemId:
				return item
		raise AssertionError(f"No configuration item '{itemId}'.")

	def test_presetDefaultsAreConsistent(self) -> None:
		"""Default model, translation-only models, and default prompt mode stay consistent."""
		defaultModel = self._getSpecItem("modelNamePreset")["default"]
		self.assertEqual(defaultModel, OpenRouterTranslateEngine.DEFAULT_MODEL)
		self.assertIn(defaultModel, OpenRouterTranslateEngine.PRESET_MODELS)
		self.assertIn(defaultModel, OpenRouterTranslateEngine.TRANSLATION_ONLY_MODELS)
		self.assertTrue(
			OpenRouterTranslateEngine.TRANSLATION_ONLY_MODELS.issubset(
				OpenRouterTranslateEngine.PRESET_MODELS,
			),
		)
		self.assertIn(
			self._getSpecItem("promptMode")["default"],
			self.engine._getPromptModeChoices(defaultModel),
		)

	def test_structuredPromptIsHiddenForTranslationOnlyModels(self) -> None:
		"""Only models that can answer with JSON offer the structured template."""
		states = self.engine.getUiStates(self.config)
		self.assertNotIn("json_structured", states["promptMode"]["choices"])
		self.config["modelNamePreset"] = "google/gemini-2.5-flash-lite"
		states = self.engine.getUiStates(self.config)
		self.assertIn("json_structured", states["promptMode"]["choices"])

	def test_autoSwapIsShownOnlyWhenLanguageDetectionIsAvailable(self) -> None:
		"""Auto-swap controls are hidden unless the effective prompt reports the source language."""
		self.config.update({"langFrom": "auto", "langTo": "en", "enableAutoSwap": True})
		for modelName, promptMode, isVisible in (
			(OpenRouterTranslateEngine.DEFAULT_MODEL, "simple", False),
			("inception/mercury-2", "simple", False),
			("inception/mercury-2", "json_structured", True),
		):
			with self.subTest(model=modelName, prompt=promptMode):
				self.config.update({"modelNamePreset": modelName, "promptMode": promptMode})
				states = self.engine.getUiStates(self.config)
				self.assertEqual(states["enableAutoSwap"]["visible"], isVisible)
				self.assertEqual(states["swapLanguage"]["visible"], isVisible)

	def test_structuredPromptFallsBackOnlyForTranslationOnlyModels(self) -> None:
		"""Structured JSON downgrades to simple for text-only models and stays for capable ones."""
		self.config["promptMode"] = "json_structured"
		for modelName, expectedSystem in (
			(OpenRouterTranslateEngine.DEFAULT_MODEL, OpenRouterTranslateEngine.PROMPT_SIMPLE_SYSTEM),
			("inception/mercury-2", OpenRouterTranslateEngine.PROMPT_JSON_STRUCTURED_SYSTEM),
		):
			with self.subTest(model=modelName):
				self.config["modelNamePreset"] = modelName
				params = self.engine._buildRequestParams("hello", "auto", "fr", self.config)
				payload = json.loads(params["data"].decode("utf-8"))
				self.assertEqual(payload["model"], modelName)
				self.assertEqual(payload["messages"][0]["content"], expectedSystem)
				self.assertIn("hello", payload["messages"][1]["content"])

	def test_retiredPresetsAreReplaced(self) -> None:
		"""A stored preset that OpenRouter retired resolves to a model that still exists."""
		for retired, replacement in OpenRouterTranslateEngine.RETIRED_MODEL_REPLACEMENTS.items():
			with self.subTest(model=retired):
				self.assertNotIn(retired, OpenRouterTranslateEngine.PRESET_MODELS)
				self.assertIn(replacement, OpenRouterTranslateEngine.PRESET_MODELS)
				self.config["modelNamePreset"] = retired
				params = self.engine._buildRequestParams("hello", "auto", "fr", self.config)
				payload = json.loads(params["data"].decode("utf-8"))
				self.assertEqual(payload["model"], replacement)

	def test_customModelKeepsItsPromptChoices(self) -> None:
		"""A custom model name is trimmed, sent verbatim, and keeps every prompt template."""
		self.config["modelNamePreset"] = "custom"
		self.config["modelNameCustom"] = " my-org/my-model "
		params = self.engine._buildRequestParams("hello", "auto", "fr", self.config)
		payload = json.loads(params["data"].decode("utf-8"))
		self.assertEqual(payload["model"], "my-org/my-model")
		self.assertIn("json_structured", self.engine._getPromptModeChoices("my-org/my-model"))


if __name__ == "__main__":
	unittest.main()
