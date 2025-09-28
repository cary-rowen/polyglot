# -*- coding: utf-8 -*-

"""
A stateless, utility module for providing user feedback (cues).

This module offers static methods for playing sounds, beeps, and speaking text.
It also provides simple, standalone functions for managing a periodic,
background cue loop for tasks like indicating progress.
"""

import os
import threading
from collections.abc import Callable

import addonHandler
import globalVars
import nvwave
import tones
import ui


addonHandler.initTranslation()


class CueType:
	START = "start"
	SUCCESS = "success"
	ERROR = "error"
	WAITING = "waiting"
	INFO = "info"


_sounds_dir = os.path.join(globalVars.appArgs.configPath, "addons", "polyglot", "sounds")


def _get_sound_path(name: str) -> str:
	"""Internal helper to get the full path for a sound file."""
	return os.path.join(_sounds_dir, f"{name}.wav")


# --- Internal Periodic Cue Machinery (Shared by all cue types) ---
_progress_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _start_periodic_cue_internal(cue_function: Callable[[], None], interval_ms: int, delay_ms: int) -> None:
	"""
	Internal implementation to start a periodic cue in a background thread.
	"""
	global _progress_thread
	stop_periodic_cue()  # Stop any existing cue first
	_stop_event.clear()

	def loop_target():
		interval_sec = interval_ms / 1000.0
		delay_sec = delay_ms / 1000.0
		if delay_sec > 0:
			if _stop_event.wait(delay_sec):
				return
		while not _stop_event.is_set():
			cue_function()
			if _stop_event.wait(interval_sec):
				break

	_progress_thread = threading.Thread(target=loop_target, daemon=True)
	_progress_thread.start()


def stop_periodic_cue() -> None:
	"""
	Signals the currently running periodic cue, if any, to stop.
	This function is safe to call even if no cue is running.
	"""
	global _progress_thread
	_stop_event.set()
	_progress_thread = None


class sound:
	"""A namespace for all sound-file-based cues."""

	@staticmethod
	def play(sound_name: str) -> None:
		sound_path = _get_sound_path(sound_name)
		if os.path.exists(sound_path):
			nvwave.playWaveFile(sound_path)

	@staticmethod
	def start_periodic(event_name: str, interval_ms: int, delay_ms: int) -> None:
		"""
		Starts a periodic sound cue using asynchronous playback.

		IMPORTANT: This method uses non-blocking (asynchronous) sound playback.
		To prevent audio overlap and chaotic sound stacking, the caller MUST
		ensure that the specified `interval_ms` is greater than the duration
		of the audio file being played (e.g., 'waiting.wav').

		For example, if 'waiting.wav' is 300ms long, `interval_ms` should be
		set to a value significantly higher, like 800ms or more.

		Args:
		    event_name: The name of the sound file to play periodically
		                (e.g., CueType.WAITING).
		    interval_ms: The interval in milliseconds between each playback trigger.
		    delay_ms: The initial delay in milliseconds before the first trigger.
		"""
		cue_function = lambda: sound.play(event_name)
		_start_periodic_cue_internal(cue_function, interval_ms, delay_ms)


class beep:
	"""A namespace for all beep-based cues."""

	_BEEPS = {
		CueType.START: (100, 10),
		CueType.SUCCESS: (440, 50),
		CueType.ERROR: (220, 120),
		CueType.WAITING: (450, 30),
		CueType.INFO: (330, 30),
	}

	@staticmethod
	def play(event_name: str) -> None:
		"""Plays a predefined beep pattern."""
		freq, dur = beep._BEEPS.get(event_name, (200, 50))
		tones.beep(freq, dur)

	@staticmethod
	def start_periodic(event_name: str, interval_ms: int, delay_ms: int) -> None:
		"""Starts a periodic beep cue."""
		cue_function = lambda: beep.play(event_name)
		_start_periodic_cue_internal(cue_function, interval_ms, delay_ms)


class speech:
	"""A namespace for all speech-based cues."""

	@staticmethod
	def message(text: str) -> None:
		"""Speaks text. MUST be called from the main NVDA thread."""
		ui.message(text)
