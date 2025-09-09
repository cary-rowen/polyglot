# -*- coding: utf-8 -*-

import importlib
import inspect
import pkgutil

from logHandler import log

from . import engines
from .engine import TranslationEngine

_engine_instances: list[TranslationEngine] | None = None


def _scan_and_load_engines() -> None:
	global _engine_instances
	log.debug("First-time scan: Loading translation engines...")
	_engine_instances = []
	for _, name, _ in pkgutil.iter_modules(engines.__path__, engines.__name__ + "."):
		try:
			module = importlib.import_module(name)
			for _, member_obj in inspect.getmembers(module):
				if (
					inspect.isclass(member_obj)
					and issubclass(member_obj, TranslationEngine)
					and member_obj is not TranslationEngine
					and not inspect.isabstract(member_obj)
				):
					instance: TranslationEngine = member_obj()
					_engine_instances.append(instance)
					log.debug(f"Successfully loaded engine: {instance.name} (ID: {instance.id})")
		except Exception:
			log.error(f"Failed to load engine module '{name}'", exc_info=True)
	if not _engine_instances:
		log.warning(
			"""No translation engines were loaded successfully. This may be due to errors in the engine modules or an issue with the add-on installation. Translation functionality will not be available."""
		)
	assert _engine_instances is not None
	_engine_instances.sort(key=lambda e: e.name)


def get_all_engines() -> list[TranslationEngine]:
	global _engine_instances
	if _engine_instances is None:
		_scan_and_load_engines()
	assert _engine_instances is not None
	return _engine_instances


def get_engine_by_id(engine_id: str) -> TranslationEngine:
	all_engines = get_all_engines()
	for engine in all_engines:
		if engine.id == engine_id:
			return engine
	raise ValueError(f"Engine with ID '{engine_id}' not found.")
