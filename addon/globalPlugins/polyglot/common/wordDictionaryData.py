# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Build and validate the versioned local word dictionary data."""

import pickle
import re
import unicodedata
from pathlib import Path
from typing import NoReturn, cast


_DICTIONARY_FORMAT = "polyglot.wordDictionary"
# This is the first unreleased schema. Bump it after release when stored fields change.
_DICTIONARY_SCHEMA_VERSION = 1
_DICTIONARY_PICKLE_PROTOCOL = 4
_DICTIONARY_PICKLE_HEADER = bytes((0x80, _DICTIONARY_PICKLE_PROTOCOL))
_DICTIONARY_FIELDS = frozenset(
	(
		"format",
		"schemaVersion",
		"entries",
		"casefoldAliases",
		"normalizedAliases",
		"inflectionAliases",
	),
)
_MIN_WORD_LENGTH = 2
_MAX_WORD_LENGTH = 64
_MAX_ALIAS_TARGETS = 3
# Latin letters including diacritics (Italian: città, perché, è, più ...).
# Keeping this range here instead of ASCII-only is what lets every later
# Latin-script dictionary (French, Spanish, Portuguese, German, ...) reuse the
# same validation and lookup code without touching it again.
_LETTER = "A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF\u0100-\u017F"
_WORD_PATTERN = re.compile(
	rf"(?=[{_LETTER}0-9'-]*[{_LETTER}])[{_LETTER}0-9]+(?:[-'][{_LETTER}0-9]+)*(?:\.)?\Z",
)
_WORD_TRANSLATION = str.maketrans(
	{
		"\u00ad": "-",
		"\u02bc": "'",
		"\u2010": "-",
		"\u2011": "-",
		"\u2012": "-",
		"\u2013": "-",
		"\u2014": "-",
		"\u2018": "'",
		"\u2019": "'",
		"\u201b": "'",
		"\u2043": "-",
		"\u2212": "-",
		"\ufe58": "-",
		"\ufe63": "-",
	},
)

DictionaryEntries = dict[str, str]
DictionaryAliasTarget = str | tuple[str, ...]
DictionaryAliases = dict[str, DictionaryAliasTarget]
DictionaryTables = tuple[DictionaryEntries, DictionaryAliases, DictionaryAliases, DictionaryAliases]


class _PrimitiveOnlyUnpickler(pickle.Unpickler):
	"""Reject pickle operations which could construct global or persistent objects."""

	def find_class(self, _module: str, _name: str) -> NoReturn:  # pyright: ignore[reportImplicitOverride]
		"""Reject loading classes or functions from the pickle stream."""
		raise pickle.UnpicklingError("Global objects are not allowed in a word dictionary.")

	def persistent_load(self, _pid: object) -> NoReturn:  # pyright: ignore[reportImplicitOverride]
		"""Reject application-defined persistent objects from the pickle stream."""
		raise pickle.UnpicklingError("Persistent objects are not allowed in a word dictionary.")


def canonicalizeWord(text: str) -> str:
	"""Return a compatibility-normalized word using ASCII apostrophes and hyphens."""
	return unicodedata.normalize("NFKC", text.strip()).translate(_WORD_TRANSLATION)


def normalizeKey(text: str) -> str:
	"""Return the punctuation- and accent-insensitive key used for aliases.

	Diacritics are stripped so that ``citta`` resolves to ``città`` and
	``perche`` to ``perché`` while keeping the original keys intact.
	"""
	canonicalText = canonicalizeWord(text)
	decomposed = unicodedata.normalize("NFD", canonicalText)
	stripped = "".join(character for character in decomposed if not unicodedata.combining(character))
	return "".join(character for character in stripped if character.isalnum()).casefold()


def isLookupWord(word: str) -> bool:
	"""Return whether text is one complete supported word (English or Italian)."""
	wordWithoutPeriod = word.removesuffix(".")
	if not (_MIN_WORD_LENGTH <= len(wordWithoutPeriod) <= _MAX_WORD_LENGTH):
		return False
	# Fast path: plain ASCII alphanumerics (the overwhelming majority of keys).
	# Equivalent to the pattern below, but avoids a regex call per entry.
	if word.isascii() and word.isalnum() and not word.isdigit():
		return True
	return _WORD_PATTERN.fullmatch(word) is not None


def _normalizeDefinition(definition: str) -> str:
	"""Collapse insignificant whitespace in a dictionary definition."""
	return " ".join(definition.split())


def _objectWithoutDuplicateKeys(pairs: list[tuple[str, object]]) -> dict[str, object]:
	"""Return a JSON object while rejecting duplicate keys."""
	result: dict[str, object] = {}
	for key, value in pairs:
		if key in result:
			raise ValueError("Dictionary JSON contains duplicate keys.")
		result[key] = value
	return result


def _prepareEntries(rawEntries: object) -> DictionaryEntries:
	"""Validate and normalize source entries into deterministic key order."""
	if type(rawEntries) is not dict:
		raise ValueError("Dictionary source must contain one JSON object.")
	entries: DictionaryEntries = {}
	for key, definition in cast(dict[object, object], rawEntries).items():
		if type(key) is not str or not key or key != key.strip():
			raise ValueError("Dictionary entry keys must be non-empty trimmed strings.")
		if type(definition) is not str:
			raise ValueError("Dictionary definitions must be strings.")
		normalizedDefinition = _normalizeDefinition(definition)
		if not normalizedDefinition:
			raise ValueError("Dictionary definitions must not be empty.")
		entries[key] = normalizedDefinition
	if not entries:
		raise ValueError("Dictionary source must contain at least one entry.")
	return dict(sorted(entries.items()))


def _selectAliasTarget(targetsByDefinition: dict[str, str]) -> DictionaryAliasTarget:
	"""Return one target per distinct definition, preserving deterministic order."""
	targets = tuple(targetsByDefinition.values())[:_MAX_ALIAS_TARGETS]
	return targets[0] if len(targets) == 1 else targets


def _buildCasefoldAliases(entries: DictionaryEntries) -> DictionaryAliases:
	"""Index cased keys and retain candidates when their definitions conflict."""
	groupTargets: dict[str, dict[str, str]] = {}
	for key, definition in entries.items():
		foldedKey = key.casefold()
		if key == foldedKey or foldedKey in entries or not isLookupWord(foldedKey):
			continue
		_ = groupTargets.setdefault(foldedKey, {}).setdefault(definition, key)
	aliases = {
		foldedKey: _selectAliasTarget(targetsByDefinition)
		for foldedKey, targetsByDefinition in groupTargets.items()
	}
	return dict(sorted(aliases.items()))


def _buildNormalizedAliases(entries: DictionaryEntries) -> DictionaryAliases:
	"""Build a sparse punctuation-insensitive alias and conflict index."""
	groupTargets: dict[str, dict[str, str]] = {}
	lookupTargets: dict[str, str] = {}
	for key, definition in entries.items():
		normalizedKey = normalizeKey(key)
		if not normalizedKey:
			continue
		_ = groupTargets.setdefault(normalizedKey, {}).setdefault(definition, key)
		if isLookupWord(canonicalizeWord(key)) and key.casefold() != normalizedKey:
			_ = lookupTargets.setdefault(normalizedKey, key)

	aliases: DictionaryAliases = {}
	for normalizedKey, entryKey in lookupTargets.items():
		targetsByDefinition = {entries[entryKey]: entryKey}
		for definition, target in groupTargets[normalizedKey].items():
			_ = targetsByDefinition.setdefault(definition, target)
		if len(targetsByDefinition) > 1:
			aliases[normalizedKey] = _selectAliasTarget(targetsByDefinition)
		elif normalizedKey not in entries:
			aliases[normalizedKey] = entryKey
	return dict(sorted(aliases.items()))


def _validateAliasTarget(value: object, entries: DictionaryEntries) -> tuple[str, ...]:
	"""Return the entry keys in one valid resolved or ambiguous alias target."""
	if type(value) is str:
		if value not in entries:
			raise ValueError("Dictionary alias target is invalid.")
		return (value,)
	if type(value) is not tuple:
		raise ValueError("Dictionary alias target has an invalid type.")
	targets = cast(tuple[object, ...], value)
	if not 2 <= len(targets) <= _MAX_ALIAS_TARGETS:
		raise ValueError("Ambiguous dictionary aliases must contain two or three targets.")
	if any(type(target) is not str or target not in entries for target in targets) or len(
		set(targets),
	) != len(targets):
		raise ValueError("Dictionary alias target is invalid.")
	typedTargets = cast(tuple[str, ...], targets)
	if len({entries[target] for target in typedTargets}) != len(typedTargets):
		raise ValueError("Ambiguous dictionary alias targets must have distinct definitions.")
	return typedTargets


def _prepareInflectionAliases(
	rawAliases: object,
	entries: DictionaryEntries,
	casefoldAliases: DictionaryAliases,
	normalizedAliases: DictionaryAliases,
) -> DictionaryAliases:
	"""Validate inflections, merging punctuation-normalized collisions."""
	if type(rawAliases) is not dict:
		raise ValueError("Dictionary inflection source must contain one JSON object.")
	aliases: DictionaryAliases = {}
	canonicalEntryKeys = {key: key for key in entries}
	for alias, target in cast(dict[object, object], rawAliases).items():
		if (
			type(alias) is not str
			or not isLookupWord(alias)
			or alias.endswith(".")
			or alias != alias.casefold()
		):
			raise ValueError("Dictionary inflection alias key is invalid.")
		normalizedAlias = alias.replace("-", "").replace("'", "")
		if alias in entries or alias in casefoldAliases:
			raise ValueError("Dictionary inflection alias duplicates an earlier lookup match.")
		if type(target) is list:
			target = tuple(cast(list[object], target))
		targets = _validateAliasTarget(target, entries)
		canonicalTargets = tuple(canonicalEntryKeys[target] for target in targets)
		normalizedTarget = normalizedAliases.get(normalizedAlias)
		if normalizedTarget is not None:
			normalizedTargets = (normalizedTarget,) if isinstance(normalizedTarget, str) else normalizedTarget
			targetsByDefinition = {entries[target]: target for target in canonicalTargets}
			for existingTarget in normalizedTargets:
				targetsByDefinition[entries[existingTarget]] = existingTarget
			selectedTargets = tuple(targetsByDefinition.values())[:_MAX_ALIAS_TARGETS]
			if not any(normalizeKey(target) == normalizedAlias for target in selectedTargets):
				normalizedAnchor = next(
					target for target in normalizedTargets if normalizeKey(target) == normalizedAlias
				)
				selectedTargets = (*selectedTargets[:-1], normalizedAnchor)
			normalizedAliases[normalizedAlias] = (
				selectedTargets[0] if len(selectedTargets) == 1 else selectedTargets
			)
			continue
		aliases[alias] = canonicalTargets[0] if len(canonicalTargets) == 1 else canonicalTargets
	return dict(sorted(aliases.items()))


def _validateEntries(value: object) -> DictionaryEntries:
	"""Return a validated exact-entry table."""
	if type(value) is not dict or not value:
		raise ValueError("Dictionary entries must be a non-empty dictionary.")
	entries = cast(dict[object, object], value)
	for key, definition in entries.items():
		if type(key) is not str or not key:
			raise ValueError("Dictionary entry keys must be non-empty strings.")
		if type(definition) is not str or not definition:
			raise ValueError("Dictionary definitions must be non-empty strings.")
	return cast(DictionaryEntries, value)


def _validateCasefoldAliases(value: object, entries: DictionaryEntries) -> DictionaryAliases:
	"""Return a validated case-insensitive alias table."""
	if type(value) is not dict:
		raise ValueError("Dictionary casefold aliases must be a dictionary.")
	aliases = cast(dict[object, object], value)
	if len(aliases) > len(entries):
		raise ValueError("Dictionary casefold alias table is unexpectedly large.")
	for alias, target in aliases.items():
		if (
			type(alias) is not str
			or not alias
			or alias != alias.casefold()
			or alias in entries
			or not isLookupWord(alias)
		):
			raise ValueError("Dictionary casefold alias key is invalid.")
		targets = _validateAliasTarget(target, entries)
		if any(entryKey.casefold() != alias for entryKey in targets):
			raise ValueError("Dictionary casefold alias target is invalid.")
	return cast(DictionaryAliases, value)


def _validateNormalizedAliases(value: object, entries: DictionaryEntries) -> DictionaryAliases:
	"""Return validated punctuation aliases and merged inflection candidates."""
	if type(value) is not dict:
		raise ValueError("Dictionary normalized aliases must be a dictionary.")
	aliases = cast(dict[object, object], value)
	if len(aliases) > len(entries):
		raise ValueError("Dictionary normalized alias table is unexpectedly large.")
	for alias, target in aliases.items():
		if type(alias) is not str or not alias or normalizeKey(alias) != alias:
			raise ValueError("Dictionary normalized alias key is invalid.")
		targets = _validateAliasTarget(target, entries)
		if type(target) is str and (alias in entries or not isLookupWord(canonicalizeWord(target))):
			raise ValueError("Dictionary normalized alias target is invalid.")
		if not any(
			normalizeKey(entryKey) == alias
			and isLookupWord(canonicalizeWord(entryKey))
			and entryKey.casefold() != alias
			for entryKey in targets
		):
			raise ValueError("Dictionary normalized alias target is invalid.")
	return cast(DictionaryAliases, value)


def _validateInflectionAliases(
	value: object,
	entries: DictionaryEntries,
	casefoldAliases: DictionaryAliases,
	normalizedAliases: DictionaryAliases,
) -> DictionaryAliases:
	"""Return a validated precompiled inflection alias table."""
	if type(value) is not dict:
		raise ValueError("Dictionary inflection aliases must be a dictionary.")
	aliases = cast(dict[object, object], value)
	# Italian verb morphology yields far more inflected forms than headwords,
	# so the original 1:1 sanity bound is relaxed to 5:1.
	if len(aliases) > len(entries) * 5:
		raise ValueError("Dictionary inflection alias table is unexpectedly large.")
	for alias, target in aliases.items():
		if (
			type(alias) is not str
			or not isLookupWord(alias)
			or alias.endswith(".")
			or alias != alias.casefold()
			or alias in entries
			or alias in casefoldAliases
			or alias.replace("-", "").replace("'", "") in normalizedAliases
		):
			raise ValueError("Dictionary inflection alias key is invalid.")
		_ = _validateAliasTarget(target, entries)
	return cast(DictionaryAliases, value)


def _validateDictionaryData(value: object) -> DictionaryTables:
	"""Validate the complete schema and return its four lookup tables."""
	if type(value) is not dict:
		raise ValueError("Word dictionary data must be a dictionary.")
	data = cast(dict[object, object], value)
	if frozenset(data) != _DICTIONARY_FIELDS:
		raise ValueError("Word dictionary schema fields are invalid.")
	if type(data["format"]) is not str or data["format"] != _DICTIONARY_FORMAT:
		raise ValueError("Word dictionary format is unsupported.")
	schemaVersion = data["schemaVersion"]
	if type(schemaVersion) is not int or schemaVersion != _DICTIONARY_SCHEMA_VERSION:
		raise ValueError("Word dictionary schema version is unsupported.")
	entries = _validateEntries(data["entries"])
	casefoldAliases = _validateCasefoldAliases(data["casefoldAliases"], entries)
	normalizedAliases = _validateNormalizedAliases(data["normalizedAliases"], entries)
	inflectionAliases = _validateInflectionAliases(
		data["inflectionAliases"],
		entries,
		casefoldAliases,
		normalizedAliases,
	)
	return entries, casefoldAliases, normalizedAliases, inflectionAliases


def createDictionaryData(
	rawEntries: object,
	rawInflectionAliases: object | None = None,
) -> dict[str, object]:
	"""Create validated schema data and precomputed indexes from source entries."""
	entries = _prepareEntries(rawEntries)
	casefoldAliases = _buildCasefoldAliases(entries)
	normalizedAliases = _buildNormalizedAliases(entries)
	inflectionAliases = _prepareInflectionAliases(
		rawInflectionAliases if rawInflectionAliases is not None else {},
		entries,
		casefoldAliases,
		normalizedAliases,
	)
	data: dict[str, object] = {
		"format": _DICTIONARY_FORMAT,
		"schemaVersion": _DICTIONARY_SCHEMA_VERSION,
		"entries": entries,
		"casefoldAliases": casefoldAliases,
		"normalizedAliases": normalizedAliases,
		"inflectionAliases": inflectionAliases,
	}
	_ = _validateDictionaryData(data)
	return data


def compileDictionary(
	sourcePath: Path,
	targetPath: Path,
	inflectionsPath: Path | None = None,
) -> None:
	"""Compile source JSON into a deterministic protocol 4 pickle."""
	import json
	import tempfile

	temporaryPath: Path | None = None
	try:
		with sourcePath.open("r", encoding="utf-8") as sourceFile:
			rawEntries = json.load(sourceFile, object_pairs_hook=_objectWithoutDuplicateKeys)
		if inflectionsPath is None:
			rawInflectionAliases: object = {}
		else:
			with inflectionsPath.open("r", encoding="utf-8") as inflectionsFile:
				rawInflectionAliases = json.load(
					inflectionsFile,
					object_pairs_hook=_objectWithoutDuplicateKeys,
				)
		data = createDictionaryData(rawEntries, rawInflectionAliases)
		targetPath.parent.mkdir(parents=True, exist_ok=True)
		with tempfile.NamedTemporaryFile(
			"wb",
			dir=targetPath.parent,
			prefix=f".{targetPath.name}.",
			suffix=".tmp",
			delete=False,
		) as targetFile:
			temporaryPath = Path(targetFile.name)
			pickle.dump(
				data,
				targetFile,
				protocol=_DICTIONARY_PICKLE_PROTOCOL,
				fix_imports=False,
			)
		_ = loadDictionaryData(temporaryPath)
		_ = temporaryPath.replace(targetPath)
		temporaryPath = None
	finally:
		if temporaryPath is not None:
			temporaryPath.unlink(missing_ok=True)


def loadDictionaryData(dictionaryPath: Path) -> DictionaryTables:
	"""Load and validate lookup tables from a compiled word dictionary."""
	try:
		with dictionaryPath.open("rb") as dictionaryFile:
			if dictionaryFile.read(len(_DICTIONARY_PICKLE_HEADER)) != _DICTIONARY_PICKLE_HEADER:
				raise ValueError("Word dictionary must use pickle protocol 4.")
			_ = dictionaryFile.seek(0)
			data = _PrimitiveOnlyUnpickler(dictionaryFile).load()
			if dictionaryFile.read(1):
				raise ValueError("Word dictionary contains trailing data.")
		return _validateDictionaryData(data)
	except (
		AttributeError,
		EOFError,
		ImportError,
		IndexError,
		OverflowError,
		pickle.PickleError,
		RecursionError,
		TypeError,
		UnicodeError,
		ValueError,
	) as error:
		raise ValueError("Compiled word dictionary is invalid.") from error
