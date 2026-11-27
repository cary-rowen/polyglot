# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Local English-to-Chinese word lookup."""

import re
from dataclasses import dataclass
from pathlib import Path

import addonHandler
from logHandler import log

from .wordDictionaryData import (
	DictionaryAliases,
	canonicalizeWord as _canonicalizeWord,
	isLookupWord as _isLookupWord,
	loadDictionaryData,
	normalizeKey as _normalizeKey,
)


addonHandler.initTranslation()


_MAX_SPOKEN_WORD_MATCHES = 3
_DEFINITION_SEPARATOR_PATTERN = re.compile(r"[;,；，]")
_MIN_UNAMBIGUOUS_UPPER_LENGTH = 4
_ABBREVIATION_PATTERN = re.compile(r"(?<![A-Za-z])abbr\.", re.IGNORECASE)
_BUNDLED_DICTIONARY_PATH = Path(__file__).with_name("resources") / "dictionary.pickle"
_BUNDLED_ITALIAN_DICTIONARY_PATH = (
	Path(__file__).with_name("resources") / "dictionary.it.pickle"
)
_SENTENCE_PUNCTUATION = ",!?;:，。！？；：…"
_SURROUNDING_PAIRS = (
	('"', '"'),
	("'", "'"),
	("“", "”"),
	("‘", "’"),
	("(", ")"),
	("[", "]"),
	("{", "}"),
	("<", ">"),
	("（", "）"),
	("【", "】"),
	("《", "》"),
)

WordDictionaryMatch = tuple[str, str]


@dataclass(frozen=True)
class WordLookupResult:
	"""Describe one applicable word query and its zero or more dictionary matches."""

	word: str
	matches: tuple[WordDictionaryMatch, ...]
	isUppercaseFallback: bool = False


def _summarizeDefinition(definition: str) -> str:
	"""Return the first sense of a definition for a compact candidate list."""
	return _DEFINITION_SEPARATOR_PATTERN.split(definition, maxsplit=1)[0].strip()


def formatWordLookupResult(result: WordLookupResult) -> str:
	"""Format a local word lookup result for concise, localized speech."""
	if not result.matches:
		# Translators: Spoken when a valid-looking English word is absent from the bundled local
		# dictionary. {word} is the word reviewed by the user.
		return _("The local dictionary does not contain {word}.").format(word=result.word)

	if len(result.matches) == 1:
		entry, definition = result.matches[0]
		if not result.isUppercaseFallback:
			return definition
		return _(
			# Translators: Spoken when an all-capital word only matches a lowercase dictionary entry.
			# {word} is the reviewed text, {entry} is the lowercase headword, and {definition} is its
			# bundled definition.
			"When read as lowercase {entry}, {word} may mean: {definition}. "
			+ "In all caps, it may also be an abbreviation.",
		).format(
			entry=entry,
			word=result.word,
			definition=_summarizeDefinition(definition),
		)

	# Translators: One item in a spoken list of possible dictionary entries. {entry} is the
	# dictionary headword and {definition} is its bundled definition.
	candidateTemplate = _("{entry}: {definition}.")
	candidates = " ".join(
		candidateTemplate.format(entry=entry, definition=_summarizeDefinition(definition))
		for entry, definition in result.matches[:_MAX_SPOKEN_WORD_MATCHES]
	)
	# Translators: Introduces a spoken list of up to three possible dictionary entries.
	# {entries} contains the entries and their definitions.
	return _("Possibilities: {entries}").format(entries=candidates)


def _stripSurroundingPunctuation(text: str) -> str:
	"""Remove one sentence punctuation mark or one balanced wrapper pair."""
	word = text.strip()
	for opening, closing in _SURROUNDING_PAIRS:
		if word.startswith(opening) and word.endswith(closing) and len(word) > len(opening) + len(closing):
			return word[len(opening) : -len(closing)].strip()
	if word[-1] in _SENTENCE_PUNCTUATION:
		return word[:-1].rstrip()
	return word


class EnglishChineseDictionary:
	"""Lazily load and query the bundled English-to-Chinese dictionary."""

	_DICTIONARY_LABEL = "English-to-Chinese"

	def __init__(self, dictionaryPath: Path | None = None) -> None:
		"""Initialize a dictionary backed by ``dictionaryPath`` or the bundled data."""
		super().__init__()
		self._dictionaryPath = dictionaryPath or _BUNDLED_DICTIONARY_PATH
		self._entries: dict[str, str] | None = None
		self._casefoldEntryKeys: DictionaryAliases = {}
		self._normalizedEntryKeys: DictionaryAliases = {}
		self._inflectionEntryKeys: DictionaryAliases = {}

	def lookup(self, text: str) -> WordLookupResult | None:
		"""Return the result for one supported English word, or ``None`` when inapplicable."""
		strippedText = text.strip()
		if len(strippedText) < 2:
			return None
		rawWord = _stripSurroundingPunctuation(strippedText)
		if len(rawWord.removesuffix(".")) < 2:
			return None
		word = _canonicalizeWord(rawWord)
		if not _isLookupWord(word):
			return None
		if not self._loadEntries():
			return None
		displayWord = word.removesuffix(".")

		matches = self._lookupEntry(word)
		if matches is not None:
			if word != rawWord:
				self._logMatch("Unicode-normalized")
			elif rawWord != strippedText:
				self._logMatch("surrounding-punctuation")
			return WordLookupResult(displayWord, matches)

		matches = self._lookupCaseInsensitiveEntry(word)
		if matches is not None:
			isUppercaseFallback = self._requiresUppercaseCaution(displayWord, matches)
			if isUppercaseFallback:
				self._logUppercaseFallback()
			self._logMatch("case-insensitive")
			return WordLookupResult(displayWord, matches, isUppercaseFallback)

		wordWithoutPeriod = word.removesuffix(".")
		if wordWithoutPeriod != word:
			matches = self._lookupCaseInsensitiveEntry(wordWithoutPeriod)
			if matches is not None:
				isUppercaseFallback = self._requiresUppercaseCaution(wordWithoutPeriod, matches)
				if isUppercaseFallback:
					self._logUppercaseFallback()
				self._logMatch("trailing-period")
				return WordLookupResult(displayWord, matches, isUppercaseFallback)

		matches = self._lookupNormalizedEntry(word)
		if matches is not None:
			isUppercaseFallback = self._requiresUppercaseCaution(displayWord, matches)
			if isUppercaseFallback:
				self._logUppercaseFallback()
			self._logMatch("normalized")
			return WordLookupResult(displayWord, matches, isUppercaseFallback)

		matches = self._lookupInflection(wordWithoutPeriod.casefold())
		if matches is not None:
			isUppercaseFallback = self._requiresUppercaseCaution(displayWord, matches)
			if isUppercaseFallback:
				self._logUppercaseFallback()
			self._logMatch("inflection")
			return WordLookupResult(displayWord, matches, isUppercaseFallback)
		return WordLookupResult(displayWord, ())

	def _lookupInflection(self, word: str) -> tuple[WordDictionaryMatch, ...] | None:
		"""Return prevalidated inflection matches without deriving forms at runtime."""
		matches = self._lookupAlias(self._inflectionEntryKeys, word)
		if matches is not None and len(matches) > 1:
			log.debug("Local word dictionary found an ambiguous inflection match")
		return matches

	def _lookupCaseInsensitiveEntry(self, word: str) -> tuple[WordDictionaryMatch, ...] | None:
		"""Return exact or explicitly ambiguous case-insensitive matches."""
		foldedWord = word.casefold()
		matches = self._lookupEntry(foldedWord)
		if matches is None:
			matches = self._lookupAlias(self._casefoldEntryKeys, foldedWord)
		if matches is not None and len(matches) > 1:
			log.debug("Local word dictionary found an ambiguous case-insensitive match")
		return matches

	def _lookupNormalizedEntry(
		self,
		word: str,
	) -> tuple[WordDictionaryMatch, ...] | None:
		"""Return safe punctuation-insensitive matches, including ambiguities."""
		if "'" in word:
			return None
		normalizedKey = _normalizeKey(word)
		if not normalizedKey:
			return None
		matches = self._lookupAlias(self._normalizedEntryKeys, normalizedKey)
		if matches is not None and len(matches) > 1:
			log.debug("Local word dictionary found an ambiguous normalized match")
		return matches

	def _lookupEntry(self, word: str) -> tuple[WordDictionaryMatch, ...] | None:
		"""Return the key and definition for an exact dictionary entry."""
		definition = self._loadEntries().get(word)
		return None if definition is None else ((word, definition),)

	def _lookupAlias(
		self,
		aliases: DictionaryAliases,
		key: str,
	) -> tuple[WordDictionaryMatch, ...] | None:
		"""Resolve one prevalidated alias to its dictionary entries."""
		target = aliases.get(key)
		if target is None:
			return None
		targets = (target,) if isinstance(target, str) else target
		entries = self._loadEntries()
		return tuple((entryKey, entries[entryKey]) for entryKey in targets)

	def _loadEntries(self) -> dict[str, str]:
		"""Load the compiled dictionary once, falling back to empty tables on failure."""
		if self._entries is not None:
			return self._entries
		try:
			(
				self._entries,
				self._casefoldEntryKeys,
				self._normalizedEntryKeys,
				self._inflectionEntryKeys,
			) = loadDictionaryData(self._dictionaryPath)
			log.debug(
				"Loaded local %s dictionary: " % self._DICTIONARY_LABEL
				+ "%d entries, %d casefold aliases, %d normalized aliases, "
				+ "%d inflection aliases, %d ambiguous aliases",
				len(self._entries),
				len(self._casefoldEntryKeys),
				len(self._normalizedEntryKeys),
				len(self._inflectionEntryKeys),
				sum(isinstance(target, tuple) for target in self._casefoldEntryKeys.values())
				+ sum(isinstance(target, tuple) for target in self._normalizedEntryKeys.values())
				+ sum(isinstance(target, tuple) for target in self._inflectionEntryKeys.values()),
			)
		except (OSError, ValueError):
			log.error(
				"Unable to load the bundled %s dictionary." % self._DICTIONARY_LABEL,
				exc_info=True,
			)
			self._entries = {}
			self._casefoldEntryKeys = {}
			self._normalizedEntryKeys = {}
			self._inflectionEntryKeys = {}
		return self._entries

	@staticmethod
	def _requiresUppercaseCaution(
		word: str,
		matches: tuple[WordDictionaryMatch, ...],
	) -> bool:
		"""Return whether a short uppercase fallback may instead be an initialism."""
		if len(matches) != 1 or not word.isupper():
			return False
		alphanumericLength = sum(character.isalnum() for character in word)
		return (
			alphanumericLength < _MIN_UNAMBIGUOUS_UPPER_LENGTH
			and _ABBREVIATION_PATTERN.search(matches[0][1]) is None
		)

	@staticmethod
	def _logMatch(matchType: str) -> None:
		"""Log a non-exact dictionary decision without recording user text."""
		log.debug("Local word dictionary %s match", matchType)

	@staticmethod
	def _logUppercaseFallback() -> None:
		"""Log that a short uppercase word is being reported as an uncertain fallback."""
		log.debug("Local word dictionary found a possible short uppercase fallback")


class ItalianChineseDictionary(EnglishChineseDictionary):
	"""Lazily load and query the bundled Italian-to-Chinese dictionary.

	The Italian data lives in its own pickle so that an English lookup can never
	return an Italian entry, and vice versa.
	"""

	_DICTIONARY_LABEL = "Italian-to-Chinese"

	def __init__(self, dictionaryPath: Path | None = None) -> None:
		"""Initialize a dictionary backed by the Italian bundle."""
		super().__init__(dictionaryPath or _BUNDLED_ITALIAN_DICTIONARY_PATH)
