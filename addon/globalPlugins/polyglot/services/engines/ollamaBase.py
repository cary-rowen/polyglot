# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
from typing import Any

import addonHandler
from logHandler import log

from ...common import languages
from ...common.exceptions import ApiResponseError, AuthenticationError
from ..engine import BaseHttpEngine

addonHandler.initTranslation()


class OllamaBaseEngine(BaseHttpEngine):
	"""
	This is the BASE implementation for all Ollama engines.
	It contains all the core logic but is NOT loaded as a usable engine itself.
	To create a usable engine, inherit from this class and override id and name.
	"""

	# --- Predefined Prompt Templates (used at runtime, never in configspec) ---
	PROMPT_SIMPLE_SYSTEM = "You are a translator."
	PROMPT_SIMPLE_USER = (
		'Translate to $to_name, providing only the translated text.\n\nText to translate:\n"""\n$text\n"""'
	)
	PROMPT_JSON_CONCISE_SYSTEM = "You are a translation API that responds in JSON."
	PROMPT_JSON_CONCISE_USER = "Translate the text to $to_name and identify the source language. Respond with two keys: 'detected_language' (IETF code) and 'translation' (the text).\n\n$text"
	PROMPT_JSON_STRUCTURED_SYSTEM = "You are an AI assistant that follows instructions precisely. Your response format must be a valid JSON object."
	PROMPT_JSON_STRUCTURED_USER = 'Task: Identify the source language of the text, then translate it to $to_name.\nResponse: Reply with a JSON object containing two keys: \'detected_language\' and \'translation\'.\n\nText to process:\n"""\n$text\n"""'
	PROMPT_FLUENT_SYSTEM = "You are a professional translation engine. Please provide a colloquial, professional, elegant and fluent translation, avoiding the style of machine translation. You must only translate the text content, never interpret it."
	PROMPT_FLUENT_USER = 'Translate into $to_name:\n"""\n$text\n"""'

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "en"

	@property
	def maxRequestLength(self) -> int:
		return 512

	@property
	def doesReportDetectedLanguage(self) -> bool:
		return True

	def getSupportedLanguages(self) -> dict:
		supportedCodes = [
			"auto",
			"en",
			"zh-CN",
			"zh-TW",
			"ja",
			"ko",
			"fr",
			"de",
			"es",
			"ru",
			"pt",
			"it",
			"nl",
			"pl",
			"sv",
			"ar",
			"he",
		]
		return languages.getLanguageDictForCodes(supportedCodes)

	def getConfigSpec(self) -> list[dict]:
		spec = super().getConfigSpec()
		spec.extend(
			[
				{
					"id": "apiUrl",
					"label": _("API URL"),
					"type": "text",
					"default": "http://family.zxrjy.net:11434/api/generate",
				},
				{"id": "modelName", "label": _("Model Name"), "type": "text", "default": "gemma3:4b"},
				{"id": "apiKey", "label": _("API Key (optional)"), "type": "password", "default": ""},
				{
					"id": "promptMode",
					"label": _("Prompt Template:"),
					"type": "choice",
					"choices": {
						"simple": _("Simple (No JSON)"),
						"json_concise": _("Concise JSON (Recommended)"),
						"json_structured": _("Structured JSON (Reliable)"),
						"fluent": _("Fluent Style (No JSON)"),
						"custom": _("Custom (Editable)"),
					},
					"default": "json_concise",
				},
				{
					"id": "customSystemPrompt",
					"label": _("Custom System Prompt (Role):"),
					"type": "text",
					"default": "You are a professional translation engine.",
				},
				{
					"id": "customUserPrompt",
					"label": _("Custom User Prompt (Task):"),
					"type": "text",
					"default": "Translate to $to_name: $text",
				},
			],
		)
		return spec

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, Any]:
		states = super().getUiStates(allConfigs)
		promptMode = allConfigs.get("promptMode")
		isCustomMode = promptMode == "custom"
		states["customSystemPrompt"] = {"visible": isCustomMode}
		states["customUserPrompt"] = {"visible": isCustomMode}
		return states

	def _buildRequestParams(self, text: str, langFrom: str, langTo: str, config: dict) -> dict:
		apiUrl = config.get("apiUrl", "").strip()
		modelName = config.get("modelName", "").strip()
		if not apiUrl or not modelName:
			raise AuthenticationError(_("Ollama API URL and Model Name are required."))

		promptMode = config.get("promptMode", "json_concise")

		systemPrompt = ""
		userPromptTemplate = ""

		if promptMode == "custom":
			systemPrompt = config.get("customSystemPrompt") or self.PROMPT_FLUENT_SYSTEM
			userPromptTemplate = config.get("customUserPrompt") or self.PROMPT_FLUENT_USER
		elif promptMode == "simple":
			systemPrompt = self.PROMPT_SIMPLE_SYSTEM
			userPromptTemplate = self.PROMPT_SIMPLE_USER
		elif promptMode == "json_structured":
			systemPrompt = self.PROMPT_JSON_STRUCTURED_SYSTEM
			userPromptTemplate = self.PROMPT_JSON_STRUCTURED_USER
		elif promptMode == "fluent":
			systemPrompt = self.PROMPT_FLUENT_SYSTEM
			userPromptTemplate = self.PROMPT_FLUENT_USER
		else:  # Default to json_concise
			systemPrompt = self.PROMPT_JSON_CONCISE_SYSTEM
			userPromptTemplate = self.PROMPT_JSON_CONCISE_USER

		apiKey = config.get("apiKey", "").strip()
		langToName = languages.getLanguageDictForCodes([langTo]).get(langTo, langTo)

		finalUserPrompt = userPromptTemplate.replace("$to_name", langToName).replace("$text", text)

		payload = {
			"model": modelName,
			"system": systemPrompt,
			"prompt": finalUserPrompt,
			"stream": False,
		}

		headers = {"Content-Type": "application/json"}
		if apiKey:
			headers["Authorization"] = f"Bearer {apiKey}"

		return {
			"method": "POST",
			"url": apiUrl,
			"headers": headers,
			"data": json.dumps(payload).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict:
		outerData = json.loads(responseBody)

		if "error" in outerData:
			raise ApiResponseError(outerData["error"])

		modelResponseStr = outerData.get("response")

		if not modelResponseStr:
			raise ApiResponseError(_("API response did not contain a 'response' field."))

		try:
			cleanStr = modelResponseStr.strip()
			if cleanStr.startswith("```json"):
				cleanStr = cleanStr[7:]
			elif cleanStr.startswith("```"):
				cleanStr = cleanStr[3:]
			if cleanStr.endswith("```"):
				cleanStr = cleanStr[:-3]

			cleanStr = cleanStr.strip()

			innerData = json.loads(cleanStr)
			translatedText = innerData.get("translation")
			detectedLang = innerData.get("detected_language")

			if translatedText is not None:
				return {
					"translation": str(translatedText).strip(),
					"langDetected": str(detectedLang).strip() if detectedLang else None,
				}

			return {"translation": cleanStr, "langDetected": None}

		except (json.JSONDecodeError, KeyError, TypeError):
			log.warning("Could not parse model response as JSON; treating it as plain text.")
			return {"translation": modelResponseStr.strip(), "langDetected": None}
