# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import addonHandler

from ...common import languages
from ._nvdacn import NvdacnJsonEngine

addonHandler.initTranslation()


class TencentWebTranslateEngine(NvdacnJsonEngine):
	"""Translate text through the NVDACN-hosted Tencent web service."""

	id = "tencentPolyglot"
	name = _("Tencent Translate (Polyglot)")

	SERVICE_NAME = "tencentWeb"

	@property
	def autoDetectCode(self) -> str | None:
		return "auto"

	@property
	def fallbackTargetLanguage(self) -> str:
		return "zh"

	@property
	def doesReportDetectedLanguage(self) -> bool:
		"""Return whether the engine reports its automatically detected source language."""
		return False

	def getSupportedLanguages(self) -> dict:
		supportedCodes = ["auto", "zh", "en", "ja", "ko", "fr", "es", "ru", "de", "it", "ms", "th", "vi"]
		return languages.getLanguageDictForCodes(supportedCodes)
