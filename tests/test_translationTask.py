# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for translation-task language handling."""

import builtins
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
nvdaState = ModuleType("NVDAState")
setattr(nvdaState, "shouldWriteToDisk", Mock(return_value=False))
sys.modules.setdefault("NVDAState", nvdaState)
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

from polyglot.app.task import TranslationTask  # noqa: E402
from polyglot.services import engineManager  # noqa: E402


class TranslationTaskTest(unittest.TestCase):
	"""Check auto-swap behavior for regional language targets."""

	def test_autoSwapMatchesLanguageFamily(self) -> None:
		"""A base detected code triggers swapping for a regional target code."""
		engine = Mock()
		engine.autoDetectCode = "auto"
		engine.getConfigSpec.return_value = []
		engine.areLanguagesEquivalent.return_value = True
		engine.translate.side_effect = [
			{"translation": "first", "langDetected": "en"},
			{"translation": "second", "langDetected": "en"},
		]
		completed = Mock()
		task = TranslationTask(
			"deeplWeb",
			"hello",
			"auto",
			"en-US",
			Mock(),
			completed,
			True,
			{"enableAutoSwap": True, "swapLanguage": "de"},
		)

		with patch.object(engineManager, "getEngineById", return_value=engine):
			task.run()

		self.assertEqual(engine.translate.call_count, 2)
		self.assertEqual(engine.translate.call_args_list[1].args[:3], ("hello", "en", "de"))
		self.assertEqual(completed.call_args.args[0]["translation"], "second")
		engine.areLanguagesEquivalent.assert_called_once_with("en", "en-US")

	def test_autoSwapHonorsEngineLanguageEquivalence(self) -> None:
		"""An engine can keep distinct regional languages from auto-swapping."""
		engine = Mock()
		engine.autoDetectCode = "auto"
		engine.getConfigSpec.return_value = []
		engine.areLanguagesEquivalent.return_value = False
		engine.translate.return_value = {"translation": "first", "langDetected": "zh"}
		completed = Mock()
		task = TranslationTask(
			"microsoft",
			"hello",
			"auto",
			"zh-Hant",
			Mock(),
			completed,
			True,
			{"enableAutoSwap": True, "swapLanguage": "de"},
		)

		with patch.object(engineManager, "getEngineById", return_value=engine):
			task.run()

		engine.translate.assert_called_once()
		engine.areLanguagesEquivalent.assert_called_once_with("zh", "zh-Hant")
		self.assertEqual(completed.call_args.args[0]["translation"], "first")


if __name__ == "__main__":
	unittest.main()
