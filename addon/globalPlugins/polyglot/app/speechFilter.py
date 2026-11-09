# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import time
from typing import Any, Callable

import addonHandler
import config as nvdaConfig
import languageHandler
import speech
import speech.speech
import textInfos
from speech.extensions import filter_speechSequence

from ..common import cues
from ..common import config
from ..common.wordDictionary import (
	EnglishChineseDictionary,
	ItalianChineseDictionary,
	WordLookupResult,
	formatWordLookupResult,
)
from .manager import TranslationManager


addonHandler.initTranslation()


class TranslatableString(str):
	"""Marks user content (name, value, description) from ``getPropertiesSpeech``.

	Survives through the speech pipeline until ``filter_speechSequence`` is
	applied, letting ``SpeechFilter`` identify translatable user content.
	"""

	pass


class _UntranslatableString(str):
	"""Marks NVDA metadata (role, state, level, position) that should not be translated.

	Applied to all ``getPropertiesSpeech`` output strings that are not already
	``TranslatableString``, so that roles and states can be distinguished from
	plain text content produced by ``getTextInfoSpeech``.
	"""

	pass


# Keys in ``getPropertiesSpeech`` kwargs that carry user content.
_TRANSLATABLE_KEYS = (
	"name",
	"value",
	"description",
	"rowHeaderText",
	"columnHeaderText",
	"placeholder",
	"errorMessage",
)

_origGetPropertiesSpeech: Callable | None = None
_origGetFormatFieldSpeech: Callable | None = None
_origGetControlFieldSpeech: Callable | None = None
_origGetSpellingSpeech: Callable | None = None
_origPackageGetSpellingSpeech: Callable | None = None
_origSpeakTypedCharacters: Callable | None = None
_origPackageSpeakTypedCharacters: Callable | None = None
_origSpeakText: Callable | None = None
_origPackageSpeakText: Callable | None = None
_origGetSelectionMessageSpeech: Callable | None = None
_origPackageGetSelectionMessageSpeech: Callable | None = None
_origGetIndentationSpeech: Callable | None = None
_origPackageGetIndentationSpeech: Callable | None = None
_suppressAutoTranslationDepth = 0


def _markStringsUntranslatable(sequence: list[Any]) -> list[Any]:
	"""Mark all strings in a speech sequence as NVDA metadata."""
	return [_UntranslatableString(s) if isinstance(s, str) else s for s in sequence]


def _markGeneratedStringsUntranslatable(sequence):
	"""Mark generated speech strings as NVDA metadata."""
	for item in sequence:
		yield _UntranslatableString(item) if isinstance(item, str) else item


def _hookedGetPropertiesSpeech(reason=speech.speech.OutputReason.QUERY, **kwargs):
	"""Tags user-content inputs and marks remaining output as untranslatable."""
	for key in _TRANSLATABLE_KEYS:
		val = kwargs.get(key)
		if isinstance(val, str) and val.strip():
			kwargs[key] = TranslatableString(val)
	result = _origGetPropertiesSpeech(reason, **kwargs)
	# Wrap any remaining plain strings (role, state, level, etc.) as untranslatable.
	return [
		s if isinstance(s, TranslatableString) else _UntranslatableString(s) if isinstance(s, str) else s
		for s in result
	]


def _hookedGetFormatFieldSpeech(*args, **kwargs):
	"""Mark all format field output as untranslatable."""
	result = _origGetFormatFieldSpeech(*args, **kwargs)
	return [_UntranslatableString(s) if isinstance(s, str) else s for s in result]


def _hookedGetControlFieldSpeech(attrs=None, *args, **kwargs):
	"""Mark format metadata as untranslatable while preserving content strings."""
	# Forward attrs properly, handling cases where it might be passed as a kwarg
	if attrs is None:
		attrs = kwargs.get("attrs")
	elif "attrs" in kwargs:
		kwargs.pop("attrs")

	result = _origGetControlFieldSpeech(attrs, *args, **kwargs)

	content = attrs.get("content") if hasattr(attrs, "get") else None
	new_result = []
	for s in result:
		if isinstance(s, str) and not isinstance(s, (TranslatableString, _UntranslatableString)):
			if content is not None and s == content:
				new_result.append(TranslatableString(s))
			else:
				new_result.append(_UntranslatableString(s))
		else:
			new_result.append(s)
	return new_result


def _hookedGetSpellingSpeech(*args, **kwargs):
	"""Mark spelling and character-navigation speech as metadata."""
	return _markGeneratedStringsUntranslatable(_origGetSpellingSpeech(*args, **kwargs))


def _hookedSpeakTypedCharacters(ch: str) -> None:
	"""Speaks typed echo without capturing it for translation."""
	global _suppressAutoTranslationDepth
	_suppressAutoTranslationDepth += 1
	try:
		_origSpeakTypedCharacters(ch)
	finally:
		_suppressAutoTranslationDepth -= 1


def _hookedSpeakText(
	text: str,
	reason=speech.speech.OutputReason.MESSAGE,
	symbolLevel=None,
	priority=None,
) -> None:
	"""Speaks blank text reports as metadata while preserving real text."""
	if speech.speech.isBlank(text):
		sequence = speech.speech._getSpeakMessageSpeech(text)
		if sequence:
			speech.speech.speak(
				_markStringsUntranslatable(sequence),
				symbolLevel=symbolLevel,
				priority=priority,
			)
		return
	_origSpeakText(text, reason=reason, symbolLevel=symbolLevel, priority=priority)


def _hookedGetSelectionMessageSpeech(message: str, text: str | list[Any]) -> list[Any]:
	"""Mark selection affixes as metadata while preserving selected text."""
	prefix, sep, suffix = message.partition("%s")
	if isinstance(text, list):
		if not sep:
			return _markStringsUntranslatable(speech.speech._getSpeakMessageSpeech(message)) + text
		sequence = list(text)
		if prefix:
			sequence.insert(0, _UntranslatableString(prefix))
		if suffix:
			sequence.append(_UntranslatableString(suffix))
		return sequence

	if not sep or len(text) >= speech.speech.MAX_LENGTH_FOR_SELECTION_REPORTING:
		return _markStringsUntranslatable(_origGetSelectionMessageSpeech(message, text))

	sequence: list[Any] = []
	if prefix:
		sequence.append(_UntranslatableString(prefix))
	if text:
		sequence.append(TranslatableString(text))
	if suffix:
		sequence.append(_UntranslatableString(suffix))
	return sequence


def _hookedGetIndentationSpeech(indentation: str, formatConfig: dict[str, Any]) -> list[Any]:
	"""Mark indentation reports as metadata."""
	return _markStringsUntranslatable(_origGetIndentationSpeech(indentation, formatConfig))


class SpeechFilter:
	"""Filters Polyglot speech and manages the NVDA speech hooks it installs."""

	# Annotate instance variables at the class level
	manager: TranslationManager
	lastSpokenText: str
	_isSpeakingTranslation: bool
	_suppressCapture: int
	_gracePeriodEnd: float
	_wordDictionary: EnglishChineseDictionary
	_italianWordDictionary: ItalianChineseDictionary
	_isWordDefinitionHookActive: bool
	_origModuleSpellTextInfo: Callable[..., None] | None
	_origPackageSpellTextInfo: Callable[..., None] | None
	_hookedModuleSpellTextInfo: Callable[..., None] | None
	_hookedPackageSpellTextInfo: Callable[..., None] | None

	def __init__(self, manager: TranslationManager) -> None:
		"""Initialize speech filtering for the supplied translation manager."""
		super().__init__()
		self.manager = manager
		self.lastSpokenText = ""
		self._isSpeakingTranslation = False
		self._suppressCapture = 0
		self._gracePeriodEnd = 0.0
		self._wordDictionary = manager.wordDictionary
		self._italianWordDictionary = manager.italianDictionary
		self._isWordDefinitionHookActive = False
		self._origModuleSpellTextInfo = None
		self._origPackageSpellTextInfo = None
		self._hookedModuleSpellTextInfo = None
		self._hookedPackageSpellTextInfo = None

	def register(self) -> None:
		"""Register the speech filter, cue suppression hook, and speech hooks."""
		filter_speechSequence.register(self.onSpeechSequence)
		cues.registerSpeechHook(self.suppressNextCapture)
		config.post_localDictionarySettingsChanged.register(self._updateWordDefinitionHook)
		nvdaConfig.post_configProfileSwitch.register(self._updateWordDefinitionHook)
		nvdaConfig.post_configReset.register(self._updateWordDefinitionHook)
		self._patchGetPropertiesSpeech()
		self._patchGetFormatFieldSpeech()
		self._patchGetControlFieldSpeech()
		self._patchGetSpellingSpeech()
		self._updateWordDefinitionHook()
		self._patchSpeakTypedCharacters()
		self._patchSpeakText()
		self._patchGetSelectionMessageSpeech()
		self._patchGetIndentationSpeech()

	def unregister(self) -> None:
		"""Unregisters the speech filter, cue suppression hook, and restores speech hooks."""
		config.post_localDictionarySettingsChanged.unregister(self._updateWordDefinitionHook)
		nvdaConfig.post_configProfileSwitch.unregister(self._updateWordDefinitionHook)
		nvdaConfig.post_configReset.unregister(self._updateWordDefinitionHook)
		self._unpatchGetIndentationSpeech()
		self._unpatchGetSelectionMessageSpeech()
		self._unpatchSpeakText()
		self._unpatchSpeakTypedCharacters()
		self._unpatchSpellTextInfo()
		self._unpatchGetSpellingSpeech()
		self._unpatchGetControlFieldSpeech()
		self._unpatchGetFormatFieldSpeech()
		self._unpatchGetPropertiesSpeech()
		_unused = filter_speechSequence.unregister(self.onSpeechSequence)
		cues.unregisterSpeechHook()

	def _patchGetPropertiesSpeech(self) -> None:
		"""Patches ``speech.speech.getPropertiesSpeech`` to tag translatable fields."""
		global _origGetPropertiesSpeech
		_origGetPropertiesSpeech = speech.speech.getPropertiesSpeech
		speech.speech.getPropertiesSpeech = _hookedGetPropertiesSpeech

	def _unpatchGetPropertiesSpeech(self) -> None:
		"""Restores the original ``speech.speech.getPropertiesSpeech``."""
		global _origGetPropertiesSpeech
		if _origGetPropertiesSpeech is not None:
			speech.speech.getPropertiesSpeech = _origGetPropertiesSpeech
			_origGetPropertiesSpeech = None

	def _patchGetFormatFieldSpeech(self) -> None:
		"""Patches ``getFormatFieldSpeech`` to tag output as untranslatable.

		Patches both ``speech.speech`` (module-level calls) and ``speech``
		(package-level calls from ``textInfos.TextInfo.getFormatFieldSpeech``).
		"""
		global _origGetFormatFieldSpeech
		_origGetFormatFieldSpeech = speech.speech.getFormatFieldSpeech
		speech.speech.getFormatFieldSpeech = _hookedGetFormatFieldSpeech
		speech.getFormatFieldSpeech = _hookedGetFormatFieldSpeech

	def _unpatchGetFormatFieldSpeech(self) -> None:
		"""Restores the original ``getFormatFieldSpeech`` at both levels."""
		global _origGetFormatFieldSpeech
		if _origGetFormatFieldSpeech is not None:
			speech.speech.getFormatFieldSpeech = _origGetFormatFieldSpeech
			speech.getFormatFieldSpeech = _origGetFormatFieldSpeech
			_origGetFormatFieldSpeech = None

	def _patchGetControlFieldSpeech(self) -> None:
		"""Patches ``getControlFieldSpeech`` to tag output as untranslatable except for main content.

		Patches both ``speech.speech`` (module-level) and ``speech``
		(package-level calls from ``textInfos.TextInfo.getControlFieldSpeech``).
		"""
		global _origGetControlFieldSpeech
		_origGetControlFieldSpeech = speech.speech.getControlFieldSpeech
		speech.speech.getControlFieldSpeech = _hookedGetControlFieldSpeech
		speech.getControlFieldSpeech = _hookedGetControlFieldSpeech

	def _unpatchGetControlFieldSpeech(self) -> None:
		"""Restores the original ``getControlFieldSpeech`` at both levels."""
		global _origGetControlFieldSpeech
		if _origGetControlFieldSpeech is not None:
			speech.speech.getControlFieldSpeech = _origGetControlFieldSpeech
			speech.getControlFieldSpeech = _origGetControlFieldSpeech
			_origGetControlFieldSpeech = None

	def _patchGetSpellingSpeech(self) -> None:
		"""Patches spelling speech so character metadata is not translated."""
		global _origGetSpellingSpeech, _origPackageGetSpellingSpeech
		_origGetSpellingSpeech = speech.speech.getSpellingSpeech
		_origPackageGetSpellingSpeech = speech.getSpellingSpeech
		speech.speech.getSpellingSpeech = _hookedGetSpellingSpeech
		speech.getSpellingSpeech = _hookedGetSpellingSpeech

	def _unpatchGetSpellingSpeech(self) -> None:
		"""Restores ``getSpellingSpeech`` at both levels."""
		global _origGetSpellingSpeech, _origPackageGetSpellingSpeech
		if _origGetSpellingSpeech is not None:
			speech.speech.getSpellingSpeech = _origGetSpellingSpeech
			_origGetSpellingSpeech = None
		if _origPackageGetSpellingSpeech is not None:
			speech.getSpellingSpeech = _origPackageGetSpellingSpeech
			_origPackageGetSpellingSpeech = None

	def _patchSpellTextInfo(self) -> None:
		"""Patch repeated TextInfo spelling with local word definitions for Chinese NVDA."""
		if self._isWordDefinitionHookActive or not self._isChineseNvdaLanguage():
			return

		moduleOriginal = speech.speech.spellTextInfo
		packageOriginal = speech.spellTextInfo
		moduleHook = self._createSpellTextInfoHook(moduleOriginal)
		packageHook = self._createSpellTextInfoHook(packageOriginal)
		self._origModuleSpellTextInfo = moduleOriginal
		self._origPackageSpellTextInfo = packageOriginal
		self._hookedModuleSpellTextInfo = moduleHook
		self._hookedPackageSpellTextInfo = packageHook
		self._isWordDefinitionHookActive = True
		speech.speech.spellTextInfo = moduleHook
		speech.spellTextInfo = packageHook

	def _unpatchSpellTextInfo(self) -> None:
		"""Disable local definitions and safely restore both ``spellTextInfo`` aliases."""
		self._isWordDefinitionHookActive = False
		if (
			self._hookedModuleSpellTextInfo is not None
			and self._origModuleSpellTextInfo is not None
			and speech.speech.spellTextInfo is self._hookedModuleSpellTextInfo
		):
			speech.speech.spellTextInfo = self._origModuleSpellTextInfo
		if (
			self._hookedPackageSpellTextInfo is not None
			and self._origPackageSpellTextInfo is not None
			and speech.spellTextInfo is self._hookedPackageSpellTextInfo
		):
			speech.spellTextInfo = self._origPackageSpellTextInfo
		self._origModuleSpellTextInfo = None
		self._origPackageSpellTextInfo = None
		self._hookedModuleSpellTextInfo = None
		self._hookedPackageSpellTextInfo = None

	def _updateWordDefinitionHook(self) -> None:
		"""Install or remove the text-review dictionary hook according to current settings."""
		if config.getConfig().get("enableLocalDictionaryForTextReview", True):
			self._patchSpellTextInfo()
		else:
			self._unpatchSpellTextInfo()

	def _createSpellTextInfoHook(
		self,
		original: Callable[..., None],
	) -> Callable[..., None]:
		"""Create a wrapper which preserves the function chain installed at one import level."""

		def hookedSpellTextInfo(
			info: textInfos.TextInfo,
			useCharacterDescriptions: bool = False,
			priority: speech.Spri | None = None,
		) -> None:
			"""Speak a local definition or delegate unchanged to NVDA's spelling implementation."""
			# Keep NVDA's public keyword name; core review commands pass it by keyword.
			if self._isWordDefinitionHookActive and useCharacterDescriptions:
				dictionary = self._getTextReviewDictionary()
				if dictionary is not None:
					lookupResult = dictionary.lookup(info.text)
					if lookupResult is not None:
						self._speakWordLookupResult(lookupResult, priority)
						return
			original(
				info,
				useCharacterDescriptions=useCharacterDescriptions,
				priority=priority,
			)

		return hookedSpellTextInfo

	def _getTextReviewDictionary(self) -> EnglishChineseDictionary | None:
		"""Return the dictionary selected for text review, or None when disabled.

		English and Italian are separate bundles, so text review only ever
		consults the language chosen in the settings.
		"""
		language = config.getConfig().get("reviewDictionaryLanguage", "en")
		if language == "it":
			return self._italianWordDictionary
		if language == "en":
			return self._wordDictionary
		return None

	@staticmethod
	def _isChineseNvdaLanguage() -> bool:
		"""Return whether NVDA's current interface language is Chinese."""
		normalizedLanguage = languageHandler.normalizeLanguage(languageHandler.getLanguage())
		return bool(normalizedLanguage and normalizedLanguage.partition("_")[0] == "zh")

	@classmethod
	def _speakWordLookupResult(
		cls,
		result: WordLookupResult,
		priority: speech.Spri | None,
	) -> None:
		"""Speak one lookup result without capturing or automatically translating it."""
		global _suppressAutoTranslationDepth
		_suppressAutoTranslationDepth += 1
		try:
			speech.speakMessage(formatWordLookupResult(result), priority=priority)
		finally:
			_suppressAutoTranslationDepth -= 1

	def _patchSpeakTypedCharacters(self) -> None:
		"""Patches typed echo so typed input is not auto-translated."""
		global _origSpeakTypedCharacters, _origPackageSpeakTypedCharacters
		_origSpeakTypedCharacters = speech.speech.speakTypedCharacters
		_origPackageSpeakTypedCharacters = speech.speakTypedCharacters
		speech.speech.speakTypedCharacters = _hookedSpeakTypedCharacters
		speech.speakTypedCharacters = _hookedSpeakTypedCharacters

	def _unpatchSpeakTypedCharacters(self) -> None:
		"""Restores ``speakTypedCharacters`` at both levels."""
		global _origSpeakTypedCharacters, _origPackageSpeakTypedCharacters
		if _origSpeakTypedCharacters is not None:
			speech.speech.speakTypedCharacters = _origSpeakTypedCharacters
			_origSpeakTypedCharacters = None
		if _origPackageSpeakTypedCharacters is not None:
			speech.speakTypedCharacters = _origPackageSpeakTypedCharacters
			_origPackageSpeakTypedCharacters = None

	def _patchSpeakText(self) -> None:
		"""Patches blank ``speakText`` reports so they are not translated."""
		global _origSpeakText, _origPackageSpeakText
		_origSpeakText = speech.speech.speakText
		_origPackageSpeakText = speech.speakText
		speech.speech.speakText = _hookedSpeakText
		speech.speakText = _hookedSpeakText

	def _unpatchSpeakText(self) -> None:
		"""Restores ``speakText`` at both levels."""
		global _origSpeakText, _origPackageSpeakText
		if _origSpeakText is not None:
			speech.speech.speakText = _origSpeakText
			_origSpeakText = None
		if _origPackageSpeakText is not None:
			speech.speakText = _origPackageSpeakText
			_origPackageSpeakText = None

	def _patchGetSelectionMessageSpeech(self) -> None:
		"""Patches selection speech so only selected text is translated."""
		global _origGetSelectionMessageSpeech, _origPackageGetSelectionMessageSpeech
		_origGetSelectionMessageSpeech = speech.speech._getSelectionMessageSpeech
		_origPackageGetSelectionMessageSpeech = speech._getSelectionMessageSpeech
		speech.speech._getSelectionMessageSpeech = _hookedGetSelectionMessageSpeech
		speech._getSelectionMessageSpeech = _hookedGetSelectionMessageSpeech

	def _unpatchGetSelectionMessageSpeech(self) -> None:
		"""Restores ``_getSelectionMessageSpeech`` at both levels."""
		global _origGetSelectionMessageSpeech, _origPackageGetSelectionMessageSpeech
		if _origGetSelectionMessageSpeech is not None:
			speech.speech._getSelectionMessageSpeech = _origGetSelectionMessageSpeech
			_origGetSelectionMessageSpeech = None
		if _origPackageGetSelectionMessageSpeech is not None:
			speech._getSelectionMessageSpeech = _origPackageGetSelectionMessageSpeech
			_origPackageGetSelectionMessageSpeech = None

	def _patchGetIndentationSpeech(self) -> None:
		"""Patches indentation speech so indentation reports are not translated."""
		global _origGetIndentationSpeech, _origPackageGetIndentationSpeech
		_origGetIndentationSpeech = speech.speech.getIndentationSpeech
		_origPackageGetIndentationSpeech = speech.getIndentationSpeech
		speech.speech.getIndentationSpeech = _hookedGetIndentationSpeech
		speech.getIndentationSpeech = _hookedGetIndentationSpeech

	def _unpatchGetIndentationSpeech(self) -> None:
		"""Restores ``getIndentationSpeech`` at both levels."""
		global _origGetIndentationSpeech, _origPackageGetIndentationSpeech
		if _origGetIndentationSpeech is not None:
			speech.speech.getIndentationSpeech = _origGetIndentationSpeech
			_origGetIndentationSpeech = None
		if _origPackageGetIndentationSpeech is not None:
			speech.getIndentationSpeech = _origPackageGetIndentationSpeech
			_origPackageGetIndentationSpeech = None

	def suppressNextCapture(self) -> None:
		"""Prevents the next speech sequence from being captured as spoken text."""
		self._suppressCapture += 1

	def setGracePeriod(self, durationMs: int = 300) -> None:
		"""Temporarily prevents speech from overwriting ``lastSpokenText``.

		Called when entering the command layer.  Releasing modifier keys
		(e.g. Alt from NVDA+Alt+Z) may trigger IME or keyboard-layout
		switch notifications that would otherwise overwrite the text the
		user intends to translate.
		"""
		self._gracePeriodEnd = time.monotonic() + durationMs / 1000.0

	@staticmethod
	def _extractText(sequence: list[Any], isSmartFilterEnabled: bool) -> tuple[str, list[int]]:
		"""Extract translatable text from a speech sequence.

		Collects all ``str`` items that are NOT ``_UntranslatableString``,
		which means:
		- plain text content from ``getTextInfoSpeech`` — included
		- ``TranslatableString`` (name, value, description) — included
		- ``_UntranslatableString`` (role, state, level) — excluded when smart filtering is enabled

		Returns ``(joinedText, indicesIntoSequence)``.
		"""
		pairs = [
			(i, s)
			for i, s in enumerate(sequence)
			if isinstance(s, str)
			and (not isSmartFilterEnabled or not isinstance(s, _UntranslatableString))
			and s.strip()
		]
		indices = [i for i, _ in pairs]
		text = " ".join(s.strip() for _, s in pairs)
		return text, indices

	def onSpeechSequence(self, sequence: list[Any]) -> list[Any]:
		"""Capture translatable speech and replace it when automatic translation is enabled."""
		# Extract translatable content, excluding roles/states.
		isSmartFilterEnabled = config.getConfig().get("enableSmartFilter", True)
		textToSave, translatableIndices = self._extractText(sequence, isSmartFilterEnabled)
		# Save the text unless suppression was requested by the cues module.
		# Suppressed speech is internal plugin messaging and should also
		# bypass auto-translate interception to avoid being swallowed.
		if self._suppressCapture > 0:
			self._suppressCapture -= 1
			return sequence
		if _suppressAutoTranslationDepth > 0:
			return sequence
		if not textToSave:
			if self._isSpeakingTranslation:
				self._isSpeakingTranslation = False
			return sequence
		if time.monotonic() < self._gracePeriodEnd:
			# Inside the grace window; pass through without overwriting lastSpokenText.
			return sequence
		self.lastSpokenText = textToSave
		if not self.manager.isAutoTranslateEnabled:
			return sequence
		# To prevent translation loops, skip if the speech is already a translation result.
		if self._isSpeakingTranslation:
			self._isSpeakingTranslation = False
			return sequence
		self.manager.requestTranslation(
			textToSave,
			isManual=False,
			shouldShowStatus=False,
			shouldAllowCopy=False,
			onSuccess=lambda translation: self._handleAutoTranslationResult(
				translation,
				sequence,
				translatableIndices,
			),
		)
		# Block the original speech sequence; it will be replaced by the translation.
		return []

	def _handleAutoTranslationResult(
		self,
		translation: str,
		originalSequence: list[Any],
		translatableIndices: list[int],
	) -> None:
		"""
		Handle a successful automatic translation.
		Called by the TranslationManager on the main thread.
		"""
		self._isSpeakingTranslation = True
		reconstructed = list(originalSequence)
		reconstructed[translatableIndices[0]] = translation
		for idx in translatableIndices[1:]:
			reconstructed[idx] = ""
		speech.speech.speak(reconstructed)
