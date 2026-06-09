# -*- coding: utf-8 -*-

import time
from typing import Any, Callable

import speech
import speech.speech
import ui
from speech.extensions import filter_speechSequence

from ..common import cues
from ..common import config
from .manager import TranslationManager


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
_TRANSLATABLE_KEYS = ("name", "value", "description", "rowHeaderText", "columnHeaderText")

_origGetPropertiesSpeech: Callable | None = None
_origGetFormatFieldSpeech: Callable | None = None
_origGetControlFieldSpeech: Callable | None = None


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
	"""Marks all format field output (font, color, line number, etc.) as untranslatable."""
	result = _origGetFormatFieldSpeech(*args, **kwargs)
	return [_UntranslatableString(s) if isinstance(s, str) else s for s in result]


def _hookedGetControlFieldSpeech(attrs=None, *args, **kwargs):
	"""Marks format/metadata strings (like item counts and coords) as untranslatable, preserving content."""
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


class SpeechFilter:
	# Annotate instance variables at the class level
	manager: TranslationManager
	lastSpokenText: str
	_isSpeakingTranslation: bool
	_suppressCapture: int
	_gracePeriodEnd: float

	def __init__(self, manager: TranslationManager) -> None:
		super().__init__()
		self.manager = manager
		self.lastSpokenText = ""
		self._isSpeakingTranslation = False
		self._suppressCapture = 0
		self._gracePeriodEnd = 0.0

	def register(self) -> None:
		"""Registers the speech filter, cue suppression hook, and speech hooks."""
		filter_speechSequence.register(self.onSpeechSequence)
		cues.registerSpeechHook(self.suppressNextCapture)
		self._patchGetPropertiesSpeech()
		self._patchGetFormatFieldSpeech()
		self._patchGetControlFieldSpeech()

	def unregister(self) -> None:
		"""Unregisters the speech filter, cue suppression hook, and restores speech hooks."""
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
	def _extractText(sequence: list[Any], enableSmartFilter: bool) -> tuple[str, list[int]]:
		"""Extracts translatable text from a speech sequence.

		Collects all ``str`` items that are NOT ``_UntranslatableString``,
		which means:
		- plain text content from ``getTextInfoSpeech`` — included
		- ``TranslatableString`` (name, value, description) — included
		- ``_UntranslatableString`` (role, state, level) — excluded (if enableSmartFilter is True)

		Returns ``(joinedText, indicesIntoSequence)``.
		"""
		pairs = [
			(i, s)
			for i, s in enumerate(sequence)
			if isinstance(s, str)
			and (not enableSmartFilter or not isinstance(s, _UntranslatableString))
			and s.strip()
		]
		indices = [i for i, _ in pairs]
		text = " ".join(s.strip() for _, s in pairs)
		return text, indices

	def onSpeechSequence(self, sequence: list[Any]) -> list[Any]:
		# Extract translatable content, excluding roles/states.
		enableSmartFilter = config.getConfig().get("enableSmartFilter", True)
		textToSave, translatableIndices = self._extractText(sequence, enableSmartFilter)
		# Save the text unless suppression was requested by the cues module.
		# Suppressed speech is internal plugin messaging and should also
		# bypass auto-translate interception to avoid being swallowed.
		if textToSave:
			if self._suppressCapture > 0:
				self._suppressCapture -= 1
				return sequence
			elif time.monotonic() < self._gracePeriodEnd:
				# Inside the grace window; pass through without overwriting lastSpokenText.
				return sequence
			else:
				self.lastSpokenText = textToSave
		if not self.manager.isAutoTranslateEnabled:
			return sequence
		# To prevent translation loops, skip if the speech is already a translation result.
		if self._isSpeakingTranslation:
			self._isSpeakingTranslation = False
			return sequence
		# Trigger auto-translation if there is text.
		if textToSave:
			self.manager.requestTranslation(
				textToSave,
				isManual=False,
				showStatus=False,
				allowCopy=False,
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
		originalSequence: list[Any] | None = None,
		translatableIndices: list[int] | None = None,
	) -> None:
		"""
		Callback for a successful auto-translation.
		Called by the TranslationManager on the main thread.
		"""
		# 1. Set a flag to prevent this result from being re-translated.
		self._isSpeakingTranslation = True
		# 2. Reconstruct the sequence with translated content in place,
		#    preserving roles, states, and other NVDA speech commands.
		if originalSequence is not None and translatableIndices:
			reconstructed = list(originalSequence)
			reconstructed[translatableIndices[0]] = translation
			for idx in translatableIndices[1:]:
				reconstructed[idx] = ""
			speech.speech.speak(reconstructed)
		else:
			ui.message(translation)
