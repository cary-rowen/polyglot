# -*- coding: utf-8 -*-

"""
chromeAi - Chrome On-Device AI Translation Engine.

Uses Chrome's built-in Translator and LanguageDetector APIs via CDP.
Download feedback uses periodic beep cues (not speech) to avoid
triggering the auto-translate cascade loop.
"""

import threading
from typing import Any
from collections.abc import Callable

import addonHandler
import queueHandler
from logHandler import log

from ...common.exceptions import EngineError
from ...common import cues
from ..engine import ChunkedTranslationMixin
from ..cdpBridge import CdpBridge, CdpError

addonHandler.initTranslation()


class ChromeAiEngine(ChunkedTranslationMixin):
	id = "chrome_ai"
	name = _("Chrome AI (Offline)")
	_downloadLock = threading.Lock()
	_isDownloading = False

	def __init__(self) -> None:
		super().__init__()
		self._bridge = CdpBridge.getInstance()
		self._supportedLangs = {
			"auto": _("Auto-detect"),
			"en": _("English"),
			"zh": _("Chinese"),
			"ja": _("Japanese"),
			"ko": _("Korean"),
			"fr": _("French"),
			"de": _("German"),
			"es": _("Spanish"),
			"ru": _("Russian"),
			"pt": _("Portuguese"),
			"it": _("Italian"),
			"ar": _("Arabic"),
			"nl": _("Dutch"),
			"hi": _("Hindi"),
			"tr": _("Turkish"),
		}

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

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
			{
				"id": "enabled",
				"label": _("Enable Chrome AI offline engine (requires Chrome 138+, resources released on NVDA exit)"),
				"type": "checkbox",
				"default": True,
			},
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
					"Auto-swap if detected source matches target (source must be 'Auto-detect')"
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
		isEnabled = allConfigs.get("enabled", True)
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
		states["langFrom"] = {"visible": isEnabled, "choices": fromChoices}
		states["langTo"] = {"visible": isEnabled, "choices": validToLangs}
		isAutoFrom = selectedFrom == autoCode
		states["enableAutoSwap"] = {"visible": isEnabled and isAutoFrom}
		isSwapVisible = isEnabled and isAutoFrom and allConfigs.get("enableAutoSwap", False)
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
		if not config.get("enabled", True):
			log.debug("Chrome AI: engine is disabled, refusing translation request.")
			raise EngineError(
				_("Chrome AI offline engine is disabled. "
				  "Please enable it in the Polyglot settings panel to use.")
			)
		if isCancelled and isCancelled():
			return {}
		# If a model download is in progress, pass through the original text
		# to avoid silence and prevent a cascade of parallel attempts.
		with self._downloadLock:
			if ChromeAiEngine._isDownloading:
				log.debug("Chrome AI: model download in progress, passing through original text.")
				return {"translation": text, "langDetected": None, "noCache": True}
		log.debug(f"Chrome AI: translate {len(text)} chars, {langFrom}->{langTo}")
		try:
			self._bridge.ensureConnection()
		except CdpError as e:
			raise EngineError(str(e))
		
		# Now that pre-checks and connection are established, let the base class handle splitting
		return super().translate(text, langFrom, langTo, config, isCancelled)

	def _translateChunk(
		self, text: str, langFrom: str, langTo: str, config: dict[str, Any]
	) -> dict[str, Any]:
		# Escape for JS template literal
		safeText = text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
		jsPayload = f"""
		(async () => {{
			if (typeof Translator === 'undefined') {{
				return JSON.stringify({{code: 'API_ERR_UNDEFINED'}});
			}}
			const inputText = `{safeText}`;
			let sourceLang = '{langFrom}';
			const targetLang = '{langTo}';
			let detectedLang = null;
			if (sourceLang === 'auto') {{
				if (typeof LanguageDetector === 'undefined') {{
					return JSON.stringify({{code: 'DETECTOR_ERR_UNDEFINED'}});
				}}
				try {{
					if (!globalThis._aiLanguageDetector) {{
						const detAvail = await LanguageDetector.availability();
						if (detAvail === 'no' || detAvail === 'unavailable') {{
							return JSON.stringify({{code: 'DETECTOR_ERR_UNAVAILABLE'}});
						}}
						globalThis._aiLanguageDetector = await LanguageDetector.create();
					}}
					const detections = await globalThis._aiLanguageDetector.detect(inputText);
					if (detections.length > 0 && detections[0].confidence > 0.1) {{
						sourceLang = detections[0].detectedLanguage;
						detectedLang = sourceLang;
					}} else {{
						sourceLang = 'en';
						detectedLang = 'en';
					}}
				}} catch (e) {{
					return JSON.stringify({{code: 'DETECTOR_ERR_EXCEPTION', message: e.toString()}});
				}}
			}}
			if (sourceLang === targetLang) {{
				return JSON.stringify({{code: 'SAME_LANGUAGE', detectedLang: detectedLang}});
			}}
			globalThis._aiTranslators = globalThis._aiTranslators || {{}};
			const key = sourceLang + '-' + targetLang;
			try {{
				if (!globalThis._aiTranslators[key]) {{
					const options = {{ sourceLanguage: sourceLang, targetLanguage: targetLang }};
					const avail = await Translator.availability(options);
					if (avail === 'no' || avail === 'unavailable') {{
						return JSON.stringify({{code: 'MODEL_STATE_NO', detectedLang: detectedLang, pair: key}});
					}}
					if (avail === 'downloadable') {{
						console.log('[DOWNLOAD_START]');
						options.monitor = (m) => {{
							m.addEventListener('downloadprogress', (e) => {{
								console.log('[DOWNLOAD_PROGRESS]' + Math.round(e.loaded * 100));
							}});
						}};
					}}
					globalThis._aiTranslators[key] = await Translator.create(options);
					if (avail === 'downloadable') {{
						console.log('[DOWNLOAD_END]');
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
				return JSON.stringify({{code: 'SUCCESS', data: result, detectedLang: detectedLang}});
			}} catch (err) {{
				delete globalThis._aiTranslators[key];
				return JSON.stringify({{code: 'TRANSLATE_ERR_EXCEPTION', message: err.toString()}});
			}}
		}})();
		"""

		def onConsoleLog(logText: str) -> None:
			"""Handle model download progress events from Chrome's console output."""
			if "[DOWNLOAD_PROGRESS]" in logText:
				try:
					pct = int(logText.replace("[DOWNLOAD_PROGRESS]", ""))
					cues.Beep.reportProgress(pct, 100)
				except ValueError:
					pass
			elif "[DOWNLOAD_START]" in logText:
				cues.Beep.resetProgress()
				log.info("Chrome AI: model download started")
				with self._downloadLock:
					ChromeAiEngine._isDownloading = True
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					cues.Speech.message,
					_("Translation model downloading..."),
				)
			elif "[DOWNLOAD_END]" in logText:
				log.info("Chrome AI: model download complete")
				with self._downloadLock:
					ChromeAiEngine._isDownloading = False
				queueHandler.queueFunction(
					queueHandler.eventQueue,
					cues.Speech.message,
					_("Download complete."),
				)

		try:
			result = self._bridge.evaluateSync(jsPayload, onConsoleLog=onConsoleLog)
		except CdpError as e:
			raise EngineError(str(e))
		except Exception as e:
			raise EngineError(_("Unexpected Chrome AI error: ") + str(e))
		finally:
			if ChromeAiEngine._isDownloading:
				with self._downloadLock:
					ChromeAiEngine._isDownloading = False
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
				_("Chrome's Translator API is not available. "
				  "Please update Chrome to version 138 or later "
				  "and ensure the TranslationAPI flag is enabled in chrome://flags.")
			)
		elif code == "DETECTOR_ERR_UNDEFINED":
			raise EngineError(
				_("Chrome's LanguageDetector API is not available. "
				  "Please update Chrome and enable the TranslationAPI flag.")
			)
		elif code == "DETECTOR_ERR_UNAVAILABLE":
			raise EngineError(
				_("Language detection is not supported in this Chrome installation.")
			)
		elif code == "DETECTOR_ERR_EXCEPTION":
			raise EngineError(_("Language detection error: ") + result.get('message', ''))
		elif code == "MODEL_STATE_NO":
			pair = result.get("pair", "?->?")
			raise EngineError(
				_("Language pair {pair} is not supported by Chrome's offline models.").format(pair=pair)
			)
		elif code == "TRANSLATE_ERR_EXCEPTION":
			raise EngineError(_("Chrome AI error: ") + result.get('message', _('Unknown error')))
		else:
			raise EngineError(_("Unexpected response from Chrome AI."))
