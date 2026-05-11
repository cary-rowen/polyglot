# -*- coding: utf-8 -*-

import importlib
import inspect
import pkgutil
from typing import Any

from logHandler import log

from . import engines
from .engine import TranslationEngine

_engineInstances: list[TranslationEngine] | None = None


def _scanAndLoadEngines() -> None:
	global _engineInstances
	log.debug("First-time scan: Loading translation engines...")
	_engineInstances = []
	for _, name, _ in pkgutil.iter_modules(engines.__path__, engines.__name__ + "."):
		try:
			module = importlib.import_module(name)
			for _, memberObj in inspect.getmembers(module):
				if (
					inspect.isclass(memberObj)
					and issubclass(memberObj, TranslationEngine)
					and memberObj is not TranslationEngine
					and not inspect.isabstract(memberObj)
				):
					instance: TranslationEngine = memberObj()
					_engineInstances.append(instance)
					log.debug(f"Successfully loaded engine: {instance.name} (ID: {instance.id})")
		except Exception:
			log.error(f"Failed to load engine module '{name}'", exc_info=True)
	if not _engineInstances:
		log.warning(
			"""No translation engines were loaded successfully. This may be due to errors in the engine modules or an issue with the add-on installation. Translation functionality will not be available.""",
		)
	assert _engineInstances is not None
	_engineInstances.sort(key=lambda e: e.name)


def getAllEngines() -> list[TranslationEngine]:
	global _engineInstances
	if _engineInstances is None:
		_scanAndLoadEngines()
	assert _engineInstances is not None
	return _engineInstances


def _getEngineConfig(engineId: str) -> dict[str, Any]:
	"""Returns the saved configuration section for the given engine."""
	from ..common import config

	conf = config.getConfig()
	return conf["engines"].get(engineId, {})


def getEnabledEngines() -> list[TranslationEngine]:
	"""Returns all loaded engines that are enabled in the current configuration."""
	return [engine for engine in getAllEngines() if engine.isEnabled(_getEngineConfig(engine.id))]


def getNextEnabledEngine(currentId: str, forward: bool = True) -> TranslationEngine | None:
	"""Returns the next enabled engine after the given engine ID, or None if none are enabled."""
	allEngines = getAllEngines()
	if not allEngines:
		return None
	engineIds = [engine.id for engine in allEngines]
	try:
		currentIndex = engineIds.index(currentId)
	except ValueError:
		currentIndex = -1 if forward else 0
	step = 1 if forward else -1
	for offset in range(1, len(allEngines) + 1):
		newIndex = (currentIndex + (step * offset)) % len(allEngines)
		candidate = allEngines[newIndex]
		if candidate.isEnabled(_getEngineConfig(candidate.id)):
			return candidate
	return None


def getEngineById(engineId: str) -> TranslationEngine:
	allEngines = getAllEngines()
	for engine in allEngines:
		if engine.id == engineId:
			return engine
	raise ValueError(f"Engine with ID '{engineId}' not found.")
