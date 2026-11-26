# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
from typing import Any

import addonHandler
from logHandler import log

from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError

addonHandler.initTranslation()


class DeepLEngine(BaseHttpEngine):
	"""Translate text through the configurable DeepL Free or Pro API."""

	id = "deepl"
	name = _("DeepL")

	BASE_URL_FREE = "https://api-free.deepl.com/v2/translate"
	BASE_URL_PRO = "https://api.deepl.com/v2/translate"
	FORMALITY_SUPPORTED_LANGUAGES = {"DE", "IT", "ES", "PL", "RU", "FR", "PT-PT", "NL", "JA", "PT-BR"}

	@property
	def maxRequestLength(self) -> int:
		return 10000

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "ZH"

	def getConfigSpec(self) -> list[dict]:
		spec = super().getConfigSpec()
		spec.extend(
			[
				{"id": "apiKey", "label": _("API Key (Auth Key)"), "type": "password", "default": ""},
				{"id": "useFreeApi", "label": _("Use Free API"), "type": "checkbox", "default": True},
				{"id": "context", "label": _("Context (optional):"), "type": "text", "default": ""},
				{
					"id": "splitSentences",
					"label": _("Sentence splitting mode:"),
					"type": "choice",
					"choices": {
						"on": _("On (split at punctuation and newlines)"),
						"off": _("Off (no splitting)"),
						"nonewlines": _("Only at punctuation"),
					},
					"default": "on",
				},
				{
					"id": "preserveFormatting",
					"label": _("Preserve formatting"),
					"type": "checkbox",
					"default": False,
				},
				{
					"id": "formality",
					"label": _("Formality (for supported languages):"),
					"type": "choice",
					"choices": {
						"default": _("Default"),
						"more": _("More formal"),
						"less": _("Less formal"),
					},
					"default": "default",
				},
				{
					"id": "modelType",
					"label": _("Model type:"),
					"type": "choice",
					"choices": {
						"latency_optimized": _("Speed-optimized (default)"),
						"quality_optimized": _("Quality-optimized"),
						"prefer_quality_optimized": _("Prefer quality-optimized model"),
					},
					"default": "latency_optimized",
				},
			],
		)
		return spec

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, dict[str, Any]]:
		states = super().getUiStates(allConfigs)
		targetLang = allConfigs.get("langTo", "")
		isFormalitySupported = targetLang.upper() in self.FORMALITY_SUPPORTED_LANGUAGES
		states["formality"] = {"enabled": isFormalitySupported}
		return states

	def getSupportedLanguages(self) -> dict:
		return {
			"auto": "Auto-detect",
			"BG": "Bulgarian",
			"CS": "Czech",
			"DA": "Danish",
			"DE": "German",
			"EL": "Greek",
			"EN": "English",
			"ES": "Spanish",
			"ET": "Estonian",
			"FI": "Finnish",
			"FR": "French",
			"HU": "Hungarian",
			"ID": "Indonesian",
			"IT": "Italian",
			"JA": "Japanese",
			"KO": "Korean",
			"LT": "Lithuanian",
			"LV": "Latvian",
			"NB": "Norwegian (Bokmål)",
			"NL": "Dutch",
			"PL": "Polish",
			"PT": "Portuguese",
			"RO": "Romanian",
			"RU": "Russian",
			"SK": "Slovak",
			"SL": "Slovenian",
			"SV": "Swedish",
			"TR": "Turkish",
			"UK": "Ukrainian",
			"ZH": "Chinese",
		}

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		apiKey = config.get("apiKey", "").strip()
		if not apiKey:
			raise AuthenticationError(_("DeepL API Key (Auth Key) is not configured."))
		useFreeApi = config.get("useFreeApi", True)
		if not useFreeApi and apiKey.endswith(":fx"):
			raise AuthenticationError(
				_(
					"You have selected the Pro API, but the provided key is for the Free API. Please check 'Use Free API' in settings.",
				),
			)

		baseUrl = self.BASE_URL_FREE if useFreeApi else self.BASE_URL_PRO
		headers = {
			"Authorization": f"DeepL-Auth-Key {apiKey}",
			"Content-Type": "application/json",
			"User-Agent": "NVDA-ModernTranslate-Plugin/1.0",
		}
		lines = [line for line in text.splitlines() if line.strip()] or [text]
		payload = {"text": lines, "target_lang": langTo.upper()}

		if langFrom != "auto":
			payload["source_lang"] = langFrom.upper()
		if config.get("context", "").strip():
			payload["context"] = config["context"]

		splitMap = {"on": "1", "off": "0", "nonewlines": "nonewlines"}
		payload["split_sentences"] = splitMap.get(config.get("splitSentences", "nonewlines"))

		if config.get("preserveFormatting"):
			payload["preserve_formatting"] = True

		formality = config.get("formality")
		if formality and formality != "default":
			if langTo.upper() in self.FORMALITY_SUPPORTED_LANGUAGES:
				payload["formality"] = formality
			else:
				log.warning(f"DeepL: Formality '{formality}' not supported for target '{langTo}'. Ignoring.")

		modelType = config.get("modelType")
		if modelType and modelType != "latency_optimized":
			payload["model_type"] = modelType

		return {
			"method": "POST",
			"url": baseUrl,
			"headers": headers,
			"data": json.dumps(payload).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict:
		data = json.loads(responseBody)
		if "message" in data:
			raise ApiResponseError(data["message"])
		if not data.get("translations"):
			raise ApiResponseError(_("Invalid API response or no translation result included."))

		translatedText = "\n".join(item.get("text", "") for item in data["translations"])
		detectedLang = (
			data["translations"][0].get("detected_source_language") if data["translations"] else None
		)

		return {"translation": translatedText, "langDetected": detectedLang}
