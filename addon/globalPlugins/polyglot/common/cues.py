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
import config
import globalVars
import nvwave
import queueHandler
import tones
import ui


addonHandler.initTranslation()


class CueType:
	START = "start"
	SUCCESS = "success"
	ERROR = "error"
	WAITING = "waiting"
	INFO = "info"


_soundsDir = os.path.join(globalVars.appArgs.configPath, "addons", "polyglot", "sounds")


def _getSoundPath(name: str) -> str:
	"""Internal helper to get the full path for a sound file."""
	return os.path.join(_soundsDir, f"{name}.wav")


# --- Internal Periodic Cue Machinery (Shared by all cue types) ---
_progressThread: threading.Thread | None = None
_stopEvent = threading.Event()


def _startPeriodicCueInternal(cueFunction: Callable[[], None], intervalMs: int, delayMs: int) -> None:
	"""
	Internal implementation to start a periodic cue in a background thread.
	"""
	global _progressThread
	stopPeriodicCue()  # Stop any existing cue first
	_stopEvent.clear()

	def loopTarget():
		intervalSec = intervalMs / 1000.0
		delaySec = delayMs / 1000.0
		if delaySec > 0:
			if _stopEvent.wait(delaySec):
				return
		while not _stopEvent.is_set():
			cueFunction()
			if _stopEvent.wait(intervalSec):
				break

	_progressThread = threading.Thread(target=loopTarget, daemon=True)
	_progressThread.start()


def stopPeriodicCue() -> None:
	"""
	Signals the currently running periodic cue, if any, to stop.
	This function is safe to call even if no cue is running.
	"""
	global _progressThread
	_stopEvent.set()
	_progressThread = None


class Sound:
	"""A namespace for all sound-file-based cues."""

	@staticmethod
	def play(soundName: str) -> None:
		soundPath = _getSoundPath(soundName)
		if os.path.exists(soundPath):
			nvwave.playWaveFile(soundPath)

	@staticmethod
	def startPeriodic(eventName: str, intervalMs: int, delayMs: int) -> None:
		"""
		Starts a periodic sound cue using asynchronous playback.

		IMPORTANT: This method uses non-blocking (asynchronous) sound playback.
		To prevent audio overlap and chaotic sound stacking, the caller MUST
		ensure that the specified `intervalMs` is greater than the duration
		of the audio file being played (e.g., 'waiting.wav').

		For example, if 'waiting.wav' is 300ms long, `intervalMs` should be
		set to a value significantly higher, like 800ms or more.

		Args:
		    eventName: The name of the sound file to play periodically
		                (e.g., CueType.WAITING).
		    intervalMs: The interval in milliseconds between each playback trigger.
		    delayMs: The initial delay in milliseconds before the first trigger.
		"""
		def cueFunction():
			Sound.play(eventName)
		_startPeriodicCueInternal(cueFunction, intervalMs, delayMs)


class Beep:
	"""A namespace for all beep-based cues."""

	_BEEPS = {
		CueType.START: (100, 10),
		CueType.SUCCESS: (440, 50),
		CueType.ERROR: (220, 120),
		CueType.WAITING: (450, 30),
		CueType.INFO: (330, 30),
	}

	@staticmethod
	def play(eventName: str) -> None:
		"""Plays a predefined beep pattern."""
		freq, dur = Beep._BEEPS.get(eventName, (200, 50))
		tones.beep(freq, dur)

	@staticmethod
	def startPeriodic(eventName: str, intervalMs: int, delayMs: int) -> None:
		"""Starts a periodic beep cue."""
		def cueFunction():
			Beep.play(eventName)
		_startPeriodicCueInternal(cueFunction, intervalMs, delayMs)

	_lastBeepPct: int = -100
	_lastSpeechPct: int = -100

	@classmethod
	def reportProgress(cls, current: int, total: int) -> None:
		"""Reports progress respecting NVDA's progressBarOutputMode setting.

		Beep feedback runs on any thread.
		Speech feedback is scheduled to the main thread via queueHandler.
		"""
		if total <= 1:
			return
		current = max(0, min(current, total))
		pct = int(current / total * 100)
		pbConf = config.conf["presentation"]["progressBarUpdates"]
		mode = pbConf["progressBarOutputMode"]
		if mode == "off":
			return
		if mode in ("beep", "both"):
			if abs(pct - cls._lastBeepPct) >= pbConf["beepPercentageInterval"]:
				freq = int(pbConf["beepMinHZ"] * 2 ** (pct / 25.0))
				tones.beep(freq, 40)
				cls._lastBeepPct = pct
		if mode in ("speak", "both"):
			if abs(pct - cls._lastSpeechPct) >= pbConf["speechPercentageInterval"]:
				cls._lastSpeechPct = pct
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					Speech.message,
					_("%d percent") % pct,
				)

	@classmethod
	def resetProgress(cls) -> None:
		"""Resets progress tracking. Call before starting a new tracked task."""
		cls._lastBeepPct = -100
		cls._lastSpeechPct = -100

	@staticmethod
	def playProgress(current: int, total: int) -> None:
		"""
		Plays a dynamic pitch beep based on progress.
		The pitch rises exponentially as the task nears completion,
		matching NVDA's native progress bar beep range (110Hz to 1760Hz).
		"""
		if total <= 1:
			return
		# Clamp current value to range [1, total]
		current = max(1, min(current, total))
		progress = current / total
		# NVDA's native progress bar range: 4 octaves starting from 110Hz
		# Formula: 110 * (2 ^ (progress * 4))
		freq = int(110 * (2 ** (progress * 4)))
		tones.beep(freq, 40)


class Speech:
	"""A namespace for all speech-based cues."""

	@staticmethod
	def message(text: str, suppressCapture: bool = True) -> None:
		"""Speaks text. MUST be called from the main NVDA thread.

		Args:
			text: The text to speak.
			suppressCapture: If True, notifies the speech filter to skip
				capturing this message as `lastSpokenText`.
		"""
		if suppressCapture and _onBeforeSpeech is not None:
			_onBeforeSpeech()
		ui.message(text)


# --- Speech Hook Registration ---
_onBeforeSpeech: Callable[[], None] | None = None


def registerSpeechHook(callback: Callable[[], None]) -> None:
	"""Registers a callback to be invoked before the cues module speaks."""
	global _onBeforeSpeech
	_onBeforeSpeech = callback


def unregisterSpeechHook() -> None:
	"""Unregisters the speech hook."""
	global _onBeforeSpeech
	_onBeforeSpeech = None
