# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Small runnable checks for local English word lookup."""

import json
import pickle
import tempfile
import unittest
from pathlib import Path
from typing import cast

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

from logHandler import log  # noqa: E402
from polyglot.common.wordDictionary import EnglishChineseDictionary, WordLookupResult  # noqa: E402
from polyglot.common.wordDictionaryData import compileDictionary, createDictionaryData  # noqa: E402


class EnglishChineseDictionaryTest(unittest.TestCase):
	"""Check exact matching, aliases, boundaries, and compiled dictionary validation."""

	def setUp(self) -> None:
		"""Create a minimal deterministic dictionary covering each lookup path."""
		log.reset_mock()
		self._temporaryDirectory = tempfile.TemporaryDirectory()
		self.addCleanup(self._temporaryDirectory.cleanup)
		self._dictionarySourcePath = Path(self._temporaryDirectory.name) / "dictionary.json"
		self._inflectionsSourcePath = Path(self._temporaryDirectory.name) / "inflections.json"
		self._dictionaryPath = Path(self._temporaryDirectory.name) / "dictionary.pickle"
		entries = {
			"Bluetooth": "n. Bluetooth",
			"Dr.": "abbr. doctor",
			"EU": "abbr. European Union",
			"add-on": "n. add-on",
			"aide-de-camp": "n. aide-de-camp",
			"analyse": "v. analyse",
			"analysis": "n. analysis",
			"api": "abbr. application programming interface",
			"back up": "v. back up",
			"back-up": "n. back-up",
			"built in": "adj. built in",
			"built-in": "adj. built in",
			"co2": "abbr. carbon dioxide",
			"dog": "n. dog",
			"go": "v. go",
			"hello": "  greeting\nvalue  ",
			"hope": "n. hope; v. hope",
			"ky.": "abbr. Kentucky",
			"let": "v. let",
			"let's": "abbr. let us",
			"resign": "v. resign",
			"run": "v. run",
			"running": "n. running",
			"us": "pron. us",
			"ｗｉｄｅ": "adj. wide",
		}
		inflections: dict[str, str | list[str]] = {
			"analyses": ["analyse", "analysis"],
			"hoped": "hope",
			"hoping": "hope",
			"lets": "let",
		}
		self._dictionarySourcePath.write_text(json.dumps(entries), encoding="utf-8")
		self._inflectionsSourcePath.write_text(json.dumps(inflections), encoding="utf-8")
		compileDictionary(
			self._dictionarySourcePath,
			self._dictionaryPath,
			self._inflectionsSourcePath,
		)
		self.dictionary = EnglishChineseDictionary(self._dictionaryPath)

	def _lookupDefinition(self, text: str) -> str | None:
		"""Return one unambiguous definition from the structured lookup result."""
		result = self.dictionary.lookup(text)
		if result is None or len(result.matches) != 1:
			return None
		return result.matches[0][1]

	def _requireResult(self, text: str) -> WordLookupResult:
		"""Return an applicable lookup result, failing the current check otherwise."""
		result = self.dictionary.lookup(text)
		self.assertIsNotNone(result)
		return cast(WordLookupResult, result)

	def _loadCompiledData(self) -> dict[str, object]:
		"""Return the trusted test fixture payload for controlled corruption checks."""
		with self._dictionaryPath.open("rb") as dictionaryFile:
			return cast(dict[str, object], pickle.load(dictionaryFile))

	def _writeCompiledData(self, data: object) -> None:
		"""Write controlled protocol 4 data to the temporary dictionary path."""
		with self._dictionaryPath.open("wb") as dictionaryFile:
			pickle.dump(data, dictionaryFile, protocol=4, fix_imports=False)

	def test_lookupPriorityAndPrecompiledInflections(self) -> None:
		"""Exact entries win; precompiled inflections support trailing periods, ambiguity, and merges."""
		self.assertEqual("n. running", self._lookupDefinition("running"))
		self.assertEqual("n. hope; v. hope", self._lookupDefinition("hoped"))
		self.assertEqual("n. hope; v. hope", self._lookupDefinition("hoped."))
		self.assertEqual(
			("analyse", "analysis"),
			tuple(entry for entry, _definition in self._requireResult("analyses").matches),
		)
		self.assertEqual(
			("let", "let's"),
			tuple(entry for entry, _definition in self._requireResult("lets").matches),
		)
		for unlisted in ("goed", "analysises"):
			with self.subTest(unlisted=unlisted):
				self.assertEqual((), self._requireResult(unlisted).matches)

	def test_mergedAliasesKeepSchemaBoundaries(self) -> None:
		"""Deduplicate meanings, cap ambiguity, and reject inflections duplicating higher-priority keys."""
		data = createDictionaryData(
			{
				"base": "third inflection",
				"fo-rms": "first normalized",
				"for-ms": "second normalized",
				"form": "shared",
				"form's": "shared",
				"shape": "second inflection",
			},
			{"forms": ["form", "shape", "base"]},
		)
		normalizedAliases = cast(dict[str, object], data["normalizedAliases"])
		inflectionAliases = cast(dict[str, object], data["inflectionAliases"])
		self.assertEqual(("form's", "shape", "base"), normalizedAliases["forms"])
		self.assertNotIn("forms", inflectionAliases)

		for label, entries in (
			("exact", {"walk": "verb", "walks": "noun"}),
			("casefold", {"walk": "verb", "Walks": "name"}),
		):
			with (
				self.subTest(label=label),
				self.assertRaisesRegex(ValueError, "duplicates an earlier lookup match"),
			):
				createDictionaryData(entries, {"walks": "walk"})

	def test_normalizedAliasesUseWholeDictionaryForConflicts(self) -> None:
		"""Resolve safe punctuation-insensitive aliases while retaining conflicts and rejecting splits."""
		self.assertEqual("n. aide-de-camp", self._lookupDefinition("aidedecamp"))
		self.assertEqual("n. aide-de-camp", self._lookupDefinition("aide‑de‑camp"))
		self.assertEqual("adj. built in", self._lookupDefinition("builtin"))
		self.assertEqual("abbr. Kentucky", self._lookupDefinition("ky"))
		self.assertEqual("greeting value", self._lookupDefinition("hello."))
		self.assertEqual("n. add-on", self._lookupDefinition("add-on."))
		backup = self._requireResult("backup")
		self.assertEqual(("back-up", "back up"), tuple(entry for entry, _definition in backup.matches))
		self.assertIsNone(self._lookupDefinition("re-sign"))

	def test_wordBoundariesCaseAndUnicodeAreHandledConservatively(self) -> None:
		"""Accept complete tokens and flag short uppercase fallbacks while rejecting invalid boundaries."""
		for token in (" Hello ", "ｈｅｌｌｏ", "(hello)", "“hello”", "hello!"):
			with self.subTest(token=token):
				self.assertEqual("greeting value", self._lookupDefinition(token))
		self.assertEqual("adj. wide", self._lookupDefinition("wide"))
		self.assertEqual("n. Bluetooth", self._lookupDefinition("BLUETOOTH"))
		self.assertEqual("abbr. application programming interface", self._lookupDefinition("API"))
		self.assertEqual("abbr. carbon dioxide", self._lookupDefinition("CO2"))
		self.assertEqual("abbr. European Union", self._lookupDefinition("EU"))
		self.assertEqual("abbr. doctor", self._lookupDefinition("dr."))

		for word in ("US", "DOG"):
			with self.subTest(word=word):
				result = self._requireResult(word)
				self.assertTrue(result.isUppercaseFallback)
				self.assertEqual(1, len(result.matches))

		self.assertEqual((), self._requireResult("it's").matches)
		for inapplicable in ("(hello),", "hello,,", "a", "hello world", "这是 hello", "№", "ﬁ"):
			with self.subTest(inapplicable=inapplicable):
				self.assertIsNone(self.dictionary.lookup(inapplicable))

	def test_debugLoggingIsLightweight(self) -> None:
		"""Log loading and non-exact decisions without logging definitions or ordinary misses."""
		self.assertEqual("greeting value", self._lookupDefinition("hello"))
		self.assertIn("Loaded local English-to-Chinese dictionary", repr(log.debug.call_args_list))
		self.assertNotIn("greeting value", repr(log.debug.call_args_list))

		log.reset_mock()
		self.assertEqual((), self._requireResult("zzunknown").matches)
		log.debug.assert_not_called()

		self.assertEqual("n. hope; v. hope", self._lookupDefinition("hoping"))
		log.debug.assert_called_once()
		self.assertNotIn("n. hope", repr(log.debug.call_args_list))

	def test_compilerOutputIsDeterministicAndAtomic(self) -> None:
		"""Generate identical protocol 4 output and preserve valid data on invalid JSON."""
		secondPath = self._dictionaryPath.with_name("second.pickle")
		compileDictionary(self._dictionarySourcePath, secondPath, self._inflectionsSourcePath)
		validData = self._dictionaryPath.read_bytes()
		self.assertEqual(b"\x80\x04", validData[:2])
		self.assertEqual(validData, secondPath.read_bytes())

		self._dictionarySourcePath.write_text('{"word": "one", "word": "two"}', encoding="utf-8")
		with self.assertRaises(ValueError):
			compileDictionary(
				self._dictionarySourcePath,
				self._dictionaryPath,
				self._inflectionsSourcePath,
			)
		self.assertEqual(validData, self._dictionaryPath.read_bytes())

	def test_corruptCompiledDataFailsClosedOnce(self) -> None:
		"""Cache empty tables after corrupt data so repeated lookups do not reload or log."""
		self._dictionaryPath.write_bytes(b"\x80\x04truncated")
		dictionary = EnglishChineseDictionary(self._dictionaryPath)
		self.assertIsNone(dictionary.lookup("hello"))
		self.assertIsNone(dictionary.lookup("hope"))
		log.error.assert_called_once()

	def test_invalidSchemaAndPickleGlobalsFailClosed(self) -> None:
		"""Reject pickle globals and unsupported, incomplete, or inconsistent schema data."""
		validData = self._loadCompiledData()
		invalidPayloads: list[tuple[str, object]] = [
			("pickle global", Path("unexpected")),
			("future version", {**validData, "schemaVersion": 2}),
			("missing field", {k: v for k, v in validData.items() if k != "normalizedAliases"}),
			("wrong table type", {**validData, "casefoldAliases": []}),
			("missing alias target", {**validData, "normalizedAliases": {"aidedecamp": "missing"}}),
			("missing inflection target", {**validData, "inflectionAliases": {"walked": "missing"}}),
		]
		for label, payload in invalidPayloads:
			with self.subTest(label=label):
				log.reset_mock()
				self._writeCompiledData(payload)
				dictionary = EnglishChineseDictionary(self._dictionaryPath)
				self.assertIsNone(dictionary.lookup("hello"))
				log.error.assert_called_once()


if __name__ == "__main__":
	unittest.main()
