# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Catalog loading and language-pair metadata for ChromeAI model packages."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import addonHandler
import requests

from ..common import languages
from .settings import getString

addonHandler.initTranslation()

DEFAULT_CATALOG_URL = "https://dl.nvdacn.com/Polyglot/catalog.json"
_CATALOG_URL_ENV = "POLYGLOT_MODEL_CATALOG_URL"
_BASE_LANGUAGE = "en"


@dataclass(frozen=True)
class ArchiveRef:
	"""Download metadata for a runtime or model archive."""

	path: str = ""
	sha256: str = ""
	size: int = 0

	@classmethod
	def fromJson(cls, data: Any) -> "ArchiveRef | None":
		"""Create an archive reference from catalog JSON."""
		if not isinstance(data, dict):
			return None
		sizeValue = data.get("size", 0)
		try:
			size = int(sizeValue)
		except (TypeError, ValueError):
			size = 0
		return cls(
			path=getString(data, "path"),
			sha256=getString(data, "sha256").lower(),
			size=size,
		)


@dataclass(frozen=True)
class RuntimeEntry:
	"""TranslateKit runtime entry from the model catalog."""

	version: str = ""
	componentId: str = ""
	crxHash: str = ""
	libRelativeDir: str = ""
	binaryRelativePath: str = ""
	crxRelativePath: str = ""
	archive: ArchiveRef | None = None
	updateClientData: dict[str, Any] | None = None

	@classmethod
	def fromJson(cls, data: Any) -> "RuntimeEntry":
		"""Create a runtime entry from catalog JSON."""
		if not isinstance(data, dict):
			return cls()
		updateClientData = data.get("updateClientData")
		return cls(
			version=getString(data, "version"),
			componentId=getString(data, "componentId"),
			crxHash=getString(data, "crxHash"),
			libRelativeDir=getString(data, "libRelativeDir"),
			binaryRelativePath=getString(data, "binaryRelativePath"),
			crxRelativePath=getString(data, "crxRelativePath"),
			archive=ArchiveRef.fromJson(data.get("archive")),
			updateClientData=updateClientData if isinstance(updateClientData, dict) else None,
		)


@dataclass(frozen=True)
class ModelPackage:
	"""A ChromeAI language model package from the catalog."""

	key: str = ""
	sourceLanguage: str = ""
	targetLanguage: str = ""
	displayName: str = ""
	version: str = ""
	componentId: str = ""
	crxHash: str = ""
	modelRelativeDir: str = ""
	installRelativeDir: str = ""
	crxRelativePath: str = ""
	archive: ArchiveRef | None = None
	updateClientData: dict[str, Any] | None = None

	@classmethod
	def fromJson(cls, data: Any) -> "ModelPackage":
		"""Create a package entry from catalog JSON."""
		if not isinstance(data, dict):
			return cls()
		updateClientData = data.get("updateClientData")
		return cls(
			key=getString(data, "key"),
			sourceLanguage=getString(data, "sourceLanguage"),
			targetLanguage=getString(data, "targetLanguage"),
			displayName=getString(data, "displayName"),
			version=getString(data, "version"),
			componentId=getString(data, "componentId"),
			crxHash=getString(data, "crxHash"),
			modelRelativeDir=getString(data, "modelRelativeDir"),
			installRelativeDir=getString(data, "installRelativeDir"),
			crxRelativePath=getString(data, "crxRelativePath"),
			archive=ArchiveRef.fromJson(data.get("archive")),
			updateClientData=updateClientData if isinstance(updateClientData, dict) else None,
		)


@dataclass
class ModelCatalog:
	"""Model catalog with package lookup helpers."""

	baseUrl: str = ""
	generatedAt: str = ""
	runtime: RuntimeEntry = field(default_factory=RuntimeEntry)
	packages: list[ModelPackage] = field(default_factory=list)
	byKey: dict[str, ModelPackage] = field(default_factory=dict)

	@classmethod
	def loadRemote(cls, catalogUrl: str) -> "ModelCatalog":
		"""Load a catalog from an HTTP or HTTPS URL."""
		response = requests.get(catalogUrl, timeout=30)
		response.raise_for_status()
		catalog = cls.deserialize(response.text)
		if not catalog.baseUrl:
			catalog.baseUrl = urljoin(catalogUrl, ".").rstrip("/")
		return catalog

	@classmethod
	def loadBundled(cls) -> "ModelCatalog":
		"""Load the bundled fallback catalog."""
		path = Path(__file__).with_name("resources") / "catalog.json"
		if not path.is_file():
			raise RuntimeError(_("Bundled model catalog is missing."))
		return cls.deserialize(path.read_text(encoding="utf-8-sig"))

	@classmethod
	def deserialize(cls, text: str) -> "ModelCatalog":
		"""Deserialize and validate catalog JSON."""
		if not text.strip():
			raise RuntimeError(_("Catalog JSON is empty."))
		rawData = json.loads(text)
		if not isinstance(rawData, dict):
			raise RuntimeError(_("Catalog JSON is invalid."))
		try:
			schemaVersion = int(rawData.get("schemaVersion", 0))
		except (TypeError, ValueError):
			schemaVersion = 0
		if schemaVersion != 1:
			raise RuntimeError(
				_("Unsupported catalog schema version: {version}").format(version=schemaVersion),
			)
		rawPackages = rawData.get("packages", [])
		if not isinstance(rawPackages, list):
			rawPackages = []
		packages = [ModelPackage.fromJson(item) for item in rawPackages]
		byKey: dict[str, ModelPackage] = {}
		for package in packages:
			if not package.key:
				continue
			lowerKey = package.key.lower()
			if lowerKey in byKey:
				raise RuntimeError(_("Duplicate model package key in catalog: {key}").format(key=package.key))
			byKey[lowerKey] = package
		return cls(
			baseUrl=getString(rawData, "baseUrl"),
			generatedAt=getString(rawData, "generatedAt"),
			runtime=RuntimeEntry.fromJson(rawData.get("runtime")),
			packages=packages,
			byKey=byKey,
		)

	def archiveUrl(self, archive: ArchiveRef) -> str:
		"""Return the absolute download URL for an archive."""
		parsed = urlparse(archive.path)
		if parsed.scheme in ("http", "https"):
			return archive.path
		return f"{self.baseUrl.rstrip('/')}/{archive.path.lstrip('/')}"

	def findPackageForPair(self, sourceLanguage: str, targetLanguage: str) -> ModelPackage | None:
		"""Find the package that can satisfy a Chrome Translator language pair."""
		sourceLanguage = normalizeLanguageCode(sourceLanguage)
		targetLanguage = normalizeLanguageCode(targetLanguage)
		if not sourceLanguage or not targetLanguage or sourceLanguage == targetLanguage:
			return None
		for source, target in ((sourceLanguage, targetLanguage), (targetLanguage, sourceLanguage)):
			key = f"{source}_{target}".lower()
			if package := self.byKey.get(key):
				return package
			for package in self.packages:
				if (
					normalizeLanguageCode(package.sourceLanguage) == source
					and normalizeLanguageCode(package.targetLanguage) == target
				):
					return package
		return None

	def findPackagesForPair(self, sourceLanguage: str, targetLanguage: str) -> list[ModelPackage]:
		"""Find all packages required for a requested translation pair."""
		sourceLanguage = normalizeLanguageCode(sourceLanguage)
		targetLanguage = normalizeLanguageCode(targetLanguage)
		if not sourceLanguage or not targetLanguage or sourceLanguage == targetLanguage:
			return []
		if package := self.findPackageForPair(sourceLanguage, targetLanguage):
			return [package]
		if sourceLanguage == _BASE_LANGUAGE or targetLanguage == _BASE_LANGUAGE:
			return []
		required: list[ModelPackage] = []
		for pairSource, pairTarget in (
			(sourceLanguage, _BASE_LANGUAGE),
			(_BASE_LANGUAGE, targetLanguage),
		):
			package = self.findPackageForPair(pairSource, pairTarget)
			if package is not None and package.key not in {item.key for item in required}:
				required.append(package)
		return required


def normalizeCatalogUrl(inputUrl: str | None) -> str:
	"""Normalize a catalog URL and append catalog.json for directory URLs."""
	catalogUrl = (inputUrl or DEFAULT_CATALOG_URL).strip() or DEFAULT_CATALOG_URL
	parsed = urlparse(catalogUrl)
	if parsed.scheme not in ("http", "https") or not parsed.netloc:
		raise RuntimeError(_("Catalog URL must be an HTTP or HTTPS URL."))
	if not parsed.query and not parsed.path.lower().endswith(".json"):
		catalogUrl = catalogUrl.rstrip("/") + "/catalog.json"
	return catalogUrl


def resolveInitialCatalogUrl(savedCatalogUrl: str = "") -> str:
	"""Resolve the catalog URL from environment, saved settings, or default."""
	for value in (os.environ.get(_CATALOG_URL_ENV), savedCatalogUrl, DEFAULT_CATALOG_URL):
		try:
			return normalizeCatalogUrl(value)
		except RuntimeError:
			continue
	return DEFAULT_CATALOG_URL


def normalizeLanguageCode(code: str) -> str:
	"""Normalize common Chrome and BCP-47 language aliases to catalog codes."""
	normalized = (code or "").replace("_", "-")
	lowerCode = normalized.lower()
	if lowerCode in ("auto", "und", ""):
		return ""
	if lowerCode in ("he", "iw"):
		return "iw"
	if lowerCode.startswith("zh-hant") or lowerCode in ("zh-tw", "zh-hk", "zh-mo"):
		return "zh-Hant"
	if lowerCode.startswith("zh"):
		return "zh"
	return lowerCode.split("-", 1)[0]


def pairDisplayName(package: ModelPackage) -> str:
	"""Return a compact localized package display name without redundant English labels."""
	sourceLanguage = normalizeLanguageCode(package.sourceLanguage)
	targetLanguage = normalizeLanguageCode(package.targetLanguage)
	if not sourceLanguage or not targetLanguage:
		return package.displayName or package.key
	if sourceLanguage == _BASE_LANGUAGE and targetLanguage != _BASE_LANGUAGE:
		return languages.getLanguageName(targetLanguage)
	if targetLanguage == _BASE_LANGUAGE and sourceLanguage != _BASE_LANGUAGE:
		return languages.getLanguageName(sourceLanguage)
	return _("{source} / {target}").format(
		source=languages.getLanguageName(sourceLanguage),
		target=languages.getLanguageName(targetLanguage),
	)
