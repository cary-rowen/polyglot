# -*- coding: utf-8 -*-

import addonHandler

from .ollama_base import OllamaBaseEngine

addonHandler.initTranslation()


class OllamaTranslateEngine(OllamaBaseEngine):
	"""
	This is the first, primary instance of the Ollama engine.
	It inherits all logic from the base engine and sets a unique ID and name.
	"""

	id = "ollama_1"
	name = _("Ollama 1")
