# Copyright (C) 2025-2026 cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Small runnable checks for local English word lookup."""

import json
import pickle
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import Mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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

from polyglot.common.wordDictionary import EnglishChineseDictionary, WordLookupResult  # noqa: E402
from polyglot.common.wordDictionaryData import compileDictionary, createDictionaryData  # noqa: E402


class EnglishChineseDictionaryTest(unittest.TestCase):
	"""Check exact matching, aliases, boundaries, and English inflections."""

	def setUp(self) -> None:
		"""Create a small deterministic dictionary for each check."""
		logHandler.log.reset_mock()
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
			"addon": "n. solid addon",
			"aide-de-camp": "n. aide-de-camp",
			"analyse": "v. analyse",
			"analysis": "n. analysis",
			"api": "abbr. application programming interface",
			"age": "n. age; v. age",
			"bare": "adj. bare; v. bare",
			"be": "v. be",
			"beautiful": "adj. beautiful",
			"benefit": "n. benefit; v. benefit",
			"big": "adj. big",
			"box": "n. box",
			"built in": "adj. built in",
			"built-in": "adj. built in",
			"carrie": "n. Carrie",
			"carry": "v. carry",
			"chairman": "n. chairman",
			"clu": "abbr. Chartered Life Underwriter",
			"clue": "n. clue; v. clue",
			"co2": "abbr. carbon dioxide",
			"cool": "adj. cool; v. cool",
			"criterion": "n. criterion",
			"cut": "v. cut",
			"cute": "adj. cute",
			"dog": "n. dog",
			"email": "n. email; v. email",
			"fail": "v. fail",
			"focus": "n. focus; v. focus",
			"fizz": "n. fizz; v. fizz",
			"go": "v. go",
			"good": "adj. good",
			"hello": "  greeting\nvalue  ",
			"hope": "n. hope; v. hope",
			"hot": "adj. hot",
			"huge": "adj. huge",
			"human": "n. human",
			"index": "n. index",
			"ky.": "abbr. Kentucky",
			"larva": "n. larva",
			"let": "v. let",
			"let's": "abbr. let us",
			"lie": "n. lie; v. lie",
			"little": "adj. little",
			"long": "adj. long; v. long",
			"longe": "v. longe",
			"make": "v. make",
			"mate": "n. mate; v. mate",
			"mango": "n. mango",
			"nice": "adj. nice",
			"not": "adv. not",
			"note": "n. note; v. note",
			"oas": "untagged oas",
			"oasis": "n. oasis",
			"occur": "v. occur",
			"one": "n. one",
			"one's": "adj. one's",
			"pale": "adj. pale",
			"panic": "n. panic; v. panic",
			"photo": "n. photo",
			"price": "n. price; v. price",
			"prix": "n. prix",
			"quiz": "n. quiz; v. quiz",
			"queue": "n. queue; v. queue",
			"run": "v. run",
			"running": "n. running",
			"second": "adj. second; v. second",
			"seconde": "n. seconde",
			"resign": "v. resign",
			"shop": "n. shop; v. shop",
			"shoppe": "n. shoppe",
			"sing": "v. sing",
			"singe": "v. singe",
			"sit": "v. sit",
			"site": "n. site; v. site",
			"ski": "n. ski; v. ski",
			"sky": "n. sky; v. sky",
			"stop": "n. stop; v. stop",
			"stomach": "n. stomach; v. stomach",
			"study": "n. study; v. study",
			"sue": "v. sue",
			"suffix": "n. suffix",
			"suffice": "v. suffice",
			"synopsis": "n. synopsis",
			"take": "v. take",
			"therapist": "n. therapist",
			"tooth": "n. tooth",
			"travel": "n. travel; v. travel",
			"up": "adv. up; v. up",
			"us": "pron. us",
			"wife": "n. wife",
			"wive": "v. wive",
			"\uff57\uff49\uff44\uff45": "adj. wide",
			"back up": "v. back up",
			"back-up": "n. back-up",
			"hop": "v. hop",
			"memorandum": "n. memorandum",
			"stimulus": "n. stimulus",
		}
		self._dictionarySourcePath.write_text(json.dumps(entries), encoding="utf-8")
		inflections: dict[str, str | list[str]] = {
			"ageing": "age",
			"aging": "age",
			"analyses": ["analyse", "analysis"],
			"baring": "bare",
			"benefited": "benefit",
			"benefitted": "benefit",
			"bigger": "big",
			"boxes": "box",
			"carries": ["carrie", "carry"],
			"chairmen": "chairman",
			"clued": "clue",
			"criteria": "criterion",
			"cuter": "cute",
			"cutest": "cute",
			"fizzed": "fizz",
			"fizzes": "fizz",
			"fizzing": "fizz",
			"focused": "focus",
			"focussed": "focus",
			"goes": "go",
			"hoped": "hope",
			"hoping": "hope",
			"huger": "huge",
			"hugest": "huge",
			"indices": "index",
			"larvae": "larva",
			"lets": "let",
			"longed": ["long", "longe"],
			"lying": "lie",
			"making": "make",
			"mated": "mate",
			"memoranda": "memorandum",
			"nicest": "nice",
			"noting": "note",
			"oases": "oasis",
			"occurred": "occur",
			"occurring": "occur",
			"ones": "one",
			"paler": "pale",
			"panicked": "panic",
			"panicking": "panic",
			"prices": "price",
			"queuing": "queue",
			"queueing": "queue",
			"quizzes": "quiz",
			"seconded": "second",
			"shopped": "shop",
			"singeing": "singe",
			"singing": "sing",
			"siting": "site",
			"skied": ["ski", "sky"],
			"stimuli": "stimulus",
			"stomachs": "stomach",
			"stopped": "stop",
			"studies": "study",
			"sueing": "sue",
			"suing": "sue",
			"suffices": "suffice",
			"synopses": "synopsis",
			"taken": "take",
			"teeth": "tooth",
			"travelled": "travel",
			"traveled": "travel",
			"upped": "up",
			"upping": "up",
			"went": "go",
			"wives": ["wife", "wive"],
		}
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

	def testExactEntriesTakePriority(self) -> None:
		"""Keep a definition for an inflected entry when it already exists."""
		self.assertEqual("n. running", self._lookupDefinition("running"))

	def testCompiledInflectionsResolveToDictionaryEntries(self) -> None:
		"""Resolve representative regular and irregular forms from compiled aliases."""
		self.assertEqual("n. study; v. study", self._lookupDefinition("studies"))
		self.assertEqual("n. stop; v. stop", self._lookupDefinition("stopped"))
		self.assertEqual("n. lie; v. lie", self._lookupDefinition("lying"))
		self.assertEqual("v. make", self._lookupDefinition("making"))
		self.assertEqual("n. box", self._lookupDefinition("boxes"))
		self.assertEqual("adj. big", self._lookupDefinition("bigger"))
		self.assertEqual("n. chairman", self._lookupDefinition("chairmen"))
		self.assertEqual("n. panic; v. panic", self._lookupDefinition("panicked"))
		self.assertEqual("n. panic; v. panic", self._lookupDefinition("panicking"))
		self.assertEqual("n. quiz; v. quiz", self._lookupDefinition("quizzes"))
		self.assertEqual("v. go", self._lookupDefinition("went"))
		self.assertEqual("v. take", self._lookupDefinition("taken"))
		self.assertEqual("n. tooth", self._lookupDefinition("teeth"))

	def testInflectionAliasesPreservePunctuationAndChosenTargets(self) -> None:
		"""Use prevalidated targets after handling a trailing sentence period."""
		self.assertEqual("n. hope; v. hope", self._lookupDefinition("hoped"))
		self.assertEqual("n. hope; v. hope", self._lookupDefinition("hoped."))
		self.assertEqual("n. hope; v. hope", self._lookupDefinition("hoping"))
		self.assertEqual("n. site; v. site", self._lookupDefinition("siting"))
		self.assertEqual("adj. second; v. second", self._lookupDefinition("seconded"))
		self.assertEqual("n. shop; v. shop", self._lookupDefinition("shopped"))
		self.assertEqual("n. mate; v. mate", self._lookupDefinition("mated"))
		self.assertEqual("n. clue; v. clue", self._lookupDefinition("clued"))
		self.assertEqual("adj. bare; v. bare", self._lookupDefinition("baring"))
		self.assertEqual("n. note; v. note", self._lookupDefinition("noting"))

	def testSupportedSpellingVariantsArePrecompiled(self) -> None:
		"""Support selected degree, regional, and optional spelling variants."""
		for word in ("paler", "cuter", "huger"):
			self.assertIsNotNone(self._lookupDefinition(word))
		for word in ("nicest", "cutest", "hugest"):
			self.assertIsNotNone(self._lookupDefinition(word))
		for word in ("traveled", "travelled", "focused", "focussed"):
			self.assertIsNotNone(self._lookupDefinition(word))
		for word in ("benefited", "benefitted", "occurred", "occurring", "upped", "upping"):
			self.assertIsNotNone(self._lookupDefinition(word))
		for word in ("aging", "ageing", "suing", "sueing", "queuing", "queueing"):
			self.assertIsNotNone(self._lookupDefinition(word))
		self.assertEqual("v. sing", self._lookupDefinition("singing"))
		self.assertEqual("v. singe", self._lookupDefinition("singeing"))
		self.assertEqual("n. stomach; v. stomach", self._lookupDefinition("stomachs"))
		for word in ("fizzes", "fizzed", "fizzing"):
			self.assertEqual("n. fizz; v. fizz", self._lookupDefinition(word))
		for misspelling in ("biger", "hotest", "makeing", "walkked"):
			self.assertIsNone(self._lookupDefinition(misspelling))

	def testClassicalPluralAliasesAreSupported(self) -> None:
		"""Resolve classical plurals explicitly supplied by the dictionary data."""
		self.assertEqual("n. oasis", self._lookupDefinition("oases"))
		self.assertEqual("n. synopsis", self._lookupDefinition("synopses"))
		self.assertEqual("n. index", self._lookupDefinition("indices"))
		self.assertEqual("n. stimulus", self._lookupDefinition("stimuli"))
		self.assertEqual("n. memorandum", self._lookupDefinition("memoranda"))
		self.assertEqual("n. larva", self._lookupDefinition("larvae"))
		self.assertEqual("n. criterion", self._lookupDefinition("criteria"))
		self.assertEqual("n. price; v. price", self._lookupDefinition("prices"))
		self.assertEqual("v. suffice", self._lookupDefinition("suffices"))

	def testAmbiguousInflectionsRetainTheirCandidates(self) -> None:
		"""Return every distinct dictionary meaning for an ambiguous inflection."""
		expectedCandidates = {
			"analyses": ("analyse", "analysis"),
			"carries": ("carrie", "carry"),
			"longed": ("long", "longe"),
			"skied": ("ski", "sky"),
			"wives": ("wife", "wive"),
		}
		for word, expectedEntries in expectedCandidates.items():
			with self.subTest(word=word):
				result = self._requireResult(word)
				self.assertEqual(expectedEntries, tuple(entry for entry, _definition in result.matches))
		self.assertEqual((), self._requireResult("analysises").matches)

	def testInflectionsMergeWithNormalizedAliases(self) -> None:
		"""Retain inflections which omit punctuation used by another entry."""
		expectedCandidates = {
			"lets": ("let", "let's"),
			"ones": ("one", "one's"),
		}
		for word, expectedEntries in expectedCandidates.items():
			with self.subTest(word=word):
				result = self._requireResult(word)
				self.assertEqual(expectedEntries, tuple(entry for entry, _definition in result.matches))

	def testMergedAliasesKeepSchemaBoundaries(self) -> None:
		"""Deduplicate meanings, cap ambiguity, and preserve higher-priority matches."""
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
				self.assertRaisesRegex(
					ValueError,
					"duplicates an earlier lookup match",
				),
			):
				_ = createDictionaryData(entries, {"walks": "walk"})

	def testUnlistedRegularizationsAreRejected(self) -> None:
		"""Reject mechanically plausible forms and misspellings absent from source data."""
		self.assertEqual("v. go", self._lookupDefinition("goes"))
		for invalidForm in (
			"Bing",
			"beautifuls",
			"beautifuled",
			"beautifulling",
			"coolled",
			"emailled",
			"failled",
			"goed",
			"gooder",
			"goodest",
			"humen",
			"littles",
			"maked",
			"photoes",
			"runned",
		):
			with self.subTest(invalidForm=invalidForm):
				self.assertIsNone(self._lookupDefinition(invalidForm))

	def testNormalizedAliasesUseTheWholeDictionaryForConflictDetection(self) -> None:
		"""Resolve safe aliases while retaining conflicting phrase definitions."""
		self.assertEqual("n. aide-de-camp", self._lookupDefinition("aidedecamp"))
		self.assertEqual("n. aide-de-camp", self._lookupDefinition("aide\u2011de\u2011camp"))
		self.assertEqual("adj. built in", self._lookupDefinition("builtin"))
		self.assertEqual("abbr. Kentucky", self._lookupDefinition("ky"))
		self.assertEqual("greeting value", self._lookupDefinition("hello."))
		backup = self._requireResult("backup")
		self.assertEqual(("back-up", "back up"), tuple(entry for entry, _definition in backup.matches))
		self.assertEqual("n. add-on", self._lookupDefinition("add-on."))
		for unrelatedHyphenation in ("re-sign", "man-go", "the-rapist"):
			self.assertIsNone(self._lookupDefinition(unrelatedHyphenation))

	def testWordBoundariesCaseAndUnicodeAreHandledConservatively(self) -> None:
		"""Accept supported complete tokens while preserving ambiguous boundaries."""
		self.assertEqual("greeting value", self._lookupDefinition(" Hello "))
		self.assertEqual("greeting value", self._lookupDefinition("\uff48\uff45\uff4c\uff4c\uff4f"))
		self.assertEqual("greeting value", self._lookupDefinition("(hello)"))
		self.assertEqual("greeting value", self._lookupDefinition("“hello”"))
		self.assertEqual("greeting value", self._lookupDefinition("hello!"))
		self.assertIsNone(self.dictionary.lookup("(hello),"))
		self.assertIsNone(self.dictionary.lookup("hello,,"))
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
		self.assertIsNone(self.dictionary.lookup("a"))
		self.assertIsNone(self.dictionary.lookup("hello world"))
		self.assertEqual((), self._requireResult("it's").matches)
		self.assertIsNone(self.dictionary.lookup("\u8fd9\u662f hello"))
		for compatibilityCharacter in ("№", "№.", "(㎏)", "“Ⅳ”", "ﬁ", "ﬂ."):
			self.assertIsNone(self.dictionary.lookup(compatibilityCharacter))

	def testDebugLoggingIsLightweight(self) -> None:
		"""Log loading and non-exact decisions without logging definitions or ordinary misses."""
		self.assertEqual("greeting value", self._lookupDefinition("hello"))
		self.assertIn("Loaded local English-to-Chinese dictionary", repr(logHandler.log.debug.call_args_list))
		self.assertNotIn("greeting value", repr(logHandler.log.debug.call_args_list))

		logHandler.log.reset_mock()
		self.assertEqual((), self._requireResult("zzunknown").matches)
		logHandler.log.debug.assert_not_called()

		self.assertEqual("n. hope; v. hope", self._lookupDefinition("hoping"))
		logHandler.log.debug.assert_called_once()
		self.assertNotIn("n. hope", repr(logHandler.log.debug.call_args_list))

	def testCompilerOutputIsDeterministic(self) -> None:
		"""Generate identical protocol 4 data from the same JSON source."""
		secondPath = self._dictionaryPath.with_name("second.pickle")
		compileDictionary(self._dictionarySourcePath, secondPath, self._inflectionsSourcePath)
		self.assertEqual(b"\x80\x04", self._dictionaryPath.read_bytes()[:2])
		self.assertEqual(self._dictionaryPath.read_bytes(), secondPath.read_bytes())

	def testCompilerPreservesValidTargetWhenSourceIsInvalid(self) -> None:
		"""Reject duplicate JSON keys without replacing the last valid compiled data."""
		validData = self._dictionaryPath.read_bytes()
		self._dictionarySourcePath.write_text('{"word": "one", "word": "two"}', encoding="utf-8")
		with self.assertRaises(ValueError):
			compileDictionary(
				self._dictionarySourcePath,
				self._dictionaryPath,
				self._inflectionsSourcePath,
			)
		self.assertEqual(validData, self._dictionaryPath.read_bytes())

	def testCorruptCompiledDataFailsClosedOnce(self) -> None:
		"""Cache empty tables after corrupt data so repeated lookups do not reload or log."""
		self._dictionaryPath.write_bytes(b"\x80\x04truncated")
		dictionary = EnglishChineseDictionary(self._dictionaryPath)
		self.assertIsNone(dictionary.lookup("hello"))
		self.assertIsNone(dictionary.lookup("hope"))
		logHandler.log.error.assert_called_once()

	def testPickleGlobalObjectsAreRejected(self) -> None:
		"""Reject pickle global objects before attempting schema validation."""
		self._writeCompiledData(Path("unexpected"))
		dictionary = EnglishChineseDictionary(self._dictionaryPath)
		self.assertIsNone(dictionary.lookup("hello"))
		logHandler.log.error.assert_called_once()

	def testInvalidSchemaFailsClosed(self) -> None:
		"""Reject unsupported, incomplete, and internally inconsistent schema data."""
		validData = self._loadCompiledData()
		invalidData: list[tuple[str, dict[str, object]]] = []

		futureVersion = validData.copy()
		futureVersion["schemaVersion"] = 2
		invalidData.append(("future version", futureVersion))

		missingField = validData.copy()
		del missingField["normalizedAliases"]
		invalidData.append(("missing field", missingField))

		wrongTableType = validData.copy()
		wrongTableType["casefoldAliases"] = []
		invalidData.append(("wrong table type", wrongTableType))

		missingTarget = validData.copy()
		missingTarget["normalizedAliases"] = {"aidedecamp": "missing"}
		invalidData.append(("missing alias target", missingTarget))

		missingInflectionTarget = validData.copy()
		missingInflectionTarget["inflectionAliases"] = {"walked": "missing"}
		invalidData.append(("missing inflection target", missingInflectionTarget))

		for label, data in invalidData:
			with self.subTest(label=label):
				logHandler.log.reset_mock()
				self._writeCompiledData(data)
				dictionary = EnglishChineseDictionary(self._dictionaryPath)
				self.assertIsNone(dictionary.lookup("hello"))
				logHandler.log.error.assert_called_once()


if __name__ == "__main__":
	unittest.main()
