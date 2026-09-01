# Copyright (C) 2025-2026 cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Small runnable checks for OpenRouter model presets and prompt selection."""

import builtins
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import Mock


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
# Another test module may have installed the stub first; share whichever one the add-on imports.
logHandler = sys.modules["logHandler"]
polyglotPackage = ModuleType("polyglot")
setattr(polyglotPackage, "__path__", [str(PROJECT_ROOT / "addon" / "globalPlugins" / "polyglot")])
sys.modules.setdefault("polyglot", polyglotPackage)

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

	def test_defaultModelIsAPresetTranslationSpecialist(self) -> None:
		"""The default model ships in the preset list and is translation-specialised."""
		defaultModel = self._getSpecItem("modelNamePreset")["default"]
		self.assertEqual(defaultModel, OpenRouterTranslateEngine.DEFAULT_MODEL)
		self.assertIn(defaultModel, OpenRouterTranslateEngine.PRESET_MODELS)
		self.assertIn(defaultModel, OpenRouterTranslateEngine.TRANSLATION_ONLY_MODELS)

	def test_allTranslationSpecialistsArePresets(self) -> None:
		"""Every translation-specialised model is available in the model selection list."""
		self.assertFalse(
			OpenRouterTranslateEngine.TRANSLATION_ONLY_MODELS.difference(
				OpenRouterTranslateEngine.PRESET_MODELS,
			),
		)

	def test_unsupportedTranslationLanguageIsNotOffered(self) -> None:
		"""Languages unsupported by the default translation model are not offered."""
		self.assertNotIn("sv", self.engine.getSupportedLanguages())

	def test_defaultPromptModeSuitsTheDefaultModel(self) -> None:
		"""The default prompt template is one the default model can follow."""
		defaultPromptMode = self._getSpecItem("promptMode")["default"]
		self.assertIn(
			defaultPromptMode,
			self.engine._getPromptModeChoices(OpenRouterTranslateEngine.DEFAULT_MODEL),
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

	def test_storedStructuredPromptFallsBackToSimple(self) -> None:
		"""A stored structured-JSON selection is downgraded, not sent to a text-only model."""
		self.config["promptMode"] = "json_structured"
		params = self.engine._buildRequestParams("hello", "auto", "fr", self.config)
		payload = json.loads(params["data"].decode("utf-8"))
		self.assertEqual(payload["model"], OpenRouterTranslateEngine.DEFAULT_MODEL)
		self.assertEqual(payload["messages"][0]["content"], OpenRouterTranslateEngine.PROMPT_SIMPLE_SYSTEM)
		self.assertNotIn("JSON", payload["messages"][1]["content"])
		self.assertIn("hello", payload["messages"][1]["content"])

	def test_structuredPromptIsKeptForCapableModels(self) -> None:
		"""Models that support it still receive the structured-JSON prompt."""
		self.config["modelNamePreset"] = "inception/mercury-2"
		self.config["promptMode"] = "json_structured"
		params = self.engine._buildRequestParams("hello", "auto", "fr", self.config)
		payload = json.loads(params["data"].decode("utf-8"))
		self.assertEqual(payload["model"], "inception/mercury-2")
		self.assertEqual(
			payload["messages"][0]["content"],
			OpenRouterTranslateEngine.PROMPT_JSON_STRUCTURED_SYSTEM,
		)

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
		"""A custom model name is used verbatim and keeps every prompt template."""
		self.config["modelNamePreset"] = "custom"
		self.config["modelNameCustom"] = " my-org/my-model "
		params = self.engine._buildRequestParams("hello", "auto", "fr", self.config)
		payload = json.loads(params["data"].decode("utf-8"))
		self.assertEqual(payload["model"], "my-org/my-model")
		self.assertIn("json_structured", self.engine._getPromptModeChoices("my-org/my-model"))


if __name__ == "__main__":
	unittest.main()
