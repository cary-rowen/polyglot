# Copyright (C) 2025-2026 cary-rowen <manchen_0528@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

import os
import sys

# Load websocket-client submodule
_ADDON_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_WEBSOCKET_CLIENT_PATH = os.path.join(_ADDON_DIR, "websocketClientRepo")
if _WEBSOCKET_CLIENT_PATH not in sys.path:
	# Insert at priority 1 to keep current dir at 0, but override other global packages
	sys.path.insert(1, _WEBSOCKET_CLIENT_PATH)

import addonHandler
import api
import config
import globalPluginHandler
import globalVars
import gui
import inputCore
import textInfos
import tones
import ui
import wx
from configobj import ConfigObj, Section
from keyboardHandler import KeyboardInputGesture
from logHandler import log
from scriptHandler import script

from .app.manager import TranslationManager
from .app.speechFilter import SpeechFilter
from .common import cues
from .common.config import getConfigSectionName
from .common.network import closeSession
from .configspec import configSpec
from .services import engineManager
from .services.cdpBridge import CdpBridge
from .modelManager import menu as modelManagerMenu
from .views import factory as uiFactory
from .views import settings
from .views.interactiveDialog import InteractiveTranslationDialog

addonHandler.initTranslation()


def _buildFinalConfigSpec() -> dict[str, ConfigObj]:
	"""
	Scan all available engines, build their dynamic config specs,
	and merges them with the static base spec.
	This function acts as the "composition root" for configuration,
	coordinating between services and views.

	Returns:
		A complete configspec dictionary for the entire addon.
	"""
	finalSpec = configSpec.copy()
	enginesSpecSection = finalSpec["engines"]
	allEngines = engineManager.getAllEngines()
	for engine in allEngines:
		engineId = engine.id
		engineSpecList = engine.getConfigSpec()
		if not engineSpecList:
			continue
		if engineId not in enginesSpecSection:
			enginesSpecSection[engineId] = {}
		engineSection: Section = enginesSpecSection[engineId]
		for item in engineSpecList:
			try:
				handler = uiFactory.getControlHandler(item["type"])
				defaultVal = handler.formatConfigDefault(item["default"])
				specStr = f"{item['id']} = {handler.configType}(default={defaultVal})"
				engineSection.merge(ConfigObj([specStr], list_values=False))
			except ValueError:
				log.warning(f"Engine '{engineId}' has an unknown control type '{item['type']}'. Skipping.")
	return {getConfigSectionName(): finalSpec}


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Expose Polyglot commands and lifecycle integration to NVDA."""

	scriptCategory = _("Polyglot")

	def __init__(self):
		"""Initialize configuration, translation services, UI, and speech hooks."""
		super().__init__()
		# Let this module build the complete, dynamic config spec.
		finalSpec = _buildFinalConfigSpec()
		# Merge this final spec into NVDA's configuration.
		config.conf.spec.merge(finalSpec)
		self.manager = TranslationManager()
		self.speechFilter = SpeechFilter(self.manager)
		self.speechFilter.register()
		self.isLayerActive = False
		self.modelManagerMenuItem: wx.MenuItem | None = None
		if not globalVars.appArgs.secure:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(settings.TranslationSettingsPanel)
			self.modelManagerMenuItem = modelManagerMenu.bindToolsMenu(self)

	def terminate(self):
		"""Unregister Polyglot UI and speech integrations and release resources."""
		self.manager.terminateAllTasks()
		self.speechFilter.unregister()
		closeSession()
		CdpBridge.getInstance().terminate()
		modelManagerMenu.closeModelManagerDialog()
		if not globalVars.appArgs.secure:
			if settings.TranslationSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
				gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(
					settings.TranslationSettingsPanel,
				)
			modelManagerMenu.unbindToolsMenu(self.modelManagerMenuItem)
		super().terminate()

	def onOpenModelManager(self, event: wx.CommandEvent) -> None:
		"""Open the native ChromeAI model manager from NVDA's Tools menu."""
		modelManagerMenu.openModelManagerDialog()

	def getScript(self, gesture: "inputCore.InputGesture") -> None:
		"""Resolve gestures through the command layer while it is active."""
		if not self.isLayerActive:
			return super().getScript(gesture)
		script = super().getScript(gesture)
		if not script:
			script = self.script_layerError

		if getattr(script, "_shouldStayInLayer", False):
			return script

		def wrappedScript(g):
			try:
				script(g)
			finally:
				self._finishLayer()

		return wrappedScript

	def _finishLayer(self):
		"""Leave the command layer and restore normal gesture bindings."""
		self.isLayerActive = False
		self.clearGestureBindings()
		self.bindGestures(self.__gestures)

	def script_layerError(self, gesture: "inputCore.InputGesture") -> None:
		"""Signal that a gesture has no command-layer action."""
		tones.beep(120, 100)

	@script(description=_("Enter the translation command layer; press H for command layer help"))
	def script_layerEntry(self, gesture: "inputCore.InputGesture") -> None:
		if self.isLayerActive:
			self.script_layerError(gesture)
			return
		self.speechFilter.setGracePeriod()
		self.bindGestures(self.__layerGestures)
		self.isLayerActive = True
		tones.beep(100, 10)

	def _getSelectedText(self) -> str | None:
		"""Get selected text, returning None when selection access fails."""
		try:
			info = api.getCaretObject().makeTextInfo(textInfos.POSITION_SELECTION)
			if not info or info.isCollapsed:
				cues.Speech.message(_("Nothing selected"))
				return None
			return info.text
		except NotImplementedError:
			log.warning("Failed to get selected text from the current object.", exc_info=True)
			cues.Speech.message(_("Cannot get selected text from the current object"))
			return None

	def _executeTranslation(self, text: str, shouldReverse: bool, shouldShowStatus: bool) -> None:
		"""Route one command-layer request through the translation manager."""
		if not shouldReverse:
			self.manager.requestTranslation(
				text,
				isManual=True,
				shouldShowStatus=shouldShowStatus,
				shouldPreferLocalDictionary=True,
			)
		else:
			newFrom, newTo, errorMessage = self.manager.getReverseLanguages()
			if errorMessage:
				cues.Speech.message(errorMessage)
				return
			self.manager.requestTranslation(
				text,
				isManual=True,
				shouldShowStatus=shouldShowStatus,
				langFrom=newFrom,
				langTo=newTo,
				shouldPreferLocalDictionary=True,
			)

	def _cycleLanguage(self, target: str, isForward: bool) -> None:
		"""Cycle one configured language and announce the result."""
		isSuccessful, message = self.manager.cycleLanguage(target, isForward)
		cues.Speech.message(message)
		if not isSuccessful:
			tones.beep(220, 120)

	@script(description=_("Next source language"))
	def script_cycleSourceLangForward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleLanguage("source", isForward=True)

	script_cycleSourceLangForward._shouldStayInLayer = True

	@script(description=_("Previous source language"))
	def script_cycleSourceLangBackward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleLanguage("source", isForward=False)

	script_cycleSourceLangBackward._shouldStayInLayer = True

	@script(description=_("Next target language"))
	def script_cycleTargetLangForward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleLanguage("target", isForward=True)

	script_cycleTargetLangForward._shouldStayInLayer = True

	@script(description=_("Previous target language"))
	def script_cycleTargetLangBackward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleLanguage("target", isForward=False)

	script_cycleTargetLangBackward._shouldStayInLayer = True

	def _cycleEngine(self, isForward: bool) -> None:
		"""Cycle the configured engine and announce the result."""
		isSuccessful, message = self.manager.cycleEngine(isForward)
		cues.Speech.message(message)
		if not isSuccessful:
			tones.beep(220, 120)

	@script(description=_("Next translation engine"))
	def script_cycleEngineForward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleEngine(isForward=True)

	script_cycleEngineForward._shouldStayInLayer = True

	@script(description=_("Previous translation engine"))
	def script_cycleEngineBackward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleEngine(isForward=False)

	script_cycleEngineBackward._shouldStayInLayer = True

	@script(description=_("Swap source and target languages"))
	def script_swapLanguages(self, gesture: "inputCore.InputGesture") -> None:
		isSuccessful, message = self.manager.swapLanguages()
		cues.Speech.message(message)
		if not isSuccessful:
			tones.beep(220, 120)

	script_swapLanguages._shouldStayInLayer = True

	@script(description=_("Announce current engine and languages"))
	def script_announceEngineLanguagesInfo(self, gesture: "inputCore.InputGesture") -> None:
		announcement = self.manager.getCurrentEngineAndLanguageInfo()
		cues.Speech.message(announcement)

	script_announceEngineLanguagesInfo._shouldStayInLayer = True

	@script(description=_("Copy last translation to clipboard"))
	def script_copyLastResult(self, gesture: "inputCore.InputGesture") -> None:
		lastResult = self.manager.lastTranslation
		if lastResult:
			_unused = api.copyToClip(lastResult, notify=True)
		else:
			cues.Speech.message(_("No translation result to copy"))

	@script(description=_("Open interactive translation dialog"))
	def script_openInteractiveDialog(self, gesture: "inputCore.InputGesture") -> None:
		def showDialog():
			gui.mainFrame.prePopup()
			try:
				dialog = InteractiveTranslationDialog(gui.mainFrame, self.manager)
				dialog.ShowModal()
				dialog.Destroy()
			finally:
				gui.mainFrame.postPopup()

		wx.CallAfter(showDialog)

	@script(description=_("Open settings"))
	def script_openSettings(self, gesture: "inputCore.InputGesture") -> None:
		wx.CallAfter(
			gui.mainFrame.popupSettingsDialog,
			gui.settingsDialogs.NVDASettingsDialog,
			settings.TranslationSettingsPanel,
		)

	@script(description=_("Toggle auto-translation"))
	def script_toggleAutoTranslate(self, gesture: "inputCore.InputGesture") -> None:
		newState = self.manager.toggleAutoTranslate()
		cues.Speech.message(_("Auto-translation enabled") if newState else _("Auto-translation disabled"))

	@script(description=_("Clear cache"))
	def script_clearCache(self, gesture: "inputCore.InputGesture") -> None:
		self.manager.clearCache()
		cues.Speech.message(_("Cache cleared"))

	@script(description=_("Translate selection"))
	def script_translateSelection(self, gesture: "inputCore.InputGesture") -> None:
		if text := self._getSelectedText():
			self._executeTranslation(text, shouldReverse=False, shouldShowStatus=True)

	@script(description=_("Translate selection (reversed direction)"))
	def script_translateReverseSelection(self, gesture: "inputCore.InputGesture") -> None:
		if text := self._getSelectedText():
			self._executeTranslation(text, shouldReverse=True, shouldShowStatus=True)

	@script(description=_("Translate clipboard"))
	def script_translateClipboard(self, gesture: "inputCore.InputGesture") -> None:
		if not (text := api.getClipData()):
			cues.Speech.message(_("Clipboard is empty"))
			return
		self._executeTranslation(text, shouldReverse=False, shouldShowStatus=True)

	@script(description=_("Translate clipboard (reversed direction)"))
	def script_translateReverseClipboard(self, gesture: "inputCore.InputGesture") -> None:
		if not (text := api.getClipData()):
			cues.Speech.message(_("Clipboard is empty"))
			return
		self._executeTranslation(text, shouldReverse=True, shouldShowStatus=True)

	@script(description=_("Translate last spoken text"))
	def script_translateLastSpoken(self, gesture: "inputCore.InputGesture") -> None:
		if not (text := self.speechFilter.lastSpokenText):
			cues.Speech.message(_("No last spoken text"))
			return
		self._executeTranslation(text, shouldReverse=False, shouldShowStatus=True)

	@script(description=_("Translate last spoken text (reversed direction)"))
	def script_translateReverseLastSpoken(self, gesture: "inputCore.InputGesture") -> None:
		if not (text := self.speechFilter.lastSpokenText):
			cues.Speech.message(_("No last spoken text"))
			return
		self._executeTranslation(text, shouldReverse=True, shouldShowStatus=True)

	@script(description=_("Show command layer help"))
	def script_layerHelp(self, gesture: "inputCore.InputGesture") -> None:
		ui.browseableMessage(
			self._generateLayerHelpHtml(),
			title=_("Polyglot Help"),
			isHtml=True,
			closeButton=True,
			copyButton=True,
		)

	def _generateLayerHelpHtml(self) -> str:
		groups = [
			(
				_("Translation Actions"),
				[
					"translateSelection",
					"translateReverseSelection",
					"translateClipboard",
					"translateReverseClipboard",
					"translateLastSpoken",
					"translateReverseLastSpoken",
				],
			),
			(
				_("Configuration & Switching"),
				[
					"cycleSourceLangForward",
					"cycleSourceLangBackward",
					"cycleTargetLangForward",
					"cycleTargetLangBackward",
					"cycleEngineForward",
					"cycleEngineBackward",
					"swapLanguages",
					"announceEngineLanguagesInfo",
				],
			),
			(
				_("Tools & System"),
				[
					"openInteractiveDialog",
					"copyLastResult",
					"toggleAutoTranslate",
					"clearCache",
					"openSettings",
					"layerHelp",
				],
			),
		]

		scriptToKey = {}
		for gesture, scriptName in self.__layerGestures.items():
			_source, keyDisplayName = KeyboardInputGesture.getDisplayTextForIdentifier(gesture)
			scriptToKey[scriptName] = keyDisplayName

		htmlParts = []
		for title, scripts in groups:
			htmlParts.append(f"<h2>{title}</h2>")
			htmlParts.append("<table border='1' style='border-collapse: collapse; width: 100%;'>")
			htmlParts.append(
				f"<thead><tr><th style='text-align: left; padding: 5px;'>{_('Key')}</th><th style='text-align: left; padding: 5px;'>{_('Action')}</th></tr></thead>",
			)
			htmlParts.append("<tbody>")
			for scriptName in scripts:
				keyDisplay = scriptToKey.get(scriptName, "")
				if not keyDisplay:
					continue
				method = getattr(self, f"script_{scriptName}")
				description = method.__doc__ or scriptName
				htmlParts.append(
					f"<tr><td style='padding: 5px;'>{keyDisplay}</td><td style='padding: 5px;'>{description}</td></tr>",
				)
			htmlParts.append("</tbody></table>")

		return "".join(htmlParts)

	__gestures = {"kb:NVDA+Alt+Z": "layerEntry"}
	__layerGestures = {
		"kb:t": "translateSelection",
		"kb:shift+t": "translateReverseSelection",
		"kb:b": "translateClipboard",
		"kb:shift+b": "translateReverseClipboard",
		"kb:l": "translateLastSpoken",
		"kb:shift+l": "translateReverseLastSpoken",
		"kb:s": "cycleSourceLangForward",
		"kb:shift+s": "cycleSourceLangBackward",
		"kb:g": "cycleTargetLangForward",
		"kb:shift+g": "cycleTargetLangBackward",
		"kb:e": "cycleEngineForward",
		"kb:shift+e": "cycleEngineBackward",
		"kb:w": "swapLanguages",
		"kb:a": "announceEngineLanguagesInfo",
		"kb:c": "copyLastResult",
		"kb:v": "toggleAutoTranslate",
		"kb:i": "openInteractiveDialog",
		"kb:o": "openSettings",
		"kb:x": "clearCache",
		"kb:h": "layerHelp",
	}
