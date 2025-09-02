# -*- coding: utf-8 -*-

import pkgutil
import importlib
import inspect
from logHandler import log
from .engine import TranslationEngine
from . import engines

_engine_instances = None

def _scan_and_load_engines():
    global _engine_instances
    log.debug("First-time scan: Loading translation engines...")
    _engine_instances = []
    for finder, name, ispkg in pkgutil.iter_modules(engines.__path__, engines.__name__ + '.'):
        try:
            module = importlib.import_module(name)
            for member_name, member_obj in inspect.getmembers(module):
                if (inspect.isclass(member_obj) and
                        issubclass(member_obj, TranslationEngine) and
                        member_obj is not TranslationEngine and
                        not inspect.isabstract(member_obj)):
                    instance = member_obj()
                    _engine_instances.append(instance)
                    log.debug(f"Successfully loaded engine: {instance.name} (ID: {instance.id})")
        except Exception as e:
            log.error(f"Failed to load engine module '{name}'", exc_info=True)
    if not _engine_instances:
        log.warning(
            "ModernTranslate: No translation engines were loaded successfully. "
            "This may be due to errors in the engine modules or an issue with the add-on installation. "
            "Translation functionality will not be available."
        )
    _engine_instances.sort(key=lambda e: e.name)

def get_all_engines() -> list[TranslationEngine]:
    global _engine_instances
    if _engine_instances is None:
        _scan_and_load_engines()
    return _engine_instances

def get_engine_by_id(engine_id: str) -> TranslationEngine:
    all_engines = get_all_engines()
    for engine in all_engines:
        if engine.id == engine_id:
            return engine
    raise ValueError(f"Engine with ID '{engine_id}' not found.")
