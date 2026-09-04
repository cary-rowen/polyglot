# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Runnable checks for DPAPI-protected engine configuration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import Mock, call, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]

nvdaConfig = sys.modules.setdefault("config", ModuleType("config"))
extensionPoints = sys.modules.setdefault("extensionPoints", ModuleType("extensionPoints"))
setattr(extensionPoints, "Action", Mock)
logHandler = sys.modules.setdefault("logHandler", ModuleType("logHandler"))
setattr(logHandler, "log", Mock())
nvdaState = sys.modules.setdefault("NVDAState", ModuleType("NVDAState"))
setattr(nvdaState, "shouldWriteToDisk", Mock(return_value=False))
polyglotPackage = ModuleType("polyglot")
setattr(polyglotPackage, "__path__", [str(PROJECT_ROOT / "addon" / "globalPlugins" / "polyglot")])
sys.modules.setdefault("polyglot", polyglotPackage)

from polyglot.common import config as configModule  # noqa: E402
from polyglot.common import secureStorage  # noqa: E402


class _Profile(dict[str, Any]):
	"""Represent the small ConfigObj surface needed by the migration check."""

	def __init__(self, name: str | None, values: dict[str, Any]) -> None:
		"""Initialize a profile name and its explicitly stored values."""
		super().__init__(values)
		self.name = name
		self.filename = f"{name or 'base'}.ini"


class SecureConfigTestCase(unittest.TestCase):
	"""Check secret format, failure behavior, and profile migration."""

	def test_secretFormatDistinguishesLegacyAndProtectedValues(self) -> None:
		"""Legacy plaintext remains readable while marked values use DPAPI."""
		with (
			patch.object(configModule, "protectString", return_value="encoded"),
			patch.object(configModule, "unprotectString", return_value="secret") as unprotect,
		):
			protected = configModule.protectSecret("secret")
			self.assertEqual(protected, "polyglot-dpapi:v1:encoded")
			self.assertEqual(configModule.unprotectSecret(protected), "secret")
			self.assertEqual(configModule.unprotectSecret("legacy-secret"), "legacy-secret")
			unprotect.assert_called_once_with("encoded")

	def test_foreignProtectedValueDoesNotBecomePlaintext(self) -> None:
		"""An undecryptable protected value becomes empty only in the runtime copy."""
		engineConfig = {"apiKey": "polyglot-dpapi:v1:foreign", "apiUrl": "https://example.com"}
		configSpec = [
			{"id": "apiKey", "type": "password"},
			{"id": "apiUrl", "type": "text"},
		]
		with patch.object(
			configModule,
			"unprotectString",
			side_effect=secureStorage.SecureStorageError("different computer"),
		):
			result = configModule.decryptConfigSecrets("example", engineConfig, configSpec)

		self.assertEqual(result["apiKey"], "")
		self.assertEqual(result["apiUrl"], "https://example.com")
		self.assertEqual(engineConfig["apiKey"], "polyglot-dpapi:v1:foreign")

	def test_migrationUpdatesOnlyExplicitPasswordFields(self) -> None:
		"""Every loaded profile keeps its own overrides and non-secret values."""
		baseProfile = _Profile(
			None,
			{
				"modernTranslate": {
					"engines": {
						"example": {"apiKey": "base-secret", "apiUrl": "https://base.example"},
					},
				},
			},
		)
		namedProfile = _Profile(
			"work",
			{
				"modernTranslate": {
					"engines": {
						"example": {"apiKey": "profile-secret"},
					},
				},
			},
		)
		unchangedProfile = _Profile(
			"unchanged",
			{
				"modernTranslate": {
					"engines": {
						"example": {"apiKey": "polyglot-dpapi:v1:already-protected"},
					},
				},
			},
		)
		conf = Mock()
		conf.profiles = [baseProfile, namedProfile, unchangedProfile]
		engine = Mock(id="example")
		engine.getConfigSpec.return_value = [
			{"id": "apiKey", "type": "password"},
			{"id": "apiUrl", "type": "text"},
		]

		with (
			patch.object(configModule, "shouldWriteToDisk", return_value=True),
			patch.object(configModule.nvdaConfig, "conf", conf, create=True),
			patch.object(
				configModule, "protectString", side_effect=lambda value, **_kwargs: f"dpapi-{value}"
			),
		):
			configModule.migrateStoredSecrets([engine])

		baseEngine = baseProfile["modernTranslate"]["engines"]["example"]
		namedEngine = namedProfile["modernTranslate"]["engines"]["example"]
		self.assertEqual(baseEngine["apiKey"], "polyglot-dpapi:v1:dpapi-base-secret")
		self.assertEqual(baseEngine["apiUrl"], "https://base.example")
		self.assertEqual(namedEngine["apiKey"], "polyglot-dpapi:v1:dpapi-profile-secret")
		self.assertEqual(
			conf._writeProfileToFile.call_args_list,
			[
				call(baseProfile.filename, baseProfile),
				call(namedProfile.filename, namedProfile),
			],
		)
		conf.save.assert_not_called()


@unittest.skipUnless(sys.platform == "win32", "Windows DPAPI is only available on Windows")
class SecureStorageRoundTripTestCase(unittest.TestCase):
	"""Check that the copied DPAPI wrapper round-trips text."""

	def test_protectStringRoundTrip(self) -> None:
		"""Protected UTF-8 text decrypts for the current Windows user."""
		secret = "api-token-\u2603-\u4f60\u597d"
		protected = secureStorage.protectString(secret)
		self.assertNotEqual(protected, secret)
		self.assertEqual(secureStorage.unprotectString(protected), secret)


if __name__ == "__main__":
	unittest.main()
