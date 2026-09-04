# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

from collections.abc import Iterable, MutableMapping
from typing import Any

import config as nvdaConfig
import extensionPoints
from logHandler import log
from NVDAState import shouldWriteToDisk

from .secureStorage import SecureStorageError, protectString, unprotectString

_CONFIG_SECTION = "modernTranslate"
_PROTECTED_SECRET_PREFIX = "polyglot-dpapi:v1:"
_PROTECTED_SECRET_NAMESPACE = "polyglot-dpapi:"
_PROTECTED_SECRET_DESCRIPTION = "Polyglot protected secret"
post_localDictionarySettingsChanged = extensionPoints.Action()


def getConfigSectionName() -> str:
	"""Return the NVDA configuration section used by Polyglot."""
	return _CONFIG_SECTION


def getConfig() -> dict[str, Any]:
	"""Return the add-on configuration section."""
	return nvdaConfig.conf[_CONFIG_SECTION]


def protectSecret(secret: str) -> str:
	"""Protect a secret for storage in the NVDA configuration."""
	if not secret:
		return ""
	return _PROTECTED_SECRET_PREFIX + protectString(secret, description=_PROTECTED_SECRET_DESCRIPTION)


def unprotectSecret(storedSecret: str) -> str:
	"""Return plaintext from a protected or legacy plaintext configuration value."""
	if not storedSecret or not storedSecret.startswith(_PROTECTED_SECRET_NAMESPACE):
		return storedSecret
	if not storedSecret.startswith(_PROTECTED_SECRET_PREFIX):
		raise SecureStorageError("The protected secret uses an unsupported format.")
	return unprotectString(storedSecret.removeprefix(_PROTECTED_SECRET_PREFIX))


def _getSecretFieldNames(configSpec: Iterable[dict[str, Any]]) -> tuple[str, ...]:
	"""Return the configuration fields declared as password controls."""
	return tuple(item["id"] for item in configSpec if item.get("type") == "password")


def decryptConfigSecrets(
	engineId: str,
	engineConfig: dict[str, Any],
	configSpec: Iterable[dict[str, Any]],
) -> dict[str, Any]:
	"""Decrypt an engine configuration copy before it is passed to the engine."""
	decryptedConfig = engineConfig.copy()
	for fieldName in _getSecretFieldNames(configSpec):
		storedSecret = str(decryptedConfig.get(fieldName, "") or "")
		try:
			decryptedConfig[fieldName] = unprotectSecret(storedSecret)
		except SecureStorageError:
			log.warning(
				"Stored secret '%s.%s' could not be unprotected on this computer.",
				engineId,
				fieldName,
				exc_info=True,
			)
			decryptedConfig[fieldName] = ""
	return decryptedConfig


def _getStoredEngineSections(profile: MutableMapping[str, Any]) -> MutableMapping[str, Any] | None:
	"""Return engine sections explicitly stored in one NVDA profile."""
	addOnSection = profile.get(_CONFIG_SECTION)
	if not isinstance(addOnSection, MutableMapping):
		return None
	enginesSection = addOnSection.get("engines")
	return enginesSection if isinstance(enginesSection, MutableMapping) else None


def _migrateProfileSecrets(
	profile: MutableMapping[str, Any],
	secretFieldsByEngine: dict[str, tuple[str, ...]],
) -> bool:
	"""Protect plaintext secrets explicitly stored in one NVDA profile."""
	engineSections = _getStoredEngineSections(profile)
	if engineSections is None:
		return False
	wasChanged = False
	profileName = getattr(profile, "name", None) or "<base>"
	for engineId, fieldNames in secretFieldsByEngine.items():
		engineSection = engineSections.get(engineId)
		if not isinstance(engineSection, MutableMapping):
			continue
		for fieldName in fieldNames:
			storedSecret = engineSection.get(fieldName)
			if (
				not isinstance(storedSecret, str)
				or not storedSecret
				or storedSecret.startswith(_PROTECTED_SECRET_NAMESPACE)
			):
				continue
			try:
				protectedSecret = protectSecret(storedSecret)
			except SecureStorageError:
				log.error(
					"Could not migrate secret '%s.%s' in configuration profile '%s'.",
					engineId,
					fieldName,
					profileName,
					exc_info=True,
				)
				continue
			engineSection[fieldName] = protectedSecret
			wasChanged = True
	return wasChanged


def migrateStoredSecrets(engines: Iterable[Any]) -> None:
	"""Protect legacy plaintext secrets in every currently loaded NVDA profile."""
	if not shouldWriteToDisk():
		return
	secretFieldsByEngine = {engine.id: _getSecretFieldNames(engine.getConfigSpec()) for engine in engines}
	for profile in nvdaConfig.conf.profiles:
		if not _migrateProfileSecrets(profile, secretFieldsByEngine):
			continue
		try:
			# NVDA has no public single-profile writer; conf.save() would persist unrelated dirty settings.
			nvdaConfig.conf._writeProfileToFile(profile.filename, profile)
		except Exception:
			log.error(
				"Could not save migrated Polyglot secrets in configuration profile '%s'.",
				profile.name or "<base>",
				exc_info=True,
			)
