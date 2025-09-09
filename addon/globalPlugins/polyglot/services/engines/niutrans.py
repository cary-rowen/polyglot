# --- FILE: globalPlugins/polyglot/services/engines/niutrans.py ---
# -*- coding: utf-8 -*-

import json
import hashlib
import time
import urllib.parse
from typing import Any, Dict

import addonHandler
from logHandler import log

from ...common import languages
from ..engine import BaseHttpEngine
from ...common.exceptions import ApiResponseError, AuthenticationError, EngineError, ResponseParsingError

addonHandler.initTranslation()


class NiutransApiError(ApiResponseError):
	"""Custom exception for Niutrans v2.0-specific API errors."""

	pass


class NiutransTranslateEngine(BaseHttpEngine):
	"""
	An engine for the Niutrans v2.0 API.
	It supports 'auto' for the source language but does not report the detected language.
	It also supports an optional bilingual alignment mode with configurable output order.
	"""

	id = "niutrans"
	name = _("Niutrans")

	API_URL_STANDARD = "https://api.niutrans.com/v2/text/translate"
	API_URL_BILINGUAL = "https://api.niutrans.com/v2/text/translate/bilingual"

	ERROR_CODES = {
		"404": _("Request address does not exist"),
		"10001": _("Request is too frequent, exceeding QPS limit"),
		"10003": _("Request string length exceeds the limit"),
		"10005": _("Source language encoding is not UTF-8"),
		"13001": _("Insufficient character allowance or no access permission"),
		"13003": _("Content filtering exception"),
		"13005": _("Source and target languages are the same"),
		"13007": _("Language not supported"),
		"13008": _("Request processing timeout"),
		"20001": _("Authentication failed"),
		"20002": _("Parameters do not conform to specifications"),
		"20003": _(
			"Parameter validation exception (e.g., from/to/srcText/appId/authStr/timestamp cannot be empty)"
		),
		"000000": _("Incorrect request parameters"),
		"000001": _("Unsupported parameter passing method"),
	}

	@property
	def auto_detect_code(self) -> str | None:
		return "auto"

	@property
	def default_target_language(self) -> str:
		return "en"

	@property
	def reports_detected_language(self) -> bool:
		return False

	def get_supported_languages(self) -> dict:
		supported_codes = [
			"auto",
			"zh",
			"en",
			"sq",
			"ar",
			"am",
			"acu",
		]
		return languages.get_language_dict_for_codes(supported_codes)

	def get_config_spec(self) -> list[dict]:
		spec = super().get_config_spec()
		spec.extend(
			[
				{"id": "appId", "label": _("App ID"), "type": "text", "default": ""},
				{"id": "apikey", "label": _("API Key (for signing)"), "type": "password", "default": ""},
				{
					"id": "enableBilingual",
					"label": _("Enable bilingual alignment mode"),
					"type": "checkbox",
					"default": False,
				},
				# Add a choice for the bilingual output order.
				{
					"id": "bilingualOrder",
					"label": _("Bilingual output order:"),
					"type": "choice",
					"choices": {
						"src_first": _("Source -> Target"),
						"tgt_first": _("Target -> Source"),
					},
					"default": "src_first",
				},
			]
		)
		return spec

	def get_ui_states(self, all_configs: Dict[str, Any]) -> Dict[str, Any]:
		"""Controls the visibility of the bilingual order choice based on the checkbox."""
		states = super().get_ui_states(all_configs)
		is_bilingual_enabled = all_configs.get("enableBilingual", False)
		# The bilingual order dropdown is only visible if bilingual mode is enabled.
		states["bilingualOrder"] = {"visible": is_bilingual_enabled}
		return states

	def _generate_auth_str(self, params: dict, apikey: str) -> str:
		"""Generates the authentication signature (authStr) as required by the v2.0 API."""
		params_with_apikey = params.copy()
		params_with_apikey["apikey"] = apikey

		sorted_params = sorted(params_with_apikey.items(), key=lambda x: x[0])

		param_str = "&".join([f"{key}={value}" for key, value in sorted_params])
		log.debug(f"Niutrans signing string: {param_str}")

		md5 = hashlib.md5()
		md5.update(param_str.encode("utf-8"))
		auth_str = md5.hexdigest()
		log.debug(f"Niutrans generated authStr: {auth_str}")

		return auth_str

	def _build_request_params(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
		"""Builds the request dictionary for the Niutrans v2.0 API call."""
		app_id = config.get("appId", "").strip()
		api_key = config.get("apikey", "").strip()
		if not app_id or not api_key:
			raise AuthenticationError(_("App ID and API Key for Niutrans must be configured."))

		use_bilingual_mode = config.get("enableBilingual", False)
		url = self.API_URL_BILINGUAL if use_bilingual_mode else self.API_URL_STANDARD

		timestamp = str(int(time.time()))
		params_for_signing = {
			"from": lang_from,
			"to": lang_to,
			"appId": app_id,
			"srcText": text,
			"timestamp": timestamp,
		}

		auth_str = self._generate_auth_str(params_for_signing, api_key)

		final_payload = params_for_signing.copy()
		final_payload["authStr"] = auth_str

		return {
			"method": "POST",
			"url": url,
			"headers": {"Content-Type": "application/x-www-form-urlencoded"},
			"data": urllib.parse.urlencode(final_payload).encode("utf-8"),
		}

	def translate(self, text: str, lang_from: str, lang_to: str, config: dict) -> dict:
		"""Overrides the base translate method to pass the config to the response parser."""
		try:
			params = self._build_request_params(text, lang_from, lang_to, config)
			log.debug(f"Engine '{self.id}' built request params: {params.get('method')} {params.get('url')}")

			proxy_mode = config.get("proxyMode", "system")
			proxies_dict = None
			if proxy_mode == "none":
				proxies_dict = {"http": None, "https": None}
			timeout_int = int(config.get("timeout", "15"))

			from ...common.network import send_request

			response_body = send_request(
				method=params.get("method", "GET"),
				url=params["url"],
				headers=params.get("headers"),
				data=params.get("data"),
				timeout=timeout_int,
				proxies=proxies_dict,
			)
			log.debug(f"Engine '{self.id}' raw response: {response_body}")
			return self._parse_response(response_body, config)
		except json.JSONDecodeError as e:
			log.error(f"Failed to parse JSON response from '{self.id}'.", exc_info=True)
			raise ResponseParsingError(_("Failed to parse response from translation service.")) from e
		except EngineError:
			raise
		except Exception as e:
			log.error(f"An unexpected error occurred in '{self.id}' engine.", exc_info=True)
			raise EngineError(_("An unknown error occurred during translation.")) from e

	def _parse_response(self, response_body: str, config: dict) -> dict:
		"""Parses the JSON response from the Niutrans v2.0 API."""
		try:
			data = json.loads(response_body)
		except json.JSONDecodeError:
			raise NiutransApiError(_("Failed to parse API response. Response was not valid JSON."))

		if "errorCode" in data:
			error_code = data.get("errorCode")
			error_msg = self.ERROR_CODES.get(error_code, data.get("errorMsg", "Unknown API error"))
			raise NiutransApiError(f"{error_msg} (Code: {error_code})")

		use_bilingual_mode = config.get("enableBilingual", False)

		if use_bilingual_mode:
			align_data = data.get("align")
			if align_data:
				bilingual_order = config.get("bilingualOrder", "src_first")
				bilingual_pairs = []
				for para_key in sorted(align_data.keys()):
					paragraph = align_data[para_key]
					if not isinstance(paragraph, dict):
						continue
					for sent_key in sorted(paragraph.keys()):
						sentence_pair = paragraph[sent_key]
						src_text = sentence_pair.get("src", "")
						tgt_text = sentence_pair.get("tgt", "")
						# Conditionally format the output based on the user's choice.
						if bilingual_order == "tgt_first":
							bilingual_pairs.append(f"{tgt_text}\n{src_text}")
						else:  # Default to source first.
							bilingual_pairs.append(f"{src_text}\n{tgt_text}")

				final_text = "\n\n".join(bilingual_pairs)
				return {"translation": final_text.strip(), "lang_detected": None}
			else:
				log.warning("Bilingual mode enabled, but 'align' field was not found in the response.")
				translated_text = data.get("tgtText", "")
				return {"translation": translated_text.strip(), "lang_detected": None}

		translated_text = data.get("tgtText")
		if translated_text is not None:
			return {"translation": translated_text.strip(), "lang_detected": None}
		else:
			log.error(f"Niutrans response missing 'tgtText'. Raw response: {response_body}")
			raise NiutransApiError(_("Invalid API response or no translation result included."))
