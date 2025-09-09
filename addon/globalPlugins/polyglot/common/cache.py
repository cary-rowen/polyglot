# -*- coding: utf-8 -*-

import hashlib
import json
import os
from typing import Any, Self  # Self is available in Python 3.11+

import globalVars
from logHandler import log


class TranslationCache:
	"""Provides a simple, persistent cache for translation results. Implemented as a singleton."""

	_instance: Self | None = None

	cache_path: str
	max_size: int
	_cache: dict[str, str]
	_initialized: bool

	def __new__(cls, *args: Any, **kwargs: Any) -> Self:
		if not cls._instance:
			cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self, filename: str = "translation_cache.json", max_size: int = 500) -> None:
		super().__init__()
		if hasattr(self, "_initialized"):
			return
		config_path = globalVars.appArgs.configPath
		self.cache_path = os.path.join(config_path, filename)
		self.max_size = max_size
		self._cache = self._load()
		self._initialized = True
		log.info(f"TranslationCache initialized. Path: {self.cache_path}, Initial items: {len(self._cache)}")

	def _load(self) -> dict[str, str]:
		try:
			if os.path.exists(self.cache_path):
				with open(self.cache_path, "r", encoding="utf-8") as f:
					loaded_data = json.load(f)
					if isinstance(loaded_data, dict):
						return loaded_data
		except (IOError, json.JSONDecodeError):
			log.error(f"Failed to load translation cache from {self.cache_path}", exc_info=True)
			pass
		return {}

	def _save(self) -> None:
		try:
			if len(self._cache) > self.max_size:
				keys_to_delete = list(self._cache.keys())[: len(self._cache) - self.max_size]
				for key in keys_to_delete:
					del self._cache[key]
				log.info(f"Cache size exceeded {self.max_size}. Pruned {len(keys_to_delete)} items.")
			with open(self.cache_path, "w", encoding="utf-8") as f:
				json.dump(self._cache, f, ensure_ascii=False, indent=2)
		except IOError:
			log.error(f"Failed to save translation cache to {self.cache_path}", exc_info=True)
			pass

	def build_key(self, lang_from: str, lang_to: str, text: str) -> str:
		# Normalize text by stripping whitespace to improve the cache hit rate.
		normalized_text = text.strip()
		key_string = f"{lang_from}:{lang_to}:{normalized_text}"
		return hashlib.md5(key_string.encode("utf-8")).hexdigest()

	def get(self, key: str) -> str | None:
		return self._cache.get(key)

	def set(self, key: str, value: str) -> None:
		self._cache[key] = value
		self._save()

	def get_item_count(self) -> int:
		return len(self._cache)

	def clear(self) -> None:
		log.info("Translation cache cleared.")
		self._cache = {}
		self._save()
