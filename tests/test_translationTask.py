# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for translation-task language handling."""

import unittest
from unittest.mock import Mock, patch

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from polyglot.app.task import TranslationTask  # noqa: E402
from polyglot.services import engineManager  # noqa: E402


class TranslationTaskTest(unittest.TestCase):
	"""Check auto-swap behavior for regional language targets."""

	def test_autoSwapFollowsEngineLanguageEquivalence(self) -> None:
		"""Auto-swap runs a second translation if and only if the engine treats languages as equivalent."""
		cases = (
			("deeplWeb", "en", "en-US", True, "second"),
			("microsoft", "zh", "zh-Hant", False, "first"),
		)
		for engineId, detected, target, equivalent, expectedTranslation in cases:
			with self.subTest(engine=engineId, equivalent=equivalent):
				engine = Mock(autoDetectCode="auto")
				engine.getConfigSpec.return_value = []
				engine.areLanguagesEquivalent.return_value = equivalent
				engine.translate.side_effect = [
					{"translation": "first", "langDetected": detected},
					{"translation": "second", "langDetected": detected},
				]
				completed = Mock()
				task = TranslationTask(
					engineId,
					"hello",
					"auto",
					target,
					Mock(),
					completed,
					True,
					{"enableAutoSwap": True, "swapLanguage": "de"},
				)

				with patch.object(engineManager, "getEngineById", return_value=engine):
					task.run()

				engine.areLanguagesEquivalent.assert_called_once_with(detected, target)
				self.assertEqual(engine.translate.call_count, 2 if equivalent else 1)
				if equivalent:
					self.assertEqual(engine.translate.call_args_list[1].args[:3], ("hello", detected, "de"))
				self.assertEqual(completed.call_args.args[0]["translation"], expectedTranslation)


if __name__ == "__main__":
	unittest.main()
