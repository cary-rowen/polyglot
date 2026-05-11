# -*- coding: utf-8 -*-

from collections import OrderedDict
from typing import Any

import addonHandler
import wx
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel
from logHandler import log

from ..common.cache import TranslationCache
from ..common import config
from ..services import engineManager
from . import factory as uiFactory

addonHandler.initTranslation()


class TranslationSettingsPanel(SettingsPanel):
	title = _("Polyglot")

	# Annotate instance variables with their known types
	engines: "OrderedDict[str, Any]"  # Forward reference because TranslationEngine is not imported
	cache: TranslationCache
	uiModel: dict[str, Any]
	dynamicControls: dict[str, dict[str, Any]]
	enginePanelContainer: wx.Panel
	enginePanelsCache: dict[str, wx.Panel]
	# Allow these instance variables to be None, matching their initial assignment.
	activeEnginePanel: wx.Panel | None
	_engineSwitchTimer: wx.CallLater | None

	def __init__(self, parent):
		self.engines = OrderedDict((e.id, e) for e in engineManager.getAllEngines())
		# TranslationCache is a singleton, so getting an instance here is safe
		# and will access the same cache used by the manager.
		self.cache = TranslationCache()
		self.uiModel = {}

		self.dynamicControls = {}
		self.enginePanelsCache = {}
		self.activeEnginePanel = None

		# --- DEBOUNCING STRATEGY: Timer for smooth engine switching ---
		self._engineSwitchTimer = None

		super().__init__(parent)
		self.Bind(wx.EVT_WINDOW_DESTROY, self._onDestroy)

	def makeSettings(self, sizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)

		self.engineChoice = sHelper.addLabeledControl(_("Translation &engine:"), wx.Choice)
		_unused = sHelper.addItem(wx.StaticLine(self, style=wx.LI_HORIZONTAL))

		self.enginePanelContainer = wx.Panel(self)
		self.enginePanelContainerSizer = wx.BoxSizer(wx.VERTICAL)
		self.enginePanelContainer.SetSizer(self.enginePanelContainerSizer)
		_unused = sHelper.addItem(self.enginePanelContainer, proportion=1, flag=wx.EXPAND)

		_unused = sHelper.addItem(wx.StaticLine(self, style=wx.LI_HORIZONTAL))

		commonBox = wx.StaticBox(self, label=_("Common Settings"))
		commonSizer = wx.StaticBoxSizer(commonBox, wx.VERTICAL)
		commonSHelper = guiHelper.BoxSizerHelper(self, sizer=commonSizer)

		self.copyResultCheckbox = commonSHelper.addItem(
			wx.CheckBox(self, label=_("Copy manual translation results to clipboard")),
		)
		self.enableSmartFilterCheckbox = commonSHelper.addItem(
			wx.CheckBox(
				self,
				label=_(
					"Enable smart speech filter (skips non-translatable text like roles, states, location and other formatting information)",
				),
			),
		)
		self.clearCacheButton = commonSHelper.addItem(wx.Button(self, label=_("Clear Cache")))
		_unused = sHelper.addItem(commonSizer, flag=wx.EXPAND)

		self.engineChoice.Bind(wx.EVT_CHOICE, self.onEngineChanged)
		self.copyResultCheckbox.Bind(wx.EVT_CHECKBOX, self.onAnyControlChanged)
		self.enableSmartFilterCheckbox.Bind(wx.EVT_CHECKBOX, self.onAnyControlChanged)
		self.clearCacheButton.Bind(wx.EVT_BUTTON, self.onClearCache)

		self._populateInitialState()

	def _onDestroy(self, event: wx.Event) -> None:
		"""Ensure the timer is stopped when the panel is destroyed."""
		if self._engineSwitchTimer and self._engineSwitchTimer.IsRunning():
			self._engineSwitchTimer.Stop()
		event.Skip()

	def onSave(self):
		conf = config.getConfig()
		self._syncModelFromUi()

		conf["engine"] = self.uiModel["engine"]
		conf["copyResult"] = self.uiModel["copyResult"]
		conf["enableSmartFilter"] = self.uiModel["enableSmartFilter"]

		for engineId, controls in self.dynamicControls.items():
			if not controls:
				continue
			if engineId not in conf["engines"]:
				conf["engines"][engineId] = {}
			engineConf = conf["engines"][engineId]
			for _unused, info in controls.items():
				info["handler"].saveToConfig(info["control"], engineConf, info["spec"])

	def onEngineChanged(self, event: wx.Event) -> None:
		"""Debounce the engine switch event to avoid stutter on rapid changes."""
		# If a switch is already scheduled, cancel it.
		if self._engineSwitchTimer and self._engineSwitchTimer.IsRunning():
			self._engineSwitchTimer.Stop()

		# Schedule the actual switch to happen after a short delay (200ms).
		self._engineSwitchTimer = wx.CallLater(200, self._performEngineSwitch)

	def _performEngineSwitch(self):
		"""The actual logic that switches the panel, called by the timer."""
		self.Freeze()
		try:
			self._switchEnginePanel()
		finally:
			self._sendLayoutUpdatedEvent()
			self.Thaw()

	def onAnyControlChanged(self, event: wx.Event | None = None):
		if event:
			event.Skip()

		self._syncModelFromUi()

		engine = self._getSelectedEngine()
		if not engine:
			return
		try:
			uiStates = engine.getUiStates(self.uiModel)
			self._applyUiStates(uiStates)
		except Exception:
			log.error(f"Error executing getUiStates for engine '{engine.id}'.", exc_info=True)

	def _populateInitialState(self):
		"""Populate settings controls and create the initial engine settings panel."""
		self.Freeze()
		try:
			conf = config.getConfig()
			for engineId, engine in self.engines.items():
				self.engineChoice.Append(engine.name, engineId)
			engineId = conf.get("engine", list(self.engines.keys())[0] if self.engines else None)
			if engineId and engineId in self.engines:
				self.engineChoice.SetStringSelection(self.engines[engineId].name)

			self.copyResultCheckbox.SetValue(conf.get("copyResult", True))
			self.enableSmartFilterCheckbox.SetValue(conf.get("enableSmartFilter", True))

			self._switchEnginePanel()
		finally:
			self.Thaw()

	def _switchEnginePanel(self):
		"""Show the panel for the selected engine, creating it if necessary."""
		engineId = self._getSelectedEngineId()
		if not engineId:
			return

		if self.activeEnginePanel:
			self.activeEnginePanel.Hide()

		if engineId in self.enginePanelsCache:
			panel = self.enginePanelsCache[engineId]
			panel.Show()
			self.activeEnginePanel = panel
		else:
			panel = self._createEnginePanel(engineId)
			self.enginePanelsCache[engineId] = panel
			self.enginePanelContainerSizer.Add(panel, 1, wx.EXPAND)
			self.activeEnginePanel = panel

		self.onAnyControlChanged()
		self.enginePanelContainer.Layout()
		self.Layout()

	def _createEnginePanel(self, engineId: str) -> wx.Panel:
		"""Create and populate the settings panel for a specific engine ONCE."""
		panel = wx.Panel(self.enginePanelContainer)
		engine = self.engines.get(engineId)
		if not engine:
			return panel

		engineConf = config.getConfig()["engines"].get(engine.id, {})
		configSpecList = engine.getConfigSpec()

		self.dynamicControls[engineId] = {}

		box = wx.StaticBox(panel, label=_("Current Engine Settings"))
		containerSizer = wx.StaticBoxSizer(box, wx.VERTICAL)

		if not configSpecList:
			noSettingsText = wx.StaticText(
				panel,
				label=_("This engine requires no additional configuration."),
			)
			containerSizer.Add(noSettingsText, 0, wx.ALL, 5)
			panel.SetSizer(containerSizer)
			return panel

		gridSizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
		gridSizer.AddGrowableCol(1)

		for spec in configSpecList:
			handler = uiFactory.getControlHandler(spec["type"])
			labelControl, control = handler.createControlPair(panel, spec)

			handler.loadFromConfig(control, engineConf, spec)
			handler.bindEvent(control, self.onAnyControlChanged)

			if labelControl is None:
				gridSizer.Add(control, 1, wx.EXPAND)
				gridSizer.AddSpacer(0)
			else:
				gridSizer.Add(labelControl, 0, wx.ALIGN_CENTER_VERTICAL)
				gridSizer.Add(control, 1, wx.EXPAND)

			self.dynamicControls[engineId][spec["id"]] = {
				"control": control,
				"handler": handler,
				"spec": spec,
				"labelControl": labelControl,
			}

		containerSizer.Add(gridSizer, 1, wx.EXPAND | wx.ALL, 5)
		panel.SetSizer(containerSizer)
		return panel

	def _applyUiStates(self, uiStates: dict[str, dict[str, Any]]):
		engineId = self._getSelectedEngineId()
		if not engineId or engineId not in self.dynamicControls:
			return

		for cid, states in uiStates.items():
			info = self.dynamicControls[engineId].get(cid)
			if not info:
				continue
			handler = info["handler"]
			for prop, value in states.items():
				handler.updateControlState(info["control"], info["labelControl"], prop, value)

		self.Layout()

	def _syncModelFromUi(self):
		engineId = self._getSelectedEngineId()
		if not engineId:
			return

		self.uiModel = {
			"engine": engineId,
			"copyResult": self.copyResultCheckbox.IsChecked(),
			"enableSmartFilter": self.enableSmartFilterCheckbox.IsChecked(),
		}

		if engineId in self.dynamicControls:
			for cid, info in self.dynamicControls[engineId].items():
				self.uiModel[cid] = info["handler"].getValueFromControl(info["control"])

	def onPanelActivated(self):
		super().onPanelActivated()
		self._updateCacheButton()

	def _getSelectedEngineId(self) -> str | None:
		selection = self.engineChoice.GetSelection()
		if selection == wx.NOT_FOUND:
			return None
		return self.engineChoice.GetClientData(selection)

	def _getSelectedEngine(self) -> Any | None:
		engineId = self._getSelectedEngineId()
		if not engineId:
			return None
		return self.engines.get(engineId)

	def onClearCache(self, event: wx.Event):
		self.cache.clear()
		self._updateCacheButton()
		wx.CallAfter(self.clearCacheButton.SetFocus)

	def _updateCacheButton(self):
		self.clearCacheButton.SetLabel(_("Clear Cache (Items: {})").format(self.cache.getItemCount()))
