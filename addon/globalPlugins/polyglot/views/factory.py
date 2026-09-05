# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import wx
from configobj.validate import is_boolean
from logHandler import log

from ..common import config
from ..common.secureStorage import SecureStorageError

# Create a Type Alias for complex, reused types.
ConfigSpec = dict[str, Any]
ConfigSection = dict[str, Any]


class ControlHandlerBase:
	"""Define the configuration and wx-control conversion contract."""

	@property
	def configType(self) -> str:
		"""Return the ConfigObj validator type handled by this adapter."""
		raise NotImplementedError

	def formatConfigDefault(self, value: Any) -> str:
		"""Format a Python value for use in a ConfigObj specification."""
		raise NotImplementedError

	def createControlPair(
		self,
		panel: wx.Window,
		spec: ConfigSpec,
	) -> tuple[wx.StaticText | None, wx.Control]:
		"""Create the optional label and control described by spec."""
		raise NotImplementedError

	def getValueFromControl(self, control: wx.Control) -> Any:
		"""Return the configuration value represented by control."""
		raise NotImplementedError

	def setValueToControl(self, control: wx.Control, value: Any, spec: ConfigSpec):
		"""Apply a configuration value to control."""
		raise NotImplementedError

	def bindEvent(self, control: wx.Control, callback: Callable[[wx.Event], None]):
		"""Bind control's value-change event to callback."""
		raise NotImplementedError

	def updateControlState(
		self,
		control: wx.Control,
		labelControl: wx.StaticText | None,
		prop: str,
		value: Any,
	):
		"""Apply a dynamic enabled or visible state to a control pair."""
		if prop == "enabled":
			if control.IsEnabled() != value:
				control.Enable(bool(value))
				if labelControl:
					labelControl.Enable(bool(value))
		elif prop == "visible":
			isShown = control.IsShown()
			if isShown != value:
				control.Show(bool(value))
				if labelControl:
					labelControl.Show(bool(value))

	def loadFromConfig(self, control: wx.Control, configSection: ConfigSection, spec: ConfigSpec) -> None:
		"""Load a configuration value into the control."""
		value = configSection.get(spec["id"], spec.get("default"))
		self.setValueToControl(control, value, spec)

	def saveToConfig(self, control: wx.Control, configSection: ConfigSection, spec: ConfigSpec) -> None:
		"""Save the control's value to the configuration dictionary."""
		configSection[spec["id"]] = self.getValueFromControl(control)


def getControlHandler(typeName: str) -> ControlHandlerBase:
	"""Return the control handler registered for a configuration type."""
	if typeName not in _controlHandlers:
		raise ValueError(f"Unknown control type: '{typeName}'")
	return _controlHandlers[typeName]


class CheckboxHandler(ControlHandlerBase):
	"""Adapt boolean configuration items to wx checkboxes."""

	@property
	def configType(self) -> str:
		return "boolean"

	def formatConfigDefault(self, value: Any) -> str:
		return str(bool(value)).capitalize()

	def createControlPair(
		self,
		panel: wx.Window,
		spec: ConfigSpec,
	) -> tuple[wx.StaticText | None, wx.Control]:
		control = wx.CheckBox(panel, label=spec["label"])
		return (None, control)

	def getValueFromControl(self, control: wx.Control) -> bool:
		assert isinstance(control, wx.CheckBox)
		return control.IsChecked()

	def setValueToControl(self, control: wx.Control, value: Any, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.CheckBox)
		control.SetValue(is_boolean(value) if value is not None else False)

	def bindEvent(self, control: wx.Control, callback: Callable[[wx.Event], None]) -> None:
		assert isinstance(control, wx.CheckBox)
		control.Bind(wx.EVT_CHECKBOX, callback)


class LabeledControlHandler(ControlHandlerBase):
	"""Create controls whose labels are separate wx static-text controls."""

	def createControlPair(
		self,
		panel: wx.Window,
		spec: ConfigSpec,
	) -> tuple[wx.StaticText | None, wx.Control]:
		wxClass, kwargs = self.getWxClassAndKwargs(spec)
		label = wx.StaticText(panel, label=spec["label"])
		control = wxClass(panel, **kwargs)
		return (label, control)

	def getWxClassAndKwargs(self, spec: ConfigSpec) -> tuple[type[wx.Control], dict[str, Any]]:
		"""Return the wx control class and constructor arguments for spec."""
		raise NotImplementedError


class TextHandler(LabeledControlHandler):
	"""Adapt string and password configuration items to wx text controls."""

	@property
	def configType(self) -> str:
		return "string"

	def formatConfigDefault(self, value: Any) -> str:
		return f'"{str(value)}"'

	def getWxClassAndKwargs(self, spec: ConfigSpec) -> tuple[type[wx.Control], dict[str, Any]]:
		kwargs = {"style": wx.TE_PASSWORD} if spec.get("type") == "password" else {}
		return wx.TextCtrl, kwargs

	def getValueFromControl(self, control: wx.Control) -> str:
		assert isinstance(control, wx.TextCtrl)
		return control.GetValue()

	def setValueToControl(self, control: wx.Control, value: Any, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.TextCtrl)
		control.SetValue(str(value) if value is not None else "")

	def bindEvent(self, control: wx.Control, callback: Callable[[wx.Event], None]) -> None:
		assert isinstance(control, wx.TextCtrl)
		control.Bind(wx.EVT_TEXT, callback)


class PasswordHandler(TextHandler):
	"""Encrypt password controls while keeping plaintext confined to the settings control."""

	def loadFromConfig(self, control: wx.Control, configSection: ConfigSection, spec: ConfigSpec) -> None:
		"""Decrypt a protected or legacy plaintext value into a password control."""
		storedValue = str(configSection.get(spec["id"], spec.get("default")) or "")
		try:
			plainValue = config.unprotectSecret(storedValue)
		except SecureStorageError:
			log.warning(
				"Stored secret for setting '%s' could not be unprotected on this computer.",
				spec["id"],
				exc_info=True,
			)
			plainValue = ""
		self.setValueToControl(control, plainValue, spec)
		assert isinstance(control, wx.TextCtrl)
		control.SetModified(False)

	def saveToConfig(self, control: wx.Control, configSection: ConfigSection, spec: ConfigSpec) -> None:
		"""Encrypt a changed password control before updating the configuration."""
		assert isinstance(control, wx.TextCtrl)
		if not control.IsModified():
			return
		protectedValue = config.protectSecret(control.GetValue())
		configSection[spec["id"]] = protectedValue
		control.SetModified(False)


class ChoiceHandler(LabeledControlHandler):
	"""Adapt enumerated string configuration items to wx choices."""

	@property
	def configType(self) -> str:
		return "string"

	def formatConfigDefault(self, value: Any) -> str:
		return f'"{str(value)}"'

	def getWxClassAndKwargs(self, spec: ConfigSpec) -> tuple[type[wx.Control], dict[str, Any]]:
		return wx.Choice, {}

	def getValueFromControl(self, control: wx.Control) -> Any:
		assert isinstance(control, wx.Choice)
		selection = control.GetSelection()
		return control.GetClientData(selection) if selection != wx.NOT_FOUND else None

	def setValueToControl(self, control: wx.Control, value: Any, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.Choice)
		self.populateChoices(control, spec.get("choices", {}), value)

	def updateControlState(
		self,
		control: wx.Control,
		labelControl: wx.StaticText | None,
		prop: str,
		value: Any,
	) -> None:
		assert isinstance(control, wx.Choice)
		if prop == "choices":
			currentSelection = self.getValueFromControl(control)
			self.populateChoices(control, value, currentSelection)
		else:
			super().updateControlState(control, labelControl, prop, value)

	def populateChoices(
		self,
		choiceCtrl: wx.Choice,
		choicesDict: dict[str, str],
		currentValueCode: Any = None,
	) -> None:
		"""Update choice items while retaining a valid current selection."""
		currentChoices = OrderedDict()
		for i in range(choiceCtrl.GetCount()):
			currentChoices[choiceCtrl.GetClientData(i)] = choiceCtrl.GetString(i)

		if choicesDict == currentChoices:
			return

		choiceCtrl.Freeze()
		try:
			if not choicesDict:
				choiceCtrl.Clear()
				choiceCtrl.Disable()
				return
			choiceCtrl.Enable()
			codes, names = list(choicesDict.keys()), list(choicesDict.values())
			choiceCtrl.Clear()
			for i, name in enumerate(names):
				choiceCtrl.Append(name, codes[i])
			finalCode = currentValueCode if currentValueCode in codes else (codes[0] if codes else None)
			if finalCode:
				try:
					index = codes.index(finalCode)
					if choiceCtrl.GetSelection() != index:
						choiceCtrl.SetSelection(index)
				except (ValueError, KeyError):
					if choiceCtrl.GetCount() > 0:
						choiceCtrl.SetSelection(0)
			elif choiceCtrl.GetCount() > 0:
				choiceCtrl.SetSelection(0)
		finally:
			choiceCtrl.Thaw()

	def bindEvent(self, control: wx.Control, callback: Callable[[wx.Event], None]) -> None:
		assert isinstance(control, wx.Choice)
		control.Bind(wx.EVT_CHOICE, callback)


class SpinCtrlHandler(LabeledControlHandler):
	"""Adapt bounded integer configuration items to wx spin controls."""

	@property
	def configType(self) -> str:
		return "integer"

	def formatConfigDefault(self, value: Any) -> str:
		return str(int(value))

	def getWxClassAndKwargs(self, spec: ConfigSpec) -> tuple[type[wx.Control], dict[str, Any]]:
		kwargs = {
			"value": str(spec.get("default", 15)),
			"min": spec.get("min", 1),
			"max": spec.get("max", 60),
		}
		# wx.SpinCtrl accepts min, max, and initial as constructor arguments.
		return wx.SpinCtrl, {"min": kwargs["min"], "max": kwargs["max"], "initial": int(kwargs["value"])}

	def getValueFromControl(self, control: wx.Control) -> int:
		assert isinstance(control, wx.SpinCtrl)
		return control.GetValue()

	def setValueToControl(self, control: wx.Control, value: Any, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.SpinCtrl)
		try:
			control.SetValue(int(value))
		except (ValueError, TypeError):
			control.SetValue(spec.get("default", control.GetMin()))

	def bindEvent(self, control: wx.Control, callback: Callable[[wx.Event], None]) -> None:
		assert isinstance(control, wx.SpinCtrl)
		# The EVT_SPINCTRL event triggers when the value changes.
		control.Bind(wx.EVT_SPINCTRL, callback)
		# Also bind the text event to respond to direct input.
		control.Bind(wx.EVT_TEXT, callback)


_controlHandlers: dict[str, ControlHandlerBase] = {
	"checkbox": CheckboxHandler(),
	"text": TextHandler(),
	"password": PasswordHandler(),
	"choice": ChoiceHandler(),
	"spinctrl": SpinCtrlHandler(),
}
