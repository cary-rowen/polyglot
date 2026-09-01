# -*- coding: utf-8 -*-

# Copyright (C) 2025-2026 cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""
chromeAi - Chrome On-Device AI Translation Engine.

Uses Chrome's built-in Translator API via CDP.
Download feedback uses periodic beep cues (not speech) to avoid
triggering the auto-translate cascade loop.
"""

import json
import re
import threading
import time
from typing import Any
from collections.abc import Callable

import addonHandler
import queueHandler
from logHandler import log

from ...common.exceptions import EngineError, SilentTranslationCancel
from ...common import cues, languages
from ...modelManager.service import getModelManagerService
from ..engine import ChunkedTranslationMixin
from ..cdpBridge import CdpBridge, CdpError

addonHandler.initTranslation()


class ChromeAiEngine(ChunkedTranslationMixin):
	"""Translate text offline with Chrome's on-device Translator API."""

	id = "chrome_ai"
	name = _("Chrome AI (Offline)")
	_downloadLock = threading.Lock()
	_isPreparingModel = False
	_MODEL_PREPARATION_POLL_INTERVAL = 0.1
	_MAX_TRANSIENT_RETRIES = 2
	_ENGLISH_EM_DASH_PATTERN = re.compile(r"[ \t]*\u2014[ \t]*")
	_TRANSIENT_ERROR_MARKERS = (
		"AbortError",
		"InvalidStateError",
		"NetworkError",
		"NotAllowedError",
		"UnknownError",
		"Other generic failures occurred",
		"not allowed",
		"temporarily",
		"timed out",
	)

	def __init__(self) -> None:
		"""Initialize CDP access and the supported Chrome AI language set."""
		super().__init__()
		self._bridge = CdpBridge.getInstance()
		supportedCodes = [
			"ar",
			"bg",
			"bn",
			"cs",
			"da",
			"de",
			"el",
			"en",
			"es",
			"fi",
			"fr",
			"hi",
			"hr",
			"hu",
			"id",
			"it",
			"iw",
			"ja",
			"kn",
			"ko",
			"lt",
			"mr",
			"nl",
			"no",
			"pl",
			"pt",
			"ro",
			"ru",
			"sk",
			"sl",
			"sv",
			"ta",
			"te",
			"th",
			"tr",
			"uk",
			"vi",
			"zh",
			"zh-Hant",
		]
		self._supportedLangs = languages.getLanguageDictForCodes(supportedCodes)

	@property
	def autoDetectCode(self) -> str | None:
		return None

	@property
	def enabledConfigLabel(self) -> str:
		"""Returns the Chrome AI-specific label for the common enable checkbox."""
		return _("Enable Chrome AI offline engine (Chrome 138+)")

	@property
	def defaultSourceLanguage(self) -> str:
		return "en"

	@property
	def defaultTargetLanguage(self) -> str:
		return "zh"

	def getConfigSpec(self) -> list[dict[str, Any]]:
		allLangs = self.getSupportedLanguages()
		fromChoices = allLangs.copy()
		toChoices = allLangs.copy()
		return [
			self.getEnabledConfigSpec(),
			{
				"id": "langFrom",
				"label": _("Source language:"),
				"type": "choice",
				"choices": fromChoices,
				"default": self.defaultSourceLanguage,
			},
			{
				"id": "langTo",
				"label": _("Target language:"),
				"type": "choice",
				"choices": toChoices,
				"default": self.defaultTargetLanguage,
			},
		]

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, Any]:
		states: dict[str, Any] = {}
		allLangs = self.getSupportedLanguages()
		selectedFrom = allConfigs.get("langFrom", self.defaultSourceLanguage)
		selectedTo = allConfigs.get("langTo", self.defaultTargetLanguage)
		toChoices = allLangs.copy()
		fromChoices = allLangs.copy()
		if selectedTo:
			_unused = fromChoices.pop(selectedTo, None)
		if selectedFrom:
			_unused = toChoices.pop(selectedFrom, None)
		states["langFrom"] = {"choices": fromChoices}
		states["langTo"] = {"choices": toChoices}
		return states

	def getSupportedLanguages(self) -> dict[str, str]:
		return self._supportedLangs

	@property
	def maxRequestLength(self) -> int:
		return 3000

	@property
	def requestDelayRange(self) -> tuple[float, float]:
		# Local model, no need for delay between chunks
		return (0, 0)

	def _waitForModelPreparation(self, isCancelled: Callable[[], bool] | None) -> bool:
		"""Wait for another request's model preparation before translating."""
		with self._downloadLock:
			isPreparing = ChromeAiEngine._isPreparingModel
		if not isPreparing:
			return True
		log.debug("Chrome AI: model preparation in progress, waiting before translating.")
		while True:
			if isCancelled and isCancelled():
				return False
			with self._downloadLock:
				if not ChromeAiEngine._isPreparingModel:
					return True
			time.sleep(self._MODEL_PREPARATION_POLL_INTERVAL)

	def _ensureNativeModelReady(self, langFrom: str, langTo: str) -> None:
		"""Prompt for native model installation when the required package is missing."""
		if langFrom == langTo:
			return
		try:
			shouldContinue = getModelManagerService().ensureModelForPairInteractive(langFrom, langTo)
		except Exception:
			log.error("Chrome AI: native model manager check failed; falling back to Chrome.", exc_info=True)
			return
		if not shouldContinue:
			raise SilentTranslationCancel()

	def translate(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
		isCancelled: Callable[[], bool] | None = None,
	) -> dict[str, Any]:
		if not self.isEnabled(config):
			log.debug("Chrome AI: engine is disabled, refusing translation request.")
			raise EngineError(
				_(
					"Chrome AI offline engine is disabled. "
					"Enable it in the Polyglot settings panel before using it.",
				),
			)
		if isCancelled and isCancelled():
			return {}
		self._ensureNativeModelReady(langFrom, langTo)
		if isCancelled and isCancelled():
			return {}
		if not self._waitForModelPreparation(isCancelled):
			return {}
		log.debug("Chrome AI: translating %d characters (%s to %s).", len(text), langFrom, langTo)
		try:
			self._bridge.ensureConnection()
		except CdpError as e:
			raise EngineError(str(e))

		# Now that pre-checks and connection are established, let the base class handle splitting
		return super().translate(text, langFrom, langTo, config, isCancelled)

	def _makeModelPreparationHandler(self, modelLabel: str) -> Callable[[str], None]:
		"""Build a handler for Chrome model-preparation progress events."""

		def handler(logText: str) -> None:
			if "[MODEL_PROGRESS]" in logText or "[DOWNLOAD_PROGRESS]" in logText:
				try:
					rawPct = logText.replace("[MODEL_PROGRESS]", "").replace("[DOWNLOAD_PROGRESS]", "")
					pct = int(rawPct)
					cues.Beep.reportProgress(pct, 100)
				except ValueError:
					pass
			elif logText in ("[MODEL_START]", "[DOWNLOAD_START]"):
				cues.Beep.resetProgress()
				log.debug("Chrome AI: %s preparation started.", modelLabel)
				with self._downloadLock:
					ChromeAiEngine._isPreparingModel = True
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					cues.Speech.message,
					# Translators: {model} is a model name like "Translation model".
					_("Preparing {model}...").format(model=modelLabel),
				)
			elif logText == "[MODEL_FINALIZING]":
				log.debug("Chrome AI: %s preparation finalizing.", modelLabel)
			elif logText in ("[MODEL_END]", "[DOWNLOAD_END]"):
				log.debug("Chrome AI: %s preparation complete.", modelLabel)
				with self._downloadLock:
					ChromeAiEngine._isPreparingModel = False
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					cues.Speech.message,
					# Translators: Announced when Chrome has finished preparing an offline model.
					_("Model ready."),
				)

		return handler

	def _toJsStringLiteral(self, value: str) -> str:
		"""Convert text to a JavaScript string literal."""
		return json.dumps(value, ensure_ascii=False)

	def _normalizeSourceTextForTranslation(self, text: str, sourceLang: str) -> str:
		"""Normalize Chrome AI input quirks without changing non-English text."""
		if sourceLang != "en" or "\u2014" not in text:
			return text
		return self._ENGLISH_EM_DASH_PATTERN.sub(" - ", text)

	def _shouldRetryResult(self, result: dict[str, Any]) -> bool:
		"""Return whether a Chrome AI result represents a transient failure."""
		code = result.get("code")
		if code in ("API_ERR_UNDEFINED", "PARSE_ERR"):
			return True
		if code != "TRANSLATE_ERR_EXCEPTION":
			return False
		message = f"{result.get('name', '')} {result.get('message', '')}".lower()
		return any(marker.lower() in message for marker in self._TRANSIENT_ERROR_MARKERS)

	def _evaluateChromeAiScript(
		self,
		jsPayload: str,
		onConsoleLog: Callable[[str], None],
		operationName: str,
	) -> dict[str, Any]:
		"""Evaluate a Chrome AI script with bounded transient retries."""
		lastResult: dict[str, Any] | None = None
		for attempt in range(self._MAX_TRANSIENT_RETRIES + 1):
			try:
				result = self._bridge.evaluateSync(jsPayload, onConsoleLog=onConsoleLog)
			except CdpError as e:
				if attempt >= self._MAX_TRANSIENT_RETRIES:
					raise EngineError(str(e)) from e
				log.warning(
					"Chrome AI: %s CDP error on transient attempt %d (%s).",
					operationName,
					attempt + 1,
					type(e).__name__,
				)
				time.sleep(0.4 * (attempt + 1))
				continue
			lastResult = result
			if not self._shouldRetryResult(result) or attempt >= self._MAX_TRANSIENT_RETRIES:
				return result
			log.warning(
				"Chrome AI: retrying %s after transient result code %s.",
				operationName,
				result.get("code", "unknown"),
			)
			time.sleep(0.4 * (attempt + 1))
		return lastResult or {"code": "PARSE_ERR", "raw": ""}

	def _translateChunk(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
	) -> dict[str, Any]:
		translationText = self._normalizeSourceTextForTranslation(text, langFrom)
		inputText = self._toJsStringLiteral(translationText)
		sourceLang = self._toJsStringLiteral(langFrom)
		targetLang = self._toJsStringLiteral(langTo)
		jsPayload = f"""
		(async () => {{
			const makeError = (e) => {{
				return {{
					name: e && e.name ? e.name : '',
					message: e && e.message ? e.message : e.toString(),
					stack: e && e.stack ? e.stack : '',
				}};
			}};
			if (!globalThis.isSecureContext) {{
				return JSON.stringify({{code: 'ERR_INSECURE_CONTEXT', href: location.href}});
			}}
			if (typeof Translator === 'undefined') {{
				return JSON.stringify({{code: 'API_ERR_UNDEFINED'}});
			}}
			const inputText = {inputText};
			const sourceLang = {sourceLang};
			const targetLang = {targetLang};
			const downloadStates = new Set(['downloadable', 'downloading']);
			if (sourceLang === targetLang) {{
				return JSON.stringify({{code: 'SAME_LANGUAGE'}});
			}}
			globalThis._aiTranslators = globalThis._aiTranslators || {{}};
			const key = sourceLang + '-' + targetLang;
			try {{
				if (!globalThis._aiTranslators[key]) {{
					const options = {{ sourceLanguage: sourceLang, targetLanguage: targetLang }};
					const avail = await Translator.availability(options);
					if (avail === 'no' || avail === 'unavailable') {{
						return JSON.stringify({{code: 'MODEL_STATE_NO', pair: key, state: avail}});
					}}
					if (downloadStates.has(avail)) {{
						console.log('[MODEL_START]');
						options.monitor = (m) => {{
							m.addEventListener('downloadprogress', (e) => {{
								const pct = Math.max(0, Math.min(100, Math.round(e.loaded * 100)));
								console.log('[MODEL_PROGRESS]' + pct);
								if (pct >= 100) {{
									console.log('[MODEL_FINALIZING]');
								}}
							}});
						}};
					}}
					globalThis._aiTranslators[key] = await Translator.create(options);
					if (downloadStates.has(avail)) {{
						console.log('[MODEL_END]');
					}}
				}}
				// Chrome AI models discard newlines; translate line-by-line to preserve structure.
				const lines = inputText.split('\\n');
				const translatedLines = [];
				for (const line of lines) {{
					if (line.trim() === '') {{
						translatedLines.push(line);
					}} else {{
						translatedLines.push(await globalThis._aiTranslators[key].translate(line));
					}}
				}}
				const result = translatedLines.join('\\n');
				return JSON.stringify({{code: 'SUCCESS', data: result}});
			}} catch (err) {{
				delete globalThis._aiTranslators[key];
				const error = makeError(err);
				return JSON.stringify({{
					code: 'TRANSLATE_ERR_EXCEPTION',
					name: error.name,
					message: error.name ? error.name + ': ' + error.message : error.message,
					stack: error.stack,
				}});
			}}
		}})();
		"""
		try:
			result = self._evaluateChromeAiScript(
				jsPayload,
				onConsoleLog=self._makeModelPreparationHandler(_("Translation model")),
				operationName=f"translation {langFrom}->{langTo}",
			)
		except EngineError:
			raise
		except Exception as e:
			raise EngineError(_("Unexpected Chrome AI error: ") + str(e))
		finally:
			if ChromeAiEngine._isPreparingModel:
				with self._downloadLock:
					ChromeAiEngine._isPreparingModel = False
		return self._parseCdpResult(result, text)

	def _parseCdpResult(self, result: dict[str, Any], text: str) -> dict[str, Any]:
		code = result.get("code")
		log.debug(f"Chrome AI: JS returned code={code}")
		if code == "SUCCESS":
			return {
				"translation": result.get("data", ""),
			}
		elif code == "SAME_LANGUAGE":
			return {
				"translation": text,
			}
		elif code == "API_ERR_UNDEFINED":
			raise EngineError(
				_(
					"Chrome's Translator API is not available. "
					"Please update Chrome to version 138 or later "
					"and ensure the TranslationAPI flag is enabled in chrome://flags.",
				),
			)
		elif code == "ERR_INSECURE_CONTEXT":
			raise EngineError(
				# Translators: Error message when Chrome AI is running on a page that cannot access the API.
				_(
					"Chrome AI must run in a secure page context. "
					"Please restart NVDA and try the Chrome AI engine again.",
				),
			)
		elif code == "MODEL_STATE_NO":
			pair = result.get("pair", "?->?")
			log.debug("Chrome AI: language pair %s is unsupported; returning original text.", pair)
			return {
				"translation": text,
			}
		elif code == "TRANSLATE_ERR_EXCEPTION":
			raise EngineError(_("Chrome AI error: ") + result.get("message", _("Unknown error")))
		else:
			raise EngineError(_("Chrome AI returned an unexpected response."))
