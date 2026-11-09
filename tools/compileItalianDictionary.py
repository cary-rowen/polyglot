# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Compile the Italian-Chinese dictionary and conjugation tables.

The Italian data is kept as two tracked source files:

* ``dictionary.it.json`` maps every Italian headword to a definition made of a
  part-of-speech abbreviation and one or more Chinese glosses.
* ``conjugation.it.tsv`` lists every conjugated form with its verb, tense and
  person, one row per form.

Two build products are generated from them:

* ``dictionary.it.pickle`` — headwords plus one entry per conjugated form; a
  form entry carries its grammatical reading, e.g. ``ho`` -> 我有（avere 直陈式现在时 io）.
* ``conjugation.it.pickle`` — the full tense/person tables used by the
  ``NVDA+Control+I`` viewer, plus a form-to-infinitive map.

Both products use the shared ``polyglot.wordDictionary`` schema.
"""

from __future__ import annotations

import importlib.util
import json
import pickle
import re
from pathlib import Path

_PRONOUNS = {
	"io": "我",
	"tu": "你",
	"lui": "他",
	"lei": "她",
	"noi": "我们",
	"voi": "你们",
	"loro": "他们",
	"": "",
}
_LEADING_POS = re.compile(r"^[A-Za-z.\s]+")
_GLOSS_SEPARATOR = re.compile(r"[；;，,、]")
_MAX_READINGS_PER_FORM = 3
_MAX_GLOSS_LENGTH = 12
_MAX_MERGED_LENGTH = 600


def _shortGloss(definition: str) -> str:
	"""Return the first Chinese gloss of a headword definition."""
	body = _LEADING_POS.sub("", definition or "")
	first = _GLOSS_SEPARATOR.split(body)[0].strip()
	return first[:_MAX_GLOSS_LENGTH]


def _dedupeGlosses(definition: str) -> str:
	"""Drop repeated ``；``-separated segments while keeping their order."""
	parts = [part.strip() for part in (definition or "").split("；")]
	seen: set[str] = set()
	out: list[str] = []
	for index, part in enumerate(parts):
		if not part:
			continue
		key = _LEADING_POS.sub("", part).strip() if index == 0 else part
		if not key or key in seen:
			continue
		seen.add(key)
		out.append(part)
	return "；".join(out) or definition


def loadConjugationRows(tsvPath: Path) -> dict[str, dict]:
	"""Return ``{lemma: {"pos": str, "tenses": [{"tense", "forms"}]}}``."""
	verbs: dict[str, dict] = {}
	with tsvPath.open(encoding="utf-8") as sourceFile:
		for line in sourceFile:
			line = line.rstrip("\n")
			if not line or line.startswith("#"):
				continue
			fields = line.split("\t")
			if len(fields) != 5:
				continue
			lemma, pos, tense, person, forms = fields
			entry = verbs.setdefault(lemma, {"pos": pos, "tenses": []})
			entry["pos"] = entry["pos"] or pos
			tenseEntry = next((item for item in entry["tenses"] if item["tense"] == tense), None)
			if tenseEntry is None:
				tenseEntry = {"tense": tense, "forms": []}
				entry["tenses"].append(tenseEntry)
			tenseEntry["forms"].append({"person": person, "form": forms})
	return verbs


def _serializeRows(verbs: dict[str, dict]) -> dict[str, dict]:
	"""Return the JSON-friendly table stored in ``conjugation.it.pickle``."""
	table = {}
	for lemma, entry in verbs.items():
		table[lemma] = {
			"pos": entry.get("pos", ""),
			"tenses": [
				{
					"tense": tense["tense"],
					"forms": [
						{"person": row.get("person", ""), "form": row.get("form", "")}
						for row in tense["forms"]
					],
				}
				for tense in entry.get("tenses", [])
			],
		}
	return table


def _formReadings(verbs: dict[str, dict], headwords: dict[str, str]) -> dict[str, list[str]]:
	"""Return ``{form: [reading, ...]}`` for every conjugated form."""
	readings: dict[str, list[str]] = {}
	for lemma, entry in verbs.items():
		gloss = _shortGloss(headwords.get(lemma, ""))
		if not gloss:
			continue
		for tense in entry.get("tenses", []):
			tenseName = tense["tense"]
			for row in tense["forms"]:
				forms = row.get("form", "")
				if not forms:
					continue
				person = row.get("person", "")
				pronoun = _PRONOUNS.get(person, "")
				for form in (part.strip() for part in forms.split(" / ")):
					if not form or " " in form:
						continue
					if person and pronoun:
						reading = f"{pronoun}{gloss}（{lemma} {tenseName} {person}）"
					else:
						reading = f"{gloss}（{lemma} {tenseName}）"
					bucket = readings.setdefault(form.casefold(), [])
					if reading not in bucket and len(bucket) < _MAX_READINGS_PER_FORM:
						bucket.append(reading)
	return readings


def _formMap(verbs: dict[str, dict]) -> dict[str, list[str]]:
	"""Return ``{form: [lemma, ...]}`` for the conjugation viewer."""
	forms: dict[str, list[str]] = {}
	for lemma, entry in verbs.items():
		for tense in entry.get("tenses", []):
			for row in tense["forms"]:
				for form in (part.strip() for part in row.get("form", "").split(" / ")):
					if not form or " " in form:
						continue
					bucket = forms.setdefault(form.casefold(), [])
					if lemma not in bucket and len(bucket) < 3:
						bucket.append(lemma)
	return forms


def compileItalianDictionary(
	dictionarySourcePath: Path,
	conjugationSourcePath: Path,
	dictionaryTargetPath: Path,
	conjugationTargetPath: Path,
	wordDictionaryDataPath: Path,
) -> None:
	"""Compile both Italian data files from their tracked sources."""
	moduleSpec = importlib.util.spec_from_file_location(
		"_polyglotWordDictionaryData", wordDictionaryDataPath,
	)
	if moduleSpec is None or moduleSpec.loader is None:
		raise RuntimeError("Unable to load the word dictionary schema module.")
	dictionaryData = importlib.util.module_from_spec(moduleSpec)
	moduleSpec.loader.exec_module(dictionaryData)

	with dictionarySourcePath.open(encoding="utf-8") as sourceFile:
		headwords: dict[str, str] = json.load(sourceFile)
	headwords = {key: _dedupeGlosses(value) for key, value in headwords.items()}

	verbs = loadConjugationRows(conjugationSourcePath)

	# Headwords first, then one entry per conjugated form.
	entries = dict(headwords)
	casefoldIndex = {key.casefold(): key for key in entries}
	for form, items in _formReadings(verbs, headwords).items():
		if not dictionaryData.isLookupWord(form):
			continue
		reading = "；".join(items)
		existingKey = casefoldIndex.get(form)
		if existingKey is not None:
			merged = _dedupeGlosses(f"{entries[existingKey]}；{reading}")
			entries[existingKey] = merged[:_MAX_MERGED_LENGTH]
		else:
			entries[form] = reading
			casefoldIndex[form] = form

	dictionaryPayload = dictionaryData.createDictionaryData(entries, {})
	dictionaryTargetPath.parent.mkdir(parents=True, exist_ok=True)
	with dictionaryTargetPath.open("wb") as targetFile:
		pickle.dump(dictionaryPayload, targetFile, protocol=4, fix_imports=False)

	conjugationPayload = {
		"verbs": _serializeRows(verbs),
		"forms": _formMap(verbs),
	}
	conjugationTargetPath.parent.mkdir(parents=True, exist_ok=True)
	with conjugationTargetPath.open("wb") as targetFile:
		pickle.dump(conjugationPayload, targetFile, protocol=4, fix_imports=False)


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="Compile the Italian dictionary data.")
	parser.add_argument("dictionary_source", type=Path)
	parser.add_argument("conjugation_source", type=Path)
	parser.add_argument("dictionary_target", type=Path)
	parser.add_argument("conjugation_target", type=Path)
	parser.add_argument("word_dictionary_data", type=Path)
	arguments = parser.parse_args()
	compileItalianDictionary(
		arguments.dictionary_source,
		arguments.conjugation_source,
		arguments.dictionary_target,
		arguments.conjugation_target,
		arguments.word_dictionary_data,
	)
