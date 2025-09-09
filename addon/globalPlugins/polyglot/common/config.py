# -*- coding: utf-8 -*-

import config as nvda_config
from typing import Any

CONF_SECTION = "modernTranslate"


def get_config() -> dict[str, Any]:
	"""Provides access to the addon's configuration section."""
	return nvda_config.conf[CONF_SECTION]
