# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Minimal NVDA runtime stubs shared by standalone unit tests."""

import builtins
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_installed = False


def installNvdaStubs() -> None:
	"""Register lightweight NVDA module stubs and the ``polyglot`` package once."""
	global _installed
	if _installed:
		return
	if not hasattr(builtins, "_"):
		setattr(builtins, "_", lambda message: message)
	for moduleName in ("config", "nvwave", "queueHandler", "tones", "ui"):
		sys.modules.setdefault(moduleName, ModuleType(moduleName))
	for moduleName, attrName, value in (
		("NVDAState", "shouldWriteToDisk", Mock(return_value=False)),
		("globalVars", "appArgs", Mock(configPath=str(PROJECT_ROOT))),
		("extensionPoints", "Action", Mock),
		("addonHandler", "initTranslation", Mock()),
		("languageHandler", "getLanguage", Mock(return_value="en")),
		("logHandler", "log", Mock()),
		("polyglot", "__path__", [str(PROJECT_ROOT / "addon" / "globalPlugins" / "polyglot")]),
	):
		module = sys.modules.setdefault(moduleName, ModuleType(moduleName))
		if not hasattr(module, attrName):
			setattr(module, attrName, value)
	_installed = True
