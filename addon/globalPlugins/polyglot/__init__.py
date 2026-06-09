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
from .common.config import CONF_SECTION
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
	Scans all available engines, builds their dynamic config specs,
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
	return {CONF_SECTION: finalSpec}


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Polyglot")

	def __init__(self):
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
		self.manager.terminateAllTasks()
		self.speechFilter.unregister()
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
		if not self.isLayerActive:
			return super().getScript(gesture)
		script = super().getScript(gesture)
		if not script:
			script = self.script_layerError

		if getattr(script, "_stayInLayer", False):
			return script

		def wrappedScript(g):
			try:
				script(g)
			finally:
				self.finishLayer()

		return wrappedScript

	def finishLayer(self):
		self.isLayerActive = False
		self.clearGestureBindings()
		self.bindGestures(self.__gestures)

	def script_layerError(self, gesture: "inputCore.InputGesture") -> None:
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
		"""Gets selected text, handling errors. Returns text or None."""
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

	def _executeTranslation(self, text: str, reverse: bool, showStatus: bool) -> None:
		"""The single execution engine for all translation requests."""
		if not reverse:
			self.manager.requestTranslation(text, isManual=True, showStatus=showStatus)
		else:
			newFrom, newTo, errorMessage = self.manager.getReverseLanguages()
			if errorMessage:
				cues.Speech.message(errorMessage)
				return
			self.manager.requestTranslation(
				text,
				isManual=True,
				showStatus=showStatus,
				langFrom=newFrom,
				langTo=newTo,
			)

	def _cycleLanguage(self, target: str, forward: bool) -> None:
		success, message = self.manager.cycleLanguage(target, forward)
		cues.Speech.message(message)
		if not success:
			tones.beep(220, 120)

	@script(description=_("Next source language"))
	def script_cycleSourceLangForward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleLanguage("source", forward=True)

	script_cycleSourceLangForward._stayInLayer = True

	@script(description=_("Previous source language"))
	def script_cycleSourceLangBackward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleLanguage("source", forward=False)

	script_cycleSourceLangBackward._stayInLayer = True

	@script(description=_("Next target language"))
	def script_cycleTargetLangForward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleLanguage("target", forward=True)

	script_cycleTargetLangForward._stayInLayer = True

	@script(description=_("Previous target language"))
	def script_cycleTargetLangBackward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleLanguage("target", forward=False)

	script_cycleTargetLangBackward._stayInLayer = True

	def _cycleEngine(self, forward: bool) -> None:
		success, message = self.manager.cycleEngine(forward)
		cues.Speech.message(message)
		if not success:
			tones.beep(220, 120)

	@script(description=_("Next translation engine"))
	def script_cycleEngineForward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleEngine(forward=True)

	script_cycleEngineForward._stayInLayer = True

	@script(description=_("Previous translation engine"))
	def script_cycleEngineBackward(self, gesture: "inputCore.InputGesture") -> None:
		self._cycleEngine(forward=False)

	script_cycleEngineBackward._stayInLayer = True

	@script(description=_("Swap source and target languages"))
	def script_swapLanguages(self, gesture: "inputCore.InputGesture") -> None:
		success, message = self.manager.swapLanguages()
		cues.Speech.message(message)
		if not success:
			tones.beep(220, 120)

	script_swapLanguages._stayInLayer = True

	@script(description=_("Announce current engine and languages"))
	def script_announceEngineLanguagesInfo(self, gesture: "inputCore.InputGesture") -> None:
		announcement = self.manager.getCurrentEngineAndLanguageInfo()
		cues.Speech.message(announcement)

	script_announceEngineLanguagesInfo._stayInLayer = True

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
			self._executeTranslation(text, reverse=False, showStatus=True)

	@script(description=_("Translate selection (reversed direction)"))
	def script_translateReverseSelection(self, gesture: "inputCore.InputGesture") -> None:
		if text := self._getSelectedText():
			self._executeTranslation(text, reverse=True, showStatus=True)

	@script(description=_("Translate clipboard"))
	def script_translateClipboard(self, gesture: "inputCore.InputGesture") -> None:
		if not (text := api.getClipData()):
			cues.Speech.message(_("Clipboard is empty"))
			return
		self._executeTranslation(text, reverse=False, showStatus=True)

	@script(description=_("Translate clipboard (reversed direction)"))
	def script_translateReverseClipboard(self, gesture: "inputCore.InputGesture") -> None:
		if not (text := api.getClipData()):
			cues.Speech.message(_("Clipboard is empty"))
			return
		self._executeTranslation(text, reverse=True, showStatus=True)

	@script(description=_("Translate last spoken text"))
	def script_translateLastSpoken(self, gesture: "inputCore.InputGesture") -> None:
		if not (text := self.speechFilter.lastSpokenText):
			cues.Speech.message(_("No last spoken text"))
			return
		self._executeTranslation(text, reverse=False, showStatus=True)

	@script(description=_("Translate last spoken text (reversed direction)"))
	def script_translateReverseLastSpoken(self, gesture: "inputCore.InputGesture") -> None:
		if not (text := self.speechFilter.lastSpokenText):
			cues.Speech.message(_("No last spoken text"))
			return
		self._executeTranslation(text, reverse=True, showStatus=True)

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
