# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Lazy Italian verb conjugation tables used by the conjugation viewer."""

import pickle
from pathlib import Path

import addonHandler
from logHandler import log


addonHandler.initTranslation()


_BUNDLED_CONJUGATION_PATH = Path(__file__).with_name("resources") / "conjugation.it.pickle"


class ItalianConjugationBook:
	"""Load the bundled Italian conjugation tables on first use."""

	def __init__(self, conjugationPath: Path | None = None) -> None:
		"""Initialize the book without touching the disk."""
		super().__init__()
		self._path = conjugationPath or _BUNDLED_CONJUGATION_PATH
		self._verbs: dict[str, dict] | None = None
		self._forms: dict[str, list[str]] = {}

	def _load(self) -> None:
		"""Load and cache the tables; degrade to empty tables on failure."""
		if self._verbs is not None:
			return
		try:
			with self._path.open("rb") as conjugationFile:
				data = pickle.load(conjugationFile)
			self._verbs = data.get("verbs", {})
			self._forms = data.get("forms", {})
		except Exception:
			log.error("Unable to load the bundled Italian conjugation tables.", exc_info=True)
			self._verbs = {}
			self._forms = {}

	def resolve(self, word: str) -> list[str]:
		"""Return the candidate infinitives for one word, or an empty list."""
		self._load()
		key = (word or "").strip().casefold()
		if not key:
			return []
		if key in self._verbs:
			return [key]
		return list(self._forms.get(key, []))

	def table(self, lemma: str) -> dict | None:
		"""Return the conjugation table for one infinitive, or None."""
		self._load()
		return self._verbs.get(lemma)

	def contains(self, lemma: str) -> bool:
		"""Return whether the book has a table for this infinitive."""
		self._load()
		return lemma in self._verbs
