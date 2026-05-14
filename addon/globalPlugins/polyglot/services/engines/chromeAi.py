# -*- coding: utf-8 -*-

"""
chromeAi - Chrome On-Device AI Translation Engine.

Uses Chrome's built-in Translator and LanguageDetector APIs via CDP.
Download feedback uses periodic beep cues (not speech) to avoid
triggering the auto-translate cascade loop.
"""

import json
import threading
import time
from typing import Any
from collections.abc import Callable

import addonHandler
import queueHandler
from logHandler import log

from ...common.exceptions import EngineError
from ...common import cues, languages
from ..engine import ChunkedTranslationMixin
from ..cdpBridge import CdpBridge, CdpError

addonHandler.initTranslation()


class ChromeAiEngine(ChunkedTranslationMixin):
	id = "chrome_ai"
	name = _("Chrome AI (Offline)")
	_downloadLock = threading.Lock()
	_isPreparingModel = False
	_DETECTION_CONFIDENCE_THRESHOLD = 0.35
	_MAX_MODEL_PREPARATION_RETRIES = 2
	_MAX_CACHED_TRANSLATORS = 4
	_TRANSIENT_ERROR_MARKERS = (
		"AbortError",
		"InvalidStateError",
		"NetworkError",
		"NotAllowedError",
		"not allowed",
		"temporarily",
		"timed out",
	)

	def __init__(self) -> None:
		super().__init__()
		self._bridge = CdpBridge.getInstance()
		supportedCodes = [
			"auto",
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
		return "auto"

	@property
	def enabledConfigLabel(self) -> str:
		"""Returns the Chrome AI-specific label for the common enable checkbox."""
		return _("Enable Chrome AI offline engine (requires Chrome 138+, resources released on NVDA exit)")

	@property
	def defaultSourceLanguage(self) -> str:
		return "auto"

	@property
	def defaultTargetLanguage(self) -> str:
		return "zh"

	def getConfigSpec(self) -> list[dict[str, Any]]:
		allLangs = self.getSupportedLanguages()
		autoCode = self.autoDetectCode
		fromChoices = allLangs.copy()
		toChoices = allLangs.copy()
		if autoCode is not None:
			_unused = toChoices.pop(autoCode, None)
		swapChoices = toChoices.copy()
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
			{
				"id": "enableAutoSwap",
				"label": _(
					"Auto-swap if detected source matches target (source must be 'Auto-detect')",
				),
				"type": "checkbox",
				"default": False,
			},
			{
				"id": "swapLanguage",
				"label": _("Swap to language:"),
				"type": "choice",
				"choices": swapChoices,
				"default": "",
			},
		]

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, Any]:
		states: dict[str, Any] = {}
		allLangs = self.getSupportedLanguages()
		autoCode = self.autoDetectCode
		selectedFrom = allConfigs.get("langFrom")
		selectedTo = allConfigs.get("langTo")
		toChoices = allLangs.copy()
		if autoCode is not None:
			_unused = toChoices.pop(autoCode, None)
		fromChoices = allLangs.copy()
		if selectedTo:
			_unused = fromChoices.pop(selectedTo, None)
		validToLangs = toChoices.copy()
		if selectedFrom and selectedFrom != autoCode:
			_unused = validToLangs.pop(selectedFrom, None)
		states["langFrom"] = {"choices": fromChoices}
		states["langTo"] = {"choices": validToLangs}
		isAutoFrom = selectedFrom == autoCode
		states["enableAutoSwap"] = {"visible": isAutoFrom}
		isSwapVisible = isAutoFrom and allConfigs.get("enableAutoSwap", False)
		states["swapLanguage"] = {"visible": isSwapVisible, "choices": validToLangs.copy()}
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
					"Please enable it in the Polyglot settings panel to use.",
				),
			)
		if isCancelled and isCancelled():
			return {}
		# If model preparation is in progress, pass through the original text
		# to avoid silence and prevent a cascade of parallel attempts.
		with self._downloadLock:
			if ChromeAiEngine._isPreparingModel:
				log.debug("Chrome AI: model preparation in progress, passing through original text.")
				return {"translation": text, "langDetected": None, "noCache": True}
		log.debug(f"Chrome AI: translate {len(text)} chars, {langFrom}->{langTo}")
		try:
			self._bridge.ensureConnection()
		except CdpError as e:
			raise EngineError(str(e))

		# Now that pre-checks and connection are established, let the base class handle splitting
		return super().translate(text, langFrom, langTo, config, isCancelled)

	def _makeModelPreparationHandler(self, modelLabel: str) -> Callable[[str], None]:
		"""Builds a console log handler for Chrome model preparation progress events."""

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
				log.info(f"Chrome AI: {modelLabel} preparation started")
				with self._downloadLock:
					ChromeAiEngine._isPreparingModel = True
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					cues.Speech.message,
					# Translators: {model} is a model name like "Translation model" or "Language detection model".
					_("Preparing {model}...").format(model=modelLabel),
				)
			elif logText == "[MODEL_FINALIZING]":
				log.info(f"Chrome AI: {modelLabel} preparation finalizing")
			elif logText in ("[MODEL_END]", "[DOWNLOAD_END]"):
				log.info(f"Chrome AI: {modelLabel} preparation complete")
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
		"""Converts text to a JavaScript string literal."""
		return json.dumps(value, ensure_ascii=False)

	def _normalizeDetectedLanguage(self, languageCode: str) -> str | None:
		"""Normalizes LanguageDetector BCP 47 results to Chrome Translator language codes."""
		if not languageCode or languageCode == "und":
			return None
		code = languageCode.replace("_", "-")
		lowerCode = code.lower()
		if lowerCode in ("he", "iw"):
			return "iw"
		if lowerCode.startswith("zh-hant") or lowerCode in ("zh-tw", "zh-hk", "zh-mo"):
			return "zh-Hant"
		if lowerCode.startswith("zh"):
			return "zh"
		return lowerCode.split("-", 1)[0]

	def _shouldRetryResult(self, result: dict[str, Any]) -> bool:
		"""Returns whether a Chrome AI result looks like a cold-start transient failure."""
		code = result.get("code")
		if code in ("API_ERR_UNDEFINED", "DETECTOR_ERR_UNDEFINED", "PARSE_ERR"):
			return True
		if code not in ("DETECTOR_ERR_EXCEPTION", "TRANSLATE_ERR_EXCEPTION"):
			return False
		message = str(result.get("message", ""))
		return any(marker.lower() in message.lower() for marker in self._TRANSIENT_ERROR_MARKERS)

	def _evaluateChromeAiScript(
		self,
		jsPayload: str,
		onConsoleLog: Callable[[str], None],
		operationName: str,
	) -> dict[str, Any]:
		"""Evaluates a Chrome AI script with a bounded cold-start retry."""
		lastResult: dict[str, Any] | None = None
		for attempt in range(self._MAX_MODEL_PREPARATION_RETRIES + 1):
			try:
				result = self._bridge.evaluateSync(jsPayload, onConsoleLog=onConsoleLog)
			except CdpError as e:
				if attempt >= self._MAX_MODEL_PREPARATION_RETRIES:
					raise EngineError(str(e)) from e
				log.warning(f"Chrome AI: {operationName} CDP error on cold-start attempt {attempt + 1}: {e}")
				time.sleep(0.4 * (attempt + 1))
				continue
			lastResult = result
			if not self._shouldRetryResult(result) or attempt >= self._MAX_MODEL_PREPARATION_RETRIES:
				return result
			log.warning(f"Chrome AI: retrying {operationName} after transient result: {result}")
			time.sleep(0.4 * (attempt + 1))
		return lastResult or {"code": "PARSE_ERR", "raw": ""}

	def _detectLanguage(self, text: str) -> dict[str, str | None]:
		"""Detect the source language via a separate CDP call.

		Runs in its own evaluateSync with a fresh userGesture activation,
		so its model download won't consume the activation needed by the Translator.
		"""
		inputText = self._toJsStringLiteral(text)
		confidenceThreshold = self._DETECTION_CONFIDENCE_THRESHOLD
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
			if (typeof LanguageDetector === 'undefined') {{
				return JSON.stringify({{code: 'DETECTOR_ERR_UNDEFINED'}});
			}}
			const inputText = {inputText};
			const downloadStates = new Set(['downloadable', 'downloading']);
			try {{
				if (!globalThis._aiLanguageDetector) {{
					const detAvail = await LanguageDetector.availability();
					if (detAvail === 'no' || detAvail === 'unavailable') {{
						return JSON.stringify({{code: 'DETECTOR_ERR_UNAVAILABLE', state: detAvail}});
					}}
					const detOptions = {{}};
					if (downloadStates.has(detAvail)) {{
						console.log('[MODEL_START]');
						detOptions.monitor = (m) => {{
							m.addEventListener('downloadprogress', (e) => {{
								const pct = Math.max(0, Math.min(100, Math.round(e.loaded * 100)));
								console.log('[MODEL_PROGRESS]' + pct);
								if (pct >= 100) {{
									console.log('[MODEL_FINALIZING]');
								}}
							}});
						}};
					}}
					globalThis._aiLanguageDetector = await LanguageDetector.create(detOptions);
					if (downloadStates.has(detAvail)) {{
						console.log('[MODEL_END]');
					}}
				}}
				const detections = await globalThis._aiLanguageDetector.detect(inputText);
				if (detections.length > 0 && detections[0].confidence >= {confidenceThreshold}) {{
					return JSON.stringify({{
						code: 'SUCCESS',
						lang: detections[0].detectedLanguage,
						confidence: detections[0].confidence,
					}});
				}}
				return JSON.stringify({{
					code: 'DETECTOR_ERR_LOW_CONFIDENCE',
					confidence: detections.length > 0 ? detections[0].confidence : 0,
				}});
			}} catch (e) {{
				const error = makeError(e);
				return JSON.stringify({{
					code: 'DETECTOR_ERR_EXCEPTION',
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
				onConsoleLog=self._makeModelPreparationHandler(_("Language detection model")),
				operationName="language detection",
			)
		finally:
			if ChromeAiEngine._isPreparingModel:
				with self._downloadLock:
					ChromeAiEngine._isPreparingModel = False
		code = result.get("code")
		if code == "SUCCESS":
			sourceLang = self._normalizeDetectedLanguage(str(result.get("lang", "")))
			if sourceLang is None:
				result = {"code": "DETECTOR_ERR_LOW_CONFIDENCE", "confidence": result.get("confidence", 0)}
				self._parseCdpResult(result, "")
			return {"sourceLang": str(sourceLang)}
		self._parseCdpResult(result, "")
		raise EngineError(_("Unexpected response from Chrome AI."))

	def _translateChunk(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
	) -> dict[str, Any]:
		detectedLang = None
		if langFrom == "auto":
			detectResult = self._detectLanguage(text)
			langFrom = detectResult["sourceLang"]
			detectedLang = langFrom
		inputText = self._toJsStringLiteral(text)
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
			globalThis._aiTranslatorOrder = globalThis._aiTranslatorOrder || [];
			const key = sourceLang + '-' + targetLang;
			const rememberTranslator = () => {{
				globalThis._aiTranslatorOrder = globalThis._aiTranslatorOrder.filter((item) => item !== key);
				globalThis._aiTranslatorOrder.push(key);
				while (globalThis._aiTranslatorOrder.length > {self._MAX_CACHED_TRANSLATORS}) {{
					const oldKey = globalThis._aiTranslatorOrder.shift();
					const oldTranslator = globalThis._aiTranslators[oldKey];
					if (oldTranslator && typeof oldTranslator.destroy === 'function') {{
						oldTranslator.destroy();
					}}
					delete globalThis._aiTranslators[oldKey];
				}}
			}};
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
				rememberTranslator();
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
				globalThis._aiTranslatorOrder = globalThis._aiTranslatorOrder.filter((item) => item !== key);
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
		if detectedLang:
			result["detectedLang"] = detectedLang
		return self._parseCdpResult(result, text)

	def _parseCdpResult(self, result: dict[str, Any], text: str) -> dict[str, Any]:
		code = result.get("code")
		detectedLang = result.get("detectedLang")
		log.debug(f"Chrome AI: JS returned code={code}, detectedLang={detectedLang}")
		if code == "SUCCESS":
			return {
				"translation": result.get("data", ""),
				"langDetected": detectedLang,
			}
		elif code == "SAME_LANGUAGE":
			return {
				"translation": text,
				"langDetected": detectedLang,
			}
		elif code == "API_ERR_UNDEFINED":
			raise EngineError(
				_(
					"Chrome's Translator API is not available. "
					"Please update Chrome to version 138 or later "
					"and ensure the TranslationAPI flag is enabled in chrome://flags.",
				),
			)
		elif code == "DETECTOR_ERR_UNDEFINED":
			raise EngineError(
				_(
					"Chrome's LanguageDetector API is not available. "
					"Please update Chrome and enable the TranslationAPI and LanguageDetectionAPI flags.",
				),
			)
		elif code == "ERR_INSECURE_CONTEXT":
			raise EngineError(
				# Translators: Error message when Chrome AI is running on a page that cannot access the API.
				_(
					"Chrome AI requires a secure page context. "
					"Please restart NVDA and try the Chrome AI engine again.",
				),
			)
		elif code == "DETECTOR_ERR_UNAVAILABLE":
			raise EngineError(
				_("Language detection is not supported in this Chrome installation."),
			)
		elif code == "DETECTOR_ERR_LOW_CONFIDENCE":
			confidence = result.get("confidence", 0)
			raise EngineError(
				_(
					"Could not confidently detect the source language. "
					"Please select a source language instead of Auto-detect. "
					"(confidence: {confidence})",
				).format(confidence=confidence),
			)
		elif code == "DETECTOR_ERR_EXCEPTION":
			raise EngineError(_("Language detection error: ") + result.get("message", ""))
		elif code == "MODEL_STATE_NO":
			pair = result.get("pair", "?->?")
			raise EngineError(
				_("Language pair {pair} is not supported by Chrome's offline models.").format(pair=pair),
			)
		elif code == "TRANSLATE_ERR_EXCEPTION":
			raise EngineError(_("Chrome AI error: ") + result.get("message", _("Unknown error")))
		else:
			raise EngineError(_("Unexpected response from Chrome AI."))
