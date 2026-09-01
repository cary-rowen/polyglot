# -*- coding: utf-8 -*-

# Copyright (C) 2025-2026 cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import json
from typing import Any

import addonHandler
from logHandler import log

from ...common import config
from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError

addonHandler.initTranslation()


class OpenRouterTranslateEngine(BaseHttpEngine):
	"""An engine for the OpenRouter API, which is compatible with the OpenAI API format."""

	id = "openrouter"
	name = _("OpenRouter")

	# Predefined prompt templates
	PROMPT_JSON_STRUCTURED_SYSTEM = "You are an AI assistant that follows instructions precisely. Your response format must be a valid JSON object."
	PROMPT_JSON_STRUCTURED_USER = 'Task: First, identify the source language of the text. Then, translate the text to $to_name.\nResponse: Reply with a JSON object containing two keys: "detected_language" (the IETF code of the source language) and "translation" (the translated text).\n\nText to process:\n"""\n$text\n"""'
	PROMPT_SIMPLE_SYSTEM = "You are a translator."
	PROMPT_SIMPLE_USER = 'Translate the following text to $to_name. Provide only the translated text, without any additional explanations or formatting.\n\nText to translate:\n"""\n$text\n"""'
	PROMPT_FLUENT_SYSTEM = "You are a professional translation engine. Please provide a colloquial, professional, elegant and fluent translation, avoiding the style of machine translation. You must only translate the text content, never interpret it."
	PROMPT_FLUENT_USER = 'Translate into $to_name:\n"""\n$text\n"""'

	# A curated list of models available on OpenRouter, ordered with the models best suited to
	# real-time translation first. Translation-specialised models answer faster and cost far less
	# than the general-purpose models below them, so they are offered first and used by default.
	PRESET_MODELS = {
		# Translators: An OpenRouter model name shown in the model selection list.
		"tencent/hy-mt2-30b-a3b": _("Tencent: Hy-MT2-30B-A3B (Translation specialist, recommended)"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"tencent/hy-mt2-7b": _("Tencent: Hy-MT2-7B (Translation specialist, fastest)"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"tencent/hy-mt2-1.8b": _("Tencent: Hy-MT2-1.8B (Translation specialist, cheapest)"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"inception/mercury-2": _("Inception: Mercury 2 (Fast, keeps language detection)"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"google/gemini-3.5-flash-lite": _("Google: Gemini 3.5 Flash Lite"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"google/gemini-3.1-flash-lite": _("Google: Gemini 3.1 Flash Lite"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"google/gemini-2.5-flash-lite": _("Google: Gemini 2.5 Flash Lite"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"openai/gpt-5-mini": _("OpenAI: GPT-5 Mini"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"anthropic/claude-haiku-4.5": _("Anthropic: Claude Haiku 4.5"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"openai/gpt-4o-mini": _("OpenAI: GPT-4o Mini"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"mistralai/mistral-large": _("Mistral: Large (High Quality)"),
		# Translators: An OpenRouter model name shown in the model selection list.
		"meta-llama/llama-3.1-70b-instruct": _("Meta: Llama 3.1 70B (Powerful)"),
		# Translators: The option for entering a custom OpenRouter model name.
		"custom": _("Custom Model"),
	}

	DEFAULT_MODEL = "tencent/hy-mt2-30b-a3b"

	# Presets that OpenRouter has retired since they were added here, mapped to their closest
	# current model. Without this, a configuration written before this change keeps asking for a
	# model that no longer exists and every translation fails.
	RETIRED_MODEL_REPLACEMENTS = {
		"google/gemini-2.0-flash-exp:free": "google/gemini-2.5-flash-lite",
		"anthropic/claude-3.5-sonnet": "anthropic/claude-haiku-4.5",
	}

	# Translation-specialised models return the translated text and nothing else. They cannot
	# follow the structured-JSON prompt, so that prompt is hidden for them and any stored
	# selection of it is treated as the simple prompt instead.
	TRANSLATION_ONLY_MODELS = frozenset(
		{
			"tencent/hy-mt2-30b-a3b",
			"tencent/hy-mt2-7b",
			"tencent/hy-mt2-1.8b",
		},
	)

	@property
	def maxRequestLength(self) -> int:
		"""
		Set to 4000 to maintain a safe token window and prevent timeout issues
		with large documents across various LLM providers.
		"""
		return 4000

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def defaultTargetLanguage(self) -> str:
		return "en"

	@property
	def doesReportDetectedLanguage(self) -> bool:
		return True

	def getSupportedLanguages(self) -> dict[str, str]:
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
			"ar",
			"he",
			"uk",
			"vi",
			"th",
			"id",
			"tr",
			"hi",
		]
		return languages.getLanguageDictForCodes(supportedCodes)

	def _getSelectedModel(self, engineConfig: dict[str, Any]) -> str:
		"""Return the model name currently configured, resolving the custom-model entry."""
		modelPreset = str(engineConfig.get("modelNamePreset", self.DEFAULT_MODEL))
		if modelPreset == "custom":
			return str(engineConfig.get("modelNameCustom", "")).strip()
		replacement = self.RETIRED_MODEL_REPLACEMENTS.get(modelPreset)
		if replacement:
			log.debug("Model '%s' is retired on OpenRouter; using '%s'.", modelPreset, replacement)
			return replacement
		return modelPreset

	def _supportsStructuredPrompt(self, modelName: str) -> bool:
		"""Return whether the model can answer the structured-JSON prompt."""
		return modelName not in self.TRANSLATION_ONLY_MODELS

	def _getPromptModeChoices(self, modelName: str) -> dict[str, str]:
		"""Return the prompt templates the given model can actually honour."""
		choices: dict[str, str] = {}
		if self._supportsStructuredPrompt(modelName):
			choices["json_structured"] = _("Structured JSON (Reliable, includes language detection)")
		choices["simple"] = _("Simple Text (Fastest, no language detection)")
		choices["fluent"] = _("Fluent Style (Natural, no language detection)")
		choices["custom"] = _("Custom (Editable)")
		return choices

	def _resolvePromptMode(self, modelName: str, promptMode: str) -> str:
		"""
		Return the prompt mode to actually use for the model.

		A configuration written before a translation-specialised model was selected can still
		request the structured-JSON prompt; those models would answer with plain text, so the
		simple prompt is used instead.
		"""
		if promptMode == "json_structured" and not self._supportsStructuredPrompt(modelName):
			return "simple"
		return promptMode

	def getConfigSpec(self) -> list[dict[str, Any]]:
		spec = super().getConfigSpec()
		spec.extend(
			[
				{
					"id": "apiUrl",
					"label": _("API URL"),
					"type": "text",
					"default": "https://openrouter.ai/api/v1/chat/completions",
				},
				{"id": "apiKey", "label": _("API Key"), "type": "password", "default": ""},
				{
					"id": "modelNamePreset",
					"label": _("Model:"),
					"type": "choice",
					"choices": self.PRESET_MODELS,
					"default": self.DEFAULT_MODEL,
				},
				{
					"id": "modelNameCustom",
					"label": _("Custom Model Name:"),
					"type": "text",
					"default": "",
				},
				{
					"id": "promptMode",
					"label": _("Prompt Template:"),
					"type": "choice",
					# The list is narrowed to the templates the selected model supports in
					# `getUiStates`; the full list is used here so every stored value stays valid.
					"choices": self._getPromptModeChoices(""),
					# The default model is a translation specialist, which is fastest and most
					# accurate with the simple prompt.
					"default": "simple",
				},
				{
					"id": "customSystemPrompt",
					"label": _("Custom System Prompt (Role):"),
					"type": "text",
					"default": self.PROMPT_FLUENT_SYSTEM.replace("\n", "\\n"),
				},
				{
					"id": "customUserPrompt",
					"label": _("Custom User Prompt (Task):"),
					"type": "text",
					"default": self.PROMPT_FLUENT_USER.replace("\n", "\\n"),
				},
			],
		)
		return spec

	def getUiStates(self, allConfigs: dict[str, Any]) -> dict[str, Any]:
		states = super().getUiStates(allConfigs)
		modelName = self._getSelectedModel(allConfigs)
		promptMode = self._resolvePromptMode(modelName, allConfigs.get("promptMode", "simple"))
		canReportDetectedLanguage = self._supportsStructuredPrompt(modelName) and promptMode in {
			"json_structured",
			"custom",
		}
		isCustomModel = allConfigs.get("modelNamePreset") == "custom"
		isCustomPrompt = allConfigs.get("promptMode") == "custom"
		states["modelNameCustom"] = {"visible": isCustomModel}
		states["customSystemPrompt"] = {"visible": isCustomPrompt}
		states["customUserPrompt"] = {"visible": isCustomPrompt}
		for controlId in ("enableAutoSwap", "swapLanguage"):
			states[controlId]["visible"] &= canReportDetectedLanguage
		# Offer only the prompt templates the selected model can follow. If the structured-JSON
		# template is dropped while it is selected, the control falls back to the simple template.
		states["promptMode"] = {"choices": self._getPromptModeChoices(modelName)}
		return states

	def _buildRequestParams(
		self,
		text: str,
		langFrom: str,
		langTo: str,
		config: dict[str, Any],
	) -> dict[str, Any]:
		apiUrl = config.get("apiUrl", "https://openrouter.ai/api/v1/chat/completions").strip()
		if not apiUrl:
			raise AuthenticationError(_("OpenRouter API URL is not configured."))
		apiKey = config.get("apiKey", "").strip()
		if not apiKey:
			raise AuthenticationError(_("API Key for OpenRouter is not configured."))

		modelName = self._getSelectedModel(config)
		if not modelName:
			raise AuthenticationError(_("Custom model name is not specified."))

		promptMode = self._resolvePromptMode(modelName, config.get("promptMode", "simple"))
		if promptMode == "custom":
			systemPrompt = config.get("customSystemPrompt") or self.PROMPT_FLUENT_SYSTEM
			userPromptTemplate = config.get("customUserPrompt") or self.PROMPT_FLUENT_USER
		elif promptMode == "simple":
			systemPrompt = self.PROMPT_SIMPLE_SYSTEM
			userPromptTemplate = self.PROMPT_SIMPLE_USER
		elif promptMode == "fluent":
			systemPrompt = self.PROMPT_FLUENT_SYSTEM
			userPromptTemplate = self.PROMPT_FLUENT_USER
		else:  # Default to structured JSON
			systemPrompt = self.PROMPT_JSON_STRUCTURED_SYSTEM
			userPromptTemplate = self.PROMPT_JSON_STRUCTURED_USER

		langToName = languages.getLanguageDictForCodes([langTo]).get(langTo, langTo)
		finalUserPrompt = userPromptTemplate.replace("$to_name", langToName).replace("$text", text)

		payload = {
			"model": modelName,
			"messages": [
				{"role": "system", "content": systemPrompt},
				{"role": "user", "content": finalUserPrompt},
			],
			"stream": False,
		}

		headers = {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {apiKey}",
			"HTTP-Referer": "https://github.com/nvaccess/nvda",
			"X-Title": "NVDA Polyglot Add-on",
		}

		return {
			"method": "POST",
			"url": apiUrl,
			"headers": headers,
			"data": json.dumps(payload).encode("utf-8"),
		}

	def _parseResponse(self, responseBody: str) -> dict[str, Any]:
		try:
			outerData = json.loads(responseBody)
		except json.JSONDecodeError:
			log.error(f"Failed to parse outer JSON response from '{self.id}'.", exc_info=True)
			raise ApiResponseError(_("Failed to parse API response.")) from None

		if "error" in outerData:
			errorMessage = outerData["error"].get("message", "Unknown API error")
			raise ApiResponseError(errorMessage)

		try:
			modelResponseStr = outerData["choices"][0]["message"]["content"]
			engineConfig = config.getConfig()["engines"][self.id]
			promptMode = self._resolvePromptMode(
				self._getSelectedModel(engineConfig),
				engineConfig.get("promptMode", "simple"),
			)

			if promptMode in ["json_structured", "custom"]:
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

					if translatedText is None:
						log.warning(
							f"'{self.id}' response was JSON but missing 'translation' key. Falling back.",
						)
						return {"translation": modelResponseStr.strip(), "langDetected": None}

					return {
						"translation": str(translatedText).strip(),
						"langDetected": str(detectedLang).strip() if detectedLang else None,
					}
				except (json.JSONDecodeError, KeyError, TypeError):
					log.warning(
						f"Could not parse model response as JSON for '{self.id}'; treating it as plain text.",
					)
					return {"translation": modelResponseStr.strip(), "langDetected": None}
			return {"translation": modelResponseStr.strip(), "langDetected": None}
		except (KeyError, IndexError):
			log.error(f"Could not extract message content from '{self.id}' response.", exc_info=True)
			raise ApiResponseError(_("Invalid API response structure.")) from None
