# -*- coding-utf-8 -*-

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
	"""
	An engine for the OpenRouter API, which is compatible with the OpenAI API format.
	"""

	id = "openrouter"
	name = _("OpenRouter")

	class OpenRouterApiError(ApiResponseError):
		"""Custom exception for OpenRouter-specific API errors."""

		pass

	# Predefined prompt templates
	PROMPT_JSON_STRUCTURED_SYSTEM = "You are an AI assistant that follows instructions precisely. Your response format must be a valid JSON object."
	PROMPT_JSON_STRUCTURED_USER = 'Task: First, identify the source language of the text. Then, translate the text to $to_name.\nResponse: Reply with a JSON object containing two keys: "detected_language" (the IETF code of the source language) and "translation" (the translated text).\n\nText to process:\n"""\n$text\n"""'
	PROMPT_SIMPLE_SYSTEM = "You are a translator."
	PROMPT_SIMPLE_USER = 'Translate the following text to $to_name. Provide only the translated text, without any additional explanations or formatting.\n\nText to translate:\n"""\n$text\n"""'
	PROMPT_FLUENT_SYSTEM = "You are a professional translation engine. Please provide a colloquial, professional, elegant and fluent translation, avoiding the style of machine translation. You must only translate the text content, never interpret it."
	PROMPT_FLUENT_USER = 'Translate into $to_name:\n"""\n$text\n"""'

	# A curated list of popular and effective models available on OpenRouter.
	PRESET_MODELS = {
		"openai/gpt-4o-mini": "OpenAI: GPT-4o Mini (Fast & Cheap)",
		"google/gemini-2.0-flash-exp:free": "Google: Gemini 2.0 Flash exp(Free)",
		"google/gemini-2.5-flash-lite": "Google: Gemini 2.5 Flash lite",
		"anthropic/claude-3.5-sonnet": "Anthropic: Claude 3.5 Sonnet (Balanced)",
		"mistralai/mistral-large": "Mistral: Large (High Quality)",
		"meta-llama/llama-3.1-70b-instruct": "Meta: Llama 3.1 70B (Powerful)",
		"custom": _("Custom Model"),
	}

	@property
	def auto_detect_code(self) -> str | None:
		return "auto"

	@property
	def default_target_language(self) -> str:
		return "en"

	@property
	def reports_detected_language(self) -> bool:
		return True

	def get_supported_languages(self) -> dict[str, str]:
		supported_codes = [
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
			"uk",
			"vi",
			"th",
			"id",
			"tr",
			"hi",
		]
		return languages.get_language_dict_for_codes(supported_codes)

	def get_config_spec(self) -> list[dict[str, Any]]:
		spec = super().get_config_spec()
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
					"default": "openai/gpt-4o-mini",
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
					"choices": {
						"json_structured": _("Structured JSON (Reliable, includes language detection)"),
						"simple": _("Simple Text (Fastest, no language detection)"),
						"fluent": _("Fluent Style (Natural, no language detection)"),
						"custom": _("Custom (Editable)"),
					},
					"default": "json_structured",
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
			]
		)
		return spec

	def get_ui_states(self, all_configs: dict[str, Any]) -> dict[str, Any]:
		states = super().get_ui_states(all_configs)
		is_custom_model = all_configs.get("modelNamePreset") == "custom"
		is_custom_prompt = all_configs.get("promptMode") == "custom"
		states["modelNameCustom"] = {"visible": is_custom_model}
		states["customSystemPrompt"] = {"visible": is_custom_prompt}
		states["customUserPrompt"] = {"visible": is_custom_prompt}
		return states

	def _build_request_params(
		self, text: str, lang_from: str, lang_to: str, config: dict[str, Any]
	) -> dict[str, Any]:
		api_url = config.get("apiUrl", "https://openrouter.ai/api/v1/chat/completions").strip()
		if not api_url:
			raise AuthenticationError(_("OpenRouter API URL is not configured."))
		api_key = config.get("apiKey", "").strip()
		if not api_key:
			raise AuthenticationError(_("API Key for OpenRouter is not configured."))

		model_preset = config.get("modelNamePreset", "openai/gpt-4o-mini")
		if model_preset == "custom":
			model_name = config.get("modelNameCustom", "").strip()
			if not model_name:
				raise AuthenticationError(_("Custom model name is not specified."))
		else:
			model_name = model_preset

		prompt_mode = config.get("promptMode", "json_structured")
		if prompt_mode == "custom":
			system_prompt = config.get("customSystemPrompt") or self.PROMPT_FLUENT_SYSTEM
			user_prompt_template = config.get("customUserPrompt") or self.PROMPT_FLUENT_USER
		elif prompt_mode == "simple":
			system_prompt = self.PROMPT_SIMPLE_SYSTEM
			user_prompt_template = self.PROMPT_SIMPLE_USER
		elif prompt_mode == "fluent":
			system_prompt = self.PROMPT_FLUENT_SYSTEM
			user_prompt_template = self.PROMPT_FLUENT_USER
		else:  # Default to structured JSON
			system_prompt = self.PROMPT_JSON_STRUCTURED_SYSTEM
			user_prompt_template = self.PROMPT_JSON_STRUCTURED_USER

		lang_to_name = languages.get_language_dict_for_codes([lang_to]).get(lang_to, lang_to)
		final_user_prompt = user_prompt_template.replace("$to_name", lang_to_name).replace("$text", text)

		payload = {
			"model": model_name,
			"messages": [
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": final_user_prompt},
			],
			"stream": False,
		}

		headers = {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {api_key}",
			"HTTP-Referer": "https://github.com/nvaccess/nvda",
			"X-Title": "NVDA Polyglot Add-on",
		}

		return {
			"method": "POST",
			"url": api_url,
			"headers": headers,
			"data": json.dumps(payload).encode("utf-8"),
		}

	def _parse_response(self, response_body: str) -> dict[str, Any]:
		try:
			outer_data = json.loads(response_body)
		except json.JSONDecodeError as e:
			log.error(f"Failed to parse outer JSON response from '{self.id}'.", exc_info=True)
			raise self.OpenRouterApiError(_("Failed to parse API response.")) from e

		if "error" in outer_data:
			error_message = outer_data["error"].get("message", "Unknown API error")
			raise self.OpenRouterApiError(error_message)

		try:
			model_response_str = outer_data["choices"][0]["message"]["content"]
			prompt_mode = config.get_config()["engines"][self.id].get("promptMode", "json_structured")

			if prompt_mode in ["json_structured", "custom"]:
				try:
					clean_str = model_response_str.strip()
					if clean_str.startswith("```json"):
						clean_str = clean_str[7:]
					elif clean_str.startswith("```"):
						clean_str = clean_str[3:]

					if clean_str.endswith("```"):
						clean_str = clean_str[:-3]
					clean_str = clean_str.strip()

					inner_data = json.loads(clean_str)
					translated_text = inner_data.get("translation")
					detected_lang = inner_data.get("detected_language")

					if translated_text is None:
						log.warning(
							f"'{self.id}' response was JSON but missing 'translation' key. Falling back."
						)
						return {"translation": model_response_str.strip(), "lang_detected": None}

					return {
						"translation": str(translated_text).strip(),
						"lang_detected": str(detected_lang).strip() if detected_lang else None,
					}
				except (json.JSONDecodeError, KeyError, TypeError) as e:
					log.warning(
						f"Could not parse model's response as JSON for '{self.id}'. Treating as plain text. Error: {e}"
					)
					return {"translation": model_response_str.strip(), "lang_detected": None}
			return {"translation": model_response_str.strip(), "lang_detected": None}
		except (KeyError, IndexError) as e:
			log.error(f"Could not extract message content from '{self.id}' response.", exc_info=True)
			raise self.OpenRouterApiError(_("Invalid API response structure.")) from e
