# -*- coding: utf-8 -*-

import addonHandler

from .ollama_base import OllamaBaseEngine

addonHandler.initTranslation()


class Ollama2TranslateEngine(OllamaBaseEngine):
	"""
	This is the second instance of the Ollama engine.
	It also inherits all logic and simply overrides the ID and name.
	"""

	id = "ollama_2"
	name = _("Ollama 2")
