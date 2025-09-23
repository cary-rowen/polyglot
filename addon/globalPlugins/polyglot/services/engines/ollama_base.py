# -*- coding: utf-8 -*-

import json
from typing import Any

import addonHandler
from logHandler import log

from ...common import languages
from ...common.exceptions import ApiResponseError, AuthenticationError
from ..engine import BaseHttpEngine

addonHandler.initTranslation()


class OllamaApiError(ApiResponseError):
	"""Custom exception for Ollama-specific API errors."""

	pass


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
	def auto_detect_code(self) -> str | None:
		return "auto"

	@property
	def default_target_language(self) -> str:
		return "en"

	@property
	def reports_detected_language(self) -> bool:
		return True

	def get_supported_languages(self) -> dict:
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
		]
		return languages.get_language_dict_for_codes(supported_codes)

	def get_config_spec(self) -> list[dict]:
		spec = super().get_config_spec()
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
			]
		)
		return spec

	def get_ui_states(self, all_configs: dict[str, Any]) -> dict[str, Any]:
		states = super().get_ui_states(all_configs)
		prompt_mode = all_configs.get("promptMode")
		is_custom_mode = prompt_mode == "custom"
		states["customSystemPrompt"] = {"visible": is_custom_mode}
		states["customUserPrompt"] = {"visible": is_custom_mode}
		return states

	def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
		api_url = config.get("apiUrl", "").strip()
		model_name = config.get("modelName", "").strip()
		if not api_url or not model_name:
			raise AuthenticationError(_("Ollama API URL and Model Name are required."))

		prompt_mode = config.get("promptMode", "json_concise")

		system_prompt = ""
		user_prompt_template = ""

		if prompt_mode == "custom":
			system_prompt = config.get("customSystemPrompt") or self.PROMPT_FLUENT_SYSTEM
			user_prompt_template = config.get("customUserPrompt") or self.PROMPT_FLUENT_USER
		elif prompt_mode == "simple":
			system_prompt = self.PROMPT_SIMPLE_SYSTEM
			user_prompt_template = self.PROMPT_SIMPLE_USER
		elif prompt_mode == "json_structured":
			system_prompt = self.PROMPT_JSON_STRUCTURED_SYSTEM
			user_prompt_template = self.PROMPT_JSON_STRUCTURED_USER
		elif prompt_mode == "fluent":
			system_prompt = self.PROMPT_FLUENT_SYSTEM
			user_prompt_template = self.PROMPT_FLUENT_USER
		else:  # Default to json_concise
			system_prompt = self.PROMPT_JSON_CONCISE_SYSTEM
			user_prompt_template = self.PROMPT_JSON_CONCISE_USER

		api_key = config.get("apiKey", "").strip()
		lang_to_name = languages.get_language_dict_for_codes([lang_to]).get(lang_to, lang_to)

		final_user_prompt = user_prompt_template.replace("$to_name", lang_to_name).replace("$text", text)

		payload = {
			"model": model_name,
			"system": system_prompt,
			"prompt": final_user_prompt,
			"stream": False,
		}

		headers = {"Content-Type": "application/json"}
		if api_key:
			headers["Authorization"] = f"Bearer {api_key}"

		return {
			"method": "POST",
			"url": api_url,
			"headers": headers,
			"data": json.dumps(payload).encode("utf-8"),
		}

	def _parse_response(self, response_body: str) -> dict:
		outer_data = json.loads(response_body)

		if "error" in outer_data:
			raise OllamaApiError(outer_data["error"])

		model_response_str = outer_data.get("response")

		if not model_response_str:
			raise OllamaApiError(_("API response did not contain a 'response' field."))

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

			if translated_text is not None:
				return {
					"translation": str(translated_text).strip(),
					"lang_detected": str(detected_lang).strip() if detected_lang else None,
				}

			return {"translation": clean_str, "lang_detected": None}

		except (json.JSONDecodeError, KeyError, TypeError):
			log.warning(
				f"Could not parse model's response as JSON. Treating as plain text. Response: {model_response_str}"
			)
			return {"translation": model_response_str.strip(), "lang_detected": None}
