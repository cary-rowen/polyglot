# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for NVDA-language-based default translation languages."""

import unittest
from typing import Any
from unittest.mock import Mock, patch

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from polyglot.common import config as configModule  # noqa: E402
from polyglot.common import languages  # noqa: E402
from polyglot.services.engines.baidu import BaiduTranslateEngine  # noqa: E402
from polyglot.services.engines.deepl import DeepLEngine  # noqa: E402
from polyglot.services.engines.deeplWeb import DeepLWebTranslateEngine  # noqa: E402
from polyglot.services.engines.google import GoogleTranslateEngine  # noqa: E402
from polyglot.services.engines.microsoft import MicrosoftTranslateEngine  # noqa: E402
from polyglot.services.engines.vivo import VivoTranslateEngine  # noqa: E402


class DefaultLanguageResolutionTest(unittest.TestCase):
	"""Check NVDA interface language matching and source/target collision handling."""

	def test_resolveTargetLanguageMatchesLocalesAndAliases(self) -> None:
		"""NVDA locales resolve to exact codes, aliases, base families, or fallback."""
		cases = (
			("es", ("auto", "en", "es"), "zh", ("auto",), "es"),
			("es", ("auto", "EN", "ES"), "ZH", ("auto",), "ES"),
			("es", ("auto", "zh", "spa"), "zh", ("auto",), "spa"),
			("es_CO", ("auto", "es", "es-419"), "zh-Hans", ("auto",), "es-419"),
			("zh_CN", ("", "zh-Hans", "zh-Hant", "en"), "zh-Hans", ("",), "zh-Hans"),
			("zh_TW", ("auto", "zh", "cht", "en"), "zh", ("auto",), "cht"),
			("zh_HK", ("auto", "zh-CN", "zh-TW", "en"), "zh-CN", ("auto",), "zh-TW"),
			("zh_Hans_CN", ("auto", "zh-Hans", "zh-Hant"), "en", ("auto",), "zh-Hans"),
			("pt_BR", ("auto", "pt", "pt-BR", "pt-PT"), "zh-Hans", ("auto",), "pt-BR"),
			("nb_NO", ("auto", "en", "no"), "zh", ("auto",), "no"),
			("he", ("en", "iw"), "zh", (), "iw"),
			("en", ("auto", "en-US", "en-GB"), "zh-Hans", ("auto",), "en-US"),
			("xx", ("auto", "en", "zh"), "zh", ("auto",), "zh"),
			("", ("", "en", "zh"), "zh", ("",), "zh"),
			("auto", ("auto", "en", "zh"), "zh", ("auto",), "zh"),
		)
		for nvdaLang, supported, fallback, exclude, expected in cases:
			with self.subTest(nvdaLang=nvdaLang, supported=supported):
				self.assertEqual(
					languages.resolveTargetLanguage(
						supported,
						fallback=fallback,
						nvdaLanguage=nvdaLang,
						excludeCodes=exclude,
					),
					expected,
				)

	def test_enginesDefaultTargetFollowsNvdaLanguage(self) -> None:
		"""Engines map NVDA's active language to their own supported code or fallback."""
		engineClasses = {
			"google": GoogleTranslateEngine,
			"microsoft": MicrosoftTranslateEngine,
			"deepl": DeepLEngine,
			"deeplWeb": DeepLWebTranslateEngine,
			"baidu": BaiduTranslateEngine,
			"vivo": VivoTranslateEngine,
		}
		expectations = (
			(
				"es",
				{
					"google": "es",
					"microsoft": "es",
					"deepl": "ES",
					"deeplWeb": "es",
					"baidu": "spa",
					"vivo": "zh-CHS",
				},
			),
			(
				"zh_TW",
				{
					"google": "zh-TW",
					"microsoft": "zh-Hant",
					"deepl": "ZH",
					"deeplWeb": "zh-Hant",
					"baidu": "cht",
					"vivo": "zh-CHS",
				},
			),
		)
		for nvdaLang, expectedByEngine in expectations:
			with patch("languageHandler.getLanguage", return_value=nvdaLang):
				for engineId, expected in expectedByEngine.items():
					with self.subTest(nvdaLang=nvdaLang, engine=engineId):
						self.assertEqual(engineClasses[engineId]().defaultTargetLanguage, expected)

	def test_nonAutoDetectEngineAvoidsSourceTargetCollision(self) -> None:
		"""Engines without auto-detect pick a distinct source language when target matches fallback source."""
		for nvdaLang, expectedSource, expectedTarget in (
			("en", "zh-CHS", "en"),
			("ja", "en", "ja"),
			("es", "en", "zh-CHS"),
		):
			with self.subTest(nvdaLang=nvdaLang), patch("languageHandler.getLanguage", return_value=nvdaLang):
				engine = VivoTranslateEngine()
				self.assertEqual(engine.defaultTargetLanguage, expectedTarget)
				self.assertEqual(engine.defaultSourceLanguage, expectedSource)


class _Profile(dict[str, Any]):
	"""Represent the ConfigObj surface used by the language-default migration."""

	filename = "nvda.ini"


class PinLegacyLanguageDefaultsTest(unittest.TestCase):
	"""Check that upgrades keep the previous fixed defaults and fresh installs do not."""

	def _run(self, *profiles: _Profile) -> Mock:
		"""Run the migration against the given profiles and return the mocked config."""
		conf = Mock(profiles=list(profiles))
		with (
			patch.object(configModule, "shouldWriteToDisk", return_value=True),
			patch.object(configModule.nvdaConfig, "conf", conf, create=True),
		):
			configModule.pinLegacyLanguageDefaults([GoogleTranslateEngine(), VivoTranslateEngine()])
		return conf

	def test_upgradePinsMissingLanguagesOnly(self) -> None:
		"""Unsaved languages are pinned to the old fallbacks; saved values are kept."""
		base = _Profile({"modernTranslate": {"engines": {"vivo": {"langTo": "ja"}}}})
		conf = self._run(base)

		engines = base["modernTranslate"]["engines"]
		self.assertEqual(engines["google"], {"langTo": "zh-CN"})
		self.assertEqual(engines["vivo"], {"langTo": "ja", "langFrom": "en"})
		self.assertTrue(base["modernTranslate"]["languageDefaultsMigrated"])
		conf._writeProfileToFile.assert_called_once_with(base.filename, base)

	def test_freshInstallOnlyRecordsMarker(self) -> None:
		"""A configuration without Polyglot settings keeps the NVDA-language defaults."""
		base = _Profile()
		self._run(base)
		self.assertEqual(base, {"modernTranslate": {"languageDefaultsMigrated": True}})

	def test_migratedConfigurationIsLeftAlone(self) -> None:
		"""The migration runs once, so later settings are never overwritten."""
		base = _Profile({"modernTranslate": {"languageDefaultsMigrated": "True"}})
		conf = self._run(base)
		self.assertEqual(base, {"modernTranslate": {"languageDefaultsMigrated": "True"}})
		conf._writeProfileToFile.assert_not_called()


if __name__ == "__main__":
	unittest.main()
