# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import wx
from configobj.validate import is_boolean

# Create a Type Alias for complex, reused types.
ConfigSpec = dict[str, Any]
ConfigSection = dict[str, Any]


class ControlHandlerBase(ABC):
	@property
	@abstractmethod
	def config_type(self) -> str:
		pass

	@abstractmethod
	def format_config_default(self, value: Any) -> str:
		pass

	@abstractmethod
	def create_control_pair(
		self, panel: wx.Window, spec: ConfigSpec
	) -> tuple[wx.StaticText | None, wx.Control]:
		pass

	@abstractmethod
	def get_value_from_control(self, control: wx.Control) -> Any:
		pass

	@abstractmethod
	def set_value_to_control(self, control: wx.Control, value: Any, spec: ConfigSpec):
		pass

	@abstractmethod
	def bind_event(self, control: wx.Control, callback: Callable[[wx.Event], None]):
		"""Binds the appropriate 'value changed' event to the control."""
		pass

	def update_control_state(
		self, control: wx.Control, label_control: wx.StaticText | None, prop: str, value: Any
	):
		if prop == "enabled":
			if control.IsEnabled() != value:
				control.Enable(bool(value))
				if label_control:
					label_control.Enable(bool(value))
		elif prop == "visible":
			is_shown = control.IsShown()
			if is_shown != value:
				control.Show(bool(value))
				if label_control:
					label_control.Show(bool(value))

	@abstractmethod
	def load_from_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec):
		"""Loads a value from the config dictionary and applies it to the control."""
		pass

	@abstractmethod
	def save_to_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec):
		"""Gets the value from the control and saves it to the config dictionary."""
		pass


_control_registry: dict[str, ControlHandlerBase] = {}


def register_control(type_name: str) -> Callable[[type[ControlHandlerBase]], type[ControlHandlerBase]]:
	def decorator(cls: type[ControlHandlerBase]) -> type[ControlHandlerBase]:
		if type_name in _control_registry:
			raise ValueError(f"Control type '{type_name}' is already registered.")
		_control_registry[type_name] = cls()
		return cls

	return decorator


def get_control_handler(type_name: str) -> ControlHandlerBase:
	if type_name not in _control_registry:
		raise ValueError(f"Unknown control type: '{type_name}'")
	return _control_registry[type_name]


@register_control("checkbox")
class CheckboxHandler(ControlHandlerBase):
	@property
	def config_type(self) -> str:
		return "boolean"

	def format_config_default(self, value: Any) -> str:
		return str(bool(value)).capitalize()

	def create_control_pair(
		self, panel: wx.Window, spec: ConfigSpec
	) -> tuple[wx.StaticText | None, wx.Control]:
		control = wx.CheckBox(panel, label=spec["label"])
		return (None, control)

	def get_value_from_control(self, control: wx.Control) -> bool:
		assert isinstance(control, wx.CheckBox)
		return control.IsChecked()

	def set_value_to_control(self, control: wx.Control, value: Any, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.CheckBox)
		control.SetValue(is_boolean(value) if value is not None else False)

	def bind_event(self, control: wx.Control, callback: Callable[[wx.Event], None]) -> None:
		assert isinstance(control, wx.CheckBox)
		control.Bind(wx.EVT_CHECKBOX, callback)

	def load_from_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.CheckBox)
		value = config_section.get(spec["id"], spec.get("default"))
		self.set_value_to_control(control, value, spec)

	def save_to_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.CheckBox)
		config_section[spec["id"]] = self.get_value_from_control(control)


class LabeledControlHandler(ControlHandlerBase, ABC):
	def create_control_pair(
		self, panel: wx.Window, spec: ConfigSpec
	) -> tuple[wx.StaticText | None, wx.Control]:
		wx_class, kwargs = self.get_wx_class_and_kwargs(spec)
		label = wx.StaticText(panel, label=spec["label"])
		control = wx_class(panel, **kwargs)
		return (label, control)

	@abstractmethod
	def get_wx_class_and_kwargs(self, spec: ConfigSpec) -> tuple[type[wx.Control], dict[str, Any]]:
		pass


@register_control("text")
@register_control("password")
class TextHandler(LabeledControlHandler):
	@property
	def config_type(self) -> str:
		return "string"

	def format_config_default(self, value: Any) -> str:
		return f'"{str(value)}"'

	def get_wx_class_and_kwargs(self, spec: ConfigSpec) -> tuple[type[wx.Control], dict[str, Any]]:
		kwargs = {"style": wx.TE_PASSWORD} if spec.get("type") == "password" else {}
		return wx.TextCtrl, kwargs

	def get_value_from_control(self, control: wx.Control) -> str:
		assert isinstance(control, wx.TextCtrl)
		return control.GetValue()

	def set_value_to_control(self, control: wx.Control, value: Any, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.TextCtrl)
		control.SetValue(str(value) if value is not None else "")

	def bind_event(self, control: wx.Control, callback: Callable[[wx.Event], None]) -> None:
		assert isinstance(control, wx.TextCtrl)
		control.Bind(wx.EVT_TEXT, callback)

	def load_from_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.TextCtrl)
		value = config_section.get(spec["id"], spec.get("default"))
		self.set_value_to_control(control, value, spec)

	def save_to_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.TextCtrl)
		config_section[spec["id"]] = self.get_value_from_control(control)


@register_control("choice")
class ChoiceHandler(LabeledControlHandler):
	@property
	def config_type(self) -> str:
		return "string"

	def format_config_default(self, value: Any) -> str:
		return f'"{str(value)}"'

	def get_wx_class_and_kwargs(self, spec: ConfigSpec) -> tuple[type[wx.Control], dict[str, Any]]:
		return wx.Choice, {}

	def get_value_from_control(self, control: wx.Control) -> Any:
		assert isinstance(control, wx.Choice)
		selection = control.GetSelection()
		return control.GetClientData(selection) if selection != wx.NOT_FOUND else None

	def set_value_to_control(self, control: wx.Control, value: Any, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.Choice)
		self.populate_choices(control, spec.get("choices", {}), value)

	def update_control_state(
		self, control: wx.Control, label_control: wx.StaticText | None, prop: str, value: Any
	) -> None:
		assert isinstance(control, wx.Choice)
		if prop == "choices":
			current_selection = self.get_value_from_control(control)
			self.populate_choices(control, value, current_selection)
		else:
			super().update_control_state(control, label_control, prop, value)

	def populate_choices(
		self, choice_ctrl: wx.Choice, choices_dict: dict[str, str], current_value_code: Any = None
	) -> None:
		current_choices = OrderedDict()
		for i in range(choice_ctrl.GetCount()):
			current_choices[choice_ctrl.GetClientData(i)] = choice_ctrl.GetString(i)

		if choices_dict == current_choices:
			return

		choice_ctrl.Freeze()
		try:
			if not choices_dict:
				choice_ctrl.Clear()
				choice_ctrl.Disable()
				return
			choice_ctrl.Enable()
			codes, names = list(choices_dict.keys()), list(choices_dict.values())
			choice_ctrl.Clear()
			for i, name in enumerate(names):
				choice_ctrl.Append(name, codes[i])
			final_code = current_value_code if current_value_code in codes else (codes[0] if codes else None)
			if final_code:
				try:
					index = codes.index(final_code)
					if choice_ctrl.GetSelection() != index:
						choice_ctrl.SetSelection(index)
				except (ValueError, KeyError):
					if choice_ctrl.GetCount() > 0:
						choice_ctrl.SetSelection(0)
			elif choice_ctrl.GetCount() > 0:
				choice_ctrl.SetSelection(0)
		finally:
			choice_ctrl.Thaw()

	def bind_event(self, control: wx.Control, callback: Callable[[wx.Event], None]) -> None:
		assert isinstance(control, wx.Choice)
		control.Bind(wx.EVT_CHOICE, callback)

	def load_from_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.Choice)
		value = config_section.get(spec["id"], spec.get("default"))
		self.set_value_to_control(control, value, spec)

	def save_to_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.Choice)
		config_section[spec["id"]] = self.get_value_from_control(control)


@register_control("spinctrl")
class SpinCtrlHandler(LabeledControlHandler):
	@property
	def config_type(self) -> str:
		return "integer"

	def format_config_default(self, value: Any) -> str:
		return str(int(value))

	def get_wx_class_and_kwargs(self, spec: ConfigSpec) -> tuple[type[wx.Control], dict[str, Any]]:
		kwargs = {
			"value": str(spec.get("default", 15)),
			"min": spec.get("min", 1),
			"max": spec.get("max", 60),
		}
		# wx.SpinCtrl accepts min, max, and initial as constructor arguments.
		return wx.SpinCtrl, {"min": kwargs["min"], "max": kwargs["max"], "initial": int(kwargs["value"])}

	def get_value_from_control(self, control: wx.Control) -> int:
		assert isinstance(control, wx.SpinCtrl)
		return control.GetValue()

	def set_value_to_control(self, control: wx.Control, value: Any, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.SpinCtrl)
		try:
			control.SetValue(int(value))
		except (ValueError, TypeError):
			control.SetValue(spec.get("default", control.GetMin()))

	def bind_event(self, control: wx.Control, callback: Callable[[wx.Event], None]) -> None:
		assert isinstance(control, wx.SpinCtrl)
		# The EVT_SPINCTRL event triggers when the value changes.
		control.Bind(wx.EVT_SPINCTRL, callback)
		# Also bind the text event to respond to direct input.
		control.Bind(wx.EVT_TEXT, callback)

	def load_from_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.SpinCtrl)
		value = config_section.get(spec["id"], spec.get("default"))
		self.set_value_to_control(control, value, spec)

	def save_to_config(self, control: wx.Control, config_section: ConfigSection, spec: ConfigSpec) -> None:
		assert isinstance(control, wx.SpinCtrl)
		config_section[spec["id"]] = self.get_value_from_control(control)
