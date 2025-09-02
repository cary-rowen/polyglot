# -*- coding: utf-8 -*-

from speech.extensions import filter_speechSequence
import ui
from . import config
from .core import manager as translation_manager

class SpeechFilter:
    def __init__(self):
        self.last_spoken_text = ""
        self._is_speaking_translation = False

    def register(self):
        filter_speechSequence.register(self.on_speech_sequence)

    def unregister(self):
        filter_speechSequence.unregister(self.on_speech_sequence)

    def on_speech_sequence(self, sequence):
        # Extract and save the text for the "Translate last spoken text" command.
        text_to_save = " ".join([s for s in sequence if isinstance(s, str) and s.strip()])
        if text_to_save:
            self.last_spoken_text = text_to_save
        if not translation_manager.auto_translate_enabled:
            return sequence
        # To prevent translation loops, skip if the speech is already a translation result.
        if self._is_speaking_translation:
            self._is_speaking_translation = False
            return sequence
        # Trigger auto-translation if there is text.
        if text_to_save:
            translation_manager.request_translation(
                text_to_save,
                is_manual=False,
                show_status=False,
                allow_copy=False,
                on_success=self._handle_auto_translation_result
            )
        # Block the original speech sequence; it will be replaced by the translation.
        return []

    def _handle_auto_translation_result(self, translation: str):
        """
        Callback for a successful auto-translation.
        Called by the TranslationManager on the main thread.
        """
        # 1. Set a flag to prevent this result from being re-translated.
        self._is_speaking_translation = True
        # 2. Speak the translation.
        ui.message(translation)


speech_filter_instance = SpeechFilter()