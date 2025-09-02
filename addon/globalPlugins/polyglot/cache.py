# -*- coding: utf-8 -*-

import os
import json
import globalVars
import hashlib
from logHandler import log

class TranslationCache:
    """Provides a simple, persistent cache for translation results. Implemented as a singleton."""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, filename="translation_cache.json", max_size=500):
        if hasattr(self, '_initialized'):
            return
        self.cache_path = os.path.join(globalVars.appArgs.configPath, filename)
        self.max_size = max_size
        self._cache = self._load()
        self._initialized = True
        log.info(f"TranslationCache initialized. Path: {self.cache_path}, Initial items: {len(self._cache)}")

    def _load(self):
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            log.error(f"Failed to load translation cache from {self.cache_path}", exc_info=True)
            pass
        return {}

    def _save(self):
        try:
            if len(self._cache) > self.max_size:
                keys_to_delete = list(self._cache.keys())[:len(self._cache) - self.max_size]
                for key in keys_to_delete:
                    del self._cache[key]
                log.info(f"Cache size exceeded {self.max_size}. Pruned {len(keys_to_delete)} items.")

            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except IOError:
            log.error(f"Failed to save translation cache to {self.cache_path}", exc_info=True)
            pass

    def build_key(self, lang_from: str, lang_to: str, text: str) -> str:
        # Normalize text by stripping whitespace to improve the cache hit rate.
        normalized_text = text.strip()
        key_string = f"{lang_from}:{lang_to}:{normalized_text}"
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()

    def get(self, key: str):
        return self._cache.get(key)

    def set(self, key: str, value: str):
        self._cache[key] = value
        self._save()

    def get_item_count(self) -> int:
        return len(self._cache)

    def clear(self):
        log.info("Translation cache cleared.")
        self._cache = {}
        self._save()