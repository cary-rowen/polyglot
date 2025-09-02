# -*- coding: utf-8 -*-

import config as nvda_config
from .configspec import config_spec
from . import engine_manager
from logHandler import log
from configobj import ConfigObj
from . import ui_factory

CONF_SECTION = 'modernTranslate'

def _apply_engine_specs():
    engines_spec_section = config_spec['engines']
    for engine in engine_manager.get_all_engines():
        engine_id = engine.id
        engine_spec_list = engine.get_config_spec()
        if not engine_spec_list: continue
        if engine_id not in engines_spec_section:
            engines_spec_section[engine_id] = {}
        engine_spec_section = engines_spec_section[engine_id]
        for item in engine_spec_list:
            item_type = item['type']
            try:
                definition = ui_factory.get_control_handler(item_type)
            except ValueError:
                log.warning(f"Engine '{engine_id}' has unknown control type '{item_type}' for setting '{item['id']}'. Skipping spec generation.")
                continue
            default_value_formatted = definition.format_config_default(item['default'])
            spec_string = f"{item['id']} = {definition.config_type}(default={default_value_formatted})"
            line_spec = ConfigObj([spec_string], list_values=False)
            engine_spec_section.merge(line_spec)
        log.debug(f"Applied config spec for engine '{engine_id}': {engine_spec_section.items()}")

def initialize():
    log.debug(f"Initializing configuration for '{CONF_SECTION}'")
    _apply_engine_specs()
    spec = {CONF_SECTION: config_spec}
    nvda_config.conf.spec.merge(spec)

def get_config():
    return nvda_config.conf[CONF_SECTION]
