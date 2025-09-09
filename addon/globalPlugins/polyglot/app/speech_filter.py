# -*- coding: utf-8 -*-

from typing import Any

import ui
from speech.extensions import filter_speechSequence

from .manager import TranslationManager


class SpeechFilter:
	# Annotate instance variables at the class level
	manager: TranslationManager
	last_spoken_text: str
	_is_speaking_translation: bool

	def __init__(self, manager: TranslationManager) -> None:
		super().__init__()
		self.manager = manager
		self.last_spoken_text = ""
		self._is_speaking_translation = False

	def register(self) -> None:
		filter_speechSequence.register(self.on_speech_sequence)

	def unregister(self) -> None:
		_unused = filter_speechSequence.unregister(self.on_speech_sequence)

	def on_speech_sequence(self, sequence: list[Any]) -> list[Any]:
		# Extract and save the text for the "Translate last spoken text" command.
		text_to_save = " ".join([s for s in sequence if isinstance(s, str) and s.strip()])
		if text_to_save:
			self.last_spoken_text = text_to_save
		if not self.manager.auto_translate_enabled:
			return sequence
		# To prevent translation loops, skip if the speech is already a translation result.
		if self._is_speaking_translation:
			self._is_speaking_translation = False
			return sequence
		# Trigger auto-translation if there is text.
		if text_to_save:
			self.manager.request_translation(
				text_to_save,
				is_manual=False,
				show_status=False,
				allow_copy=False,
				on_success=self._handle_auto_translation_result,
			)
		# Block the original speech sequence; it will be replaced by the translation.
		return []

	def _handle_auto_translation_result(self, translation: str) -> None:
		"""
		Callback for a successful auto-translation.
		Called by the TranslationManager on the main thread.
		"""
		# 1. Set a flag to prevent this result from being re-translated.
		self._is_speaking_translation = True
		# 2. Speak the translation.
		ui.message(translation)
