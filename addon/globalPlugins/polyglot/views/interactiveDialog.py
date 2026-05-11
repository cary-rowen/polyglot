# -*- coding: utf-8 -*-

import wx
from gui import guiHelper
import api
import addonHandler
from gui.nvdaControls import DPIScaledDialog

from ..common import config
from ..services import engineManager

addonHandler.initTranslation()


class InteractiveTranslationDialog(DPIScaledDialog):
	"""
	A standalone modal dialog for interactive translation.
	"""

	def __init__(self, parent, manager):
		super().__init__(
			parent,
			title=_("Polyglot Interactive Translation"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self.manager = manager
		self.allEngines = engineManager.getEnabledEngines()
		self.hasEnabledEngines = bool(self.allEngines)

		# Internal state for dynamic choices
		self._modeIds = []
		self._modelIds = []
		self._langCodes = []

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# --- Configuration Area ---
		self.engineCombo = sHelper.addLabeledControl(
			_("Translation &engine:"),
			wx.Choice,
			choices=[e.name for e in self.allEngines]
			if self.hasEnabledEngines
			else [_("No enabled translation engines available.")],
		)
		self.sourceLangCombo = sHelper.addLabeledControl(_("Source language:"), wx.Choice)
		self.targetLangCombo = sHelper.addLabeledControl(_("Target language:"), wx.Choice)

		self.advancedBox = wx.StaticBox(self, label=_("Current Engine Settings"))
		self.advancedSizer = wx.StaticBoxSizer(self.advancedBox, wx.VERTICAL)
		# Use wx.VERTICAL to ensure addLabeledControl correctly treats items as vertical candidates if needed
		advHelper = guiHelper.BoxSizerHelper(self.advancedBox, orientation=wx.VERTICAL)

		self.modelCombo = advHelper.addLabeledControl(_("Model:"), wx.Choice)
		self.promptModeCombo = advHelper.addLabeledControl(_("Prompt Template:"), wx.Choice)
		self.systemPromptCtrl = advHelper.addLabeledControl(_("Custom System Prompt (Role):"), wx.TextCtrl)
		self.userPromptCtrl = advHelper.addLabeledControl(_("Custom User Prompt (Task):"), wx.TextCtrl)

		# Explicitly set expansion for controls inside the advanced box to match the look of text areas
		for ctrl in (self.modelCombo, self.promptModeCombo, self.systemPromptCtrl, self.userPromptCtrl):
			advHelper.sizer.GetItem(ctrl.GetContainingSizer()).SetFlag(wx.EXPAND | wx.TOP)

		self.advancedSizer.Add(advHelper.sizer, 0, wx.EXPAND | wx.ALL, 5)
		sHelper.addItem(self.advancedSizer)

		# --- Text Areas (Vertical Layout for better expansion) ---
		sourceLabel = wx.StaticText(self, label=_("Te&xt to translate:"))
		self.sourceTextCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER | wx.TE_RICH2)
		self.sourceTextCtrl.SetMinSize((-1, 120))
		sourceSizer = wx.BoxSizer(wx.VERTICAL)
		sourceSizer.Add(sourceLabel)
		sourceSizer.AddSpacer(guiHelper.SPACE_BETWEEN_ASSOCIATED_CONTROL_VERTICAL)
		sourceSizer.Add(self.sourceTextCtrl, flag=wx.EXPAND, proportion=1)
		sHelper.addItem(sourceSizer, flag=wx.EXPAND, proportion=1)

		resultLabel = wx.StaticText(self, label=_("Translation &result:"))
		self.resultTextCtrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
		self.resultTextCtrl.SetMinSize((-1, 120))
		resultSizer = wx.BoxSizer(wx.VERTICAL)
		resultSizer.Add(resultLabel)
		resultSizer.AddSpacer(guiHelper.SPACE_BETWEEN_ASSOCIATED_CONTROL_VERTICAL)
		resultSizer.Add(self.resultTextCtrl, flag=wx.EXPAND, proportion=1)
		sHelper.addItem(resultSizer, flag=wx.EXPAND, proportion=1)

		# --- Buttons ---
		bHelper = guiHelper.ButtonHelper(wx.HORIZONTAL)
		self.translateBtn = bHelper.addButton(self, label=_("&Translate"))
		self.translateBtn.SetDefault()
		if not self.hasEnabledEngines:
			self.translateBtn.Disable()
		self.copyBtn = bHelper.addButton(self, label=_("C&opy result"))
		self.clearBtn = bHelper.addButton(self, label=_("C&lear"))
		self.closeBtn = bHelper.addButton(self, id=wx.ID_CLOSE, label=_("&Close"))
		sHelper.addItem(bHelper)

		# Ensure the main sHelper sizer takes up all available vertical space in the dialog
		mainSizer.Add(sHelper.sizer, proportion=1, border=10, flag=wx.ALL | wx.EXPAND)
		self.SetSizer(mainSizer)
		self.SetMinSize((650, 700))
		self.SetEscapeId(wx.ID_CLOSE)

		# Initialize engine selection
		conf = config.getConfig()
		currentEngineId = conf["engine"]
		engineIndex = 0
		if self.hasEnabledEngines:
			for i, eng in enumerate(self.allEngines):
				if eng.id == currentEngineId:
					engineIndex = i
					break
			self.engineCombo.SetSelection(engineIndex)
		else:
			self.engineCombo.Disable()

		# Bind events
		self.Bind(wx.EVT_BUTTON, self.onClose, id=wx.ID_CLOSE)
		self.sourceTextCtrl.Bind(wx.EVT_CHAR_HOOK, self.onSourceTextChar)
		self.translateBtn.Bind(wx.EVT_BUTTON, self.onTranslate)
		self.clearBtn.Bind(wx.EVT_BUTTON, self.onClear)
		self.copyBtn.Bind(wx.EVT_BUTTON, self.onCopy)
		self.engineCombo.Bind(wx.EVT_CHOICE, self.updateEngineUI)
		self.promptModeCombo.Bind(wx.EVT_CHOICE, self.onPromptModeChanged)

		# Initial UI population
		if self.hasEnabledEngines:
			self.updateEngineUI(None)
		else:
			self._disableTranslationControls()

		self.Layout()
		self.Centre()
		if self.hasEnabledEngines:
			self.sourceTextCtrl.SetFocus()
		else:
			self.resultTextCtrl.SetFocus()

	def onSourceTextChar(self, event):
		if event.GetKeyCode() == wx.WXK_RETURN and event.ControlDown():
			self.onTranslate(None)
		else:
			event.Skip()

	def getSelectedEngine(self):
		return self.allEngines[self.engineCombo.GetSelection()]

	def updateEngineUI(self, event):
		if not self.hasEnabledEngines:
			return
		engine = self.getSelectedEngine()
		conf = config.getConfig()
		engineConf = conf["engines"].get(engine.id, {})
		spec = engine.getConfigSpec()

		promptModes = {}
		models = {}
		for item in spec:
			if item["id"] == "promptMode":
				promptModes = item.get("choices", {}).copy()
			elif item["id"] in ("modelNamePreset", "modelPreset"):
				models = item.get("choices", {}).copy()

		if "custom" in models:
			customName = engineConf.get("modelNameCustom", "").strip()
			if not customName:
				del models["custom"]
			else:
				# Translators: Label for custom model with its name.
				models["custom"] = _("Custom: {modelName}").format(modelName=customName)

		isLLM = bool(promptModes)
		self.advancedBox.Enable(isLLM)

		if models:
			self.modelCombo.Enable(True)
			sortedModels = sorted(models.items(), key=lambda x: x[1])
			self._modelIds = [x[0] for x in sortedModels]
			self.modelCombo.SetItems([x[1] for x in sortedModels])
			currentModel = engineConf.get("modelNamePreset", "custom")
			try:
				self.modelCombo.SetSelection(self._modelIds.index(currentModel))
			except ValueError:
				self.modelCombo.SetSelection(0)
		else:
			self.modelCombo.SetItems([_("Not applicable")])
			self.modelCombo.Disable()

		if promptModes:
			self.promptModeCombo.Enable(True)
			sortedModes = sorted(promptModes.items(), key=lambda x: x[1])
			self._modeIds = [x[0] for x in sortedModes]
			self.promptModeCombo.SetItems([x[1] for x in sortedModes])
			currentMode = engineConf.get("promptMode", "json_concise")
			try:
				self.promptModeCombo.SetSelection(self._modeIds.index(currentMode))
			except ValueError:
				self.promptModeCombo.SetSelection(0)
		else:
			self.promptModeCombo.SetItems([_("Not applicable")])
			self.promptModeCombo.Disable()

		supportedLangs = engine.getSupportedLanguages()
		sortedLangs = sorted(supportedLangs.items(), key=lambda x: x[1])
		self._langCodes = [x[0] for x in sortedLangs]
		langNames = [x[1] for x in sortedLangs]
		self.sourceLangCombo.SetItems(langNames)
		self.targetLangCombo.SetItems(langNames)

		defFrom = engineConf.get("langFrom", engine.defaultSourceLanguage)
		defTo = engineConf.get("langTo", engine.defaultTargetLanguage)
		try:
			self.sourceLangCombo.SetSelection(self._langCodes.index(defFrom))
		except ValueError:
			self.sourceLangCombo.SetSelection(0)
		try:
			self.targetLangCombo.SetSelection(self._langCodes.index(defTo))
		except ValueError:
			self.targetLangCombo.SetSelection(0)

		self.onPromptModeChanged(None)

	def _disableTranslationControls(self):
		"""Disables translation controls when no engines are enabled."""
		self._modeIds = []
		self._modelIds = []
		self._langCodes = []
		for control in (
			self.sourceLangCombo,
			self.targetLangCombo,
			self.advancedBox,
			self.sourceTextCtrl,
			self.modelCombo,
			self.promptModeCombo,
			self.systemPromptCtrl,
			self.userPromptCtrl,
		):
			control.Disable()
		self.resultTextCtrl.SetValue(_("No enabled translation engines available."))

	def onPromptModeChanged(self, event):
		if not self.hasEnabledEngines:
			return
		engine = self.getSelectedEngine()
		if not self.promptModeCombo.IsEnabled():
			self.systemPromptCtrl.SetValue(_("Not applicable"))
			self.userPromptCtrl.SetValue(_("Not applicable"))
			self.systemPromptCtrl.Disable()
			self.userPromptCtrl.Disable()
			return

		modeId = self._modeIds[self.promptModeCombo.GetSelection()]
		isCustom = modeId == "custom"

		if isCustom:
			conf = config.getConfig()
			engineConf = conf["engines"].get(engine.id, {})
			self.systemPromptCtrl.SetValue(engineConf.get("customSystemPrompt", ""))
			self.userPromptCtrl.SetValue(engineConf.get("customUserPrompt", ""))
			self.systemPromptCtrl.Enable(True)
			self.userPromptCtrl.Enable(True)
		else:
			attrBase = modeId.upper()
			sysTpl = getattr(engine, f"PROMPT_{attrBase}_SYSTEM", "")
			userTpl = getattr(engine, f"PROMPT_{attrBase}_USER", "")
			self.systemPromptCtrl.SetValue(sysTpl)
			self.userPromptCtrl.SetValue(userTpl)
			self.systemPromptCtrl.Disable()
			self.userPromptCtrl.Disable()

	def onTranslate(self, event):
		if not self.hasEnabledEngines:
			self.resultTextCtrl.SetValue(_("No enabled translation engines available."))
			self.resultTextCtrl.SetFocus()
			return
		text = self.sourceTextCtrl.GetValue().strip()
		if not text:
			return

		engine = self.getSelectedEngine()
		langFrom = self._langCodes[self.sourceLangCombo.GetSelection()]
		langTo = self._langCodes[self.targetLangCombo.GetSelection()]

		# Sync all UI choices to global config
		conf = config.getConfig()
		if conf["engine"] != engine.id:
			conf["engine"] = engine.id

		if engine.id not in conf["engines"]:
			conf["engines"][engine.id] = {}
		engineConf = conf["engines"][engine.id]

		engineConf["langFrom"] = langFrom
		engineConf["langTo"] = langTo

		if self.modelCombo.IsEnabled():
			engineConf["modelNamePreset"] = self._modelIds[self.modelCombo.GetSelection()]

		if self.promptModeCombo.IsEnabled():
			modeId = self._modeIds[self.promptModeCombo.GetSelection()]
			engineConf["promptMode"] = modeId
			if modeId == "custom":
				engineConf["customSystemPrompt"] = self.systemPromptCtrl.GetValue().strip()
				engineConf["customUserPrompt"] = self.userPromptCtrl.GetValue().strip()

		self.resultTextCtrl.SetValue(_("Translating..."))
		self.resultTextCtrl.SetFocus()
		self.translateBtn.Disable()

		def onSuccess(resultText):
			wx.CallAfter(self.onTranslationDone, resultText)

		def onError(errorMessage):
			wx.CallAfter(self.onTranslationError, errorMessage)

		self.manager.requestTranslation(
			text,
			onSuccess=onSuccess,
			onError=onError,
			showStatus=True,
		)

	def onTranslationDone(self, resultText):
		if self.hasEnabledEngines:
			self.translateBtn.Enable()
		self.resultTextCtrl.SetValue(resultText)
		self.resultTextCtrl.SetFocus()

	def onTranslationError(self, errorMessage: str) -> None:
		if self.hasEnabledEngines:
			self.translateBtn.Enable()
		self.resultTextCtrl.SetValue(errorMessage)
		self.resultTextCtrl.SetFocus()

	def onCopy(self, event):
		translation = self.resultTextCtrl.GetValue()
		if translation:
			api.copyToClip(translation)

	def onClear(self, event):
		self.sourceTextCtrl.Clear()
		self.resultTextCtrl.Clear()
		self.sourceTextCtrl.SetFocus()

	def onClose(self, event):
		self.EndModal(wx.ID_CLOSE)
