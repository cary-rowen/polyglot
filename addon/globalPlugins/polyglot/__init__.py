# -*- coding: utf-8 -*-


import addonHandler
import api
import config
import globalPluginHandler
import globalVars
import gui
import textInfos
import tones
import ui
import wx
from configobj import ConfigObj, Section
from keyboardHandler import KeyboardInputGesture
from logHandler import log
from scriptHandler import script

from .app.manager import TranslationManager
from .app.speech_filter import SpeechFilter
from .common.config import CONF_SECTION
from .configspec import config_spec
from .services import engine_manager
from .views import factory as ui_factory
from .views import settings

addonHandler.initTranslation()


def _build_final_configspec() -> dict[str, ConfigObj]:
	"""
	Scans all available engines, builds their dynamic config specs,
	and merges them with the static base spec.
	This function acts as the "composition root" for configuration,
	coordinating between services and views.

	Returns:
		A complete configspec dictionary for the entire addon.
	"""
	final_spec = config_spec.copy()
	engines_spec_section = final_spec["engines"]
	all_engines = engine_manager.get_all_engines()
	for engine in all_engines:
		engine_id = engine.id
		engine_spec_list = engine.get_config_spec()
		if not engine_spec_list:
			continue
		if engine_id not in engines_spec_section:
			engines_spec_section[engine_id] = {}
		engine_section: Section = engines_spec_section[engine_id]
		for item in engine_spec_list:
			try:
				handler = ui_factory.get_control_handler(item["type"])
				default_val = handler.format_config_default(item["default"])
				spec_str = f"{item['id']} = {handler.config_type}(default={default_val})"
				engine_section.merge(ConfigObj([spec_str], list_values=False))
			except ValueError:
				log.warning(f"Engine '{engine_id}' has an unknown control type '{item['type']}'. Skipping.")
	return {CONF_SECTION: final_spec}


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Polyglot")

	def __init__(self):
		super().__init__()
		# Let this module build the complete, dynamic config spec.
		final_spec = _build_final_configspec()
		# Merge this final spec into NVDA's configuration.
		config.conf.spec.merge(final_spec)
		self.manager = TranslationManager()
		self.speech_filter = SpeechFilter(self.manager)
		self.speech_filter.register()
		self.is_layer_active = False
		if not globalVars.appArgs.secure:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(settings.TranslationSettingsPanel)

	def terminate(self):
		self.manager.terminate_all_tasks()
		self.speech_filter.unregister()
		if not globalVars.appArgs.secure:
			if settings.TranslationSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
				gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(
					settings.TranslationSettingsPanel
				)
		super().terminate()

	def getScript(self, gesture: KeyboardInputGesture) -> None:
		if not self.is_layer_active:
			return super().getScript(gesture)
		script = super().getScript(gesture)
		if not script:
			script = self.script_layer_error

		def wrapped_script(g):
			try:
				script(g)
			finally:
				self.finish_layer()

		return wrapped_script

	def finish_layer(self):
		self.is_layer_active = False
		self.clearGestureBindings()
		self.bindGestures(self.__gestures)

	def script_layer_error(self, gesture: KeyboardInputGesture) -> None:
		tones.beep(120, 100)

	@script(description=_("Enter translation command layer"))
	def script_layer_entry(self, gesture: KeyboardInputGesture) -> None:
		if self.is_layer_active:
			self.script_layer_error(gesture)
			return
		self.bindGestures(self.__layer_gestures)
		self.is_layer_active = True
		tones.beep(100, 10)

	def _get_selected_text(self) -> str | None:
		"""Gets selected text, handling errors. Returns text or None."""
		try:
			info = api.getCaretObject().makeTextInfo(textInfos.POSITION_SELECTION)
			if not info or info.isCollapsed:
				ui.message(_("Nothing selected"))
				return None
			return info.text
		except NotImplementedError:
			log.warning("Failed to get selected text from the current object.", exc_info=True)
			ui.message(_("Cannot get selected text from the current object"))
			return None

	def _execute_translation(self, text: str, reverse: bool, show_status: bool) -> None:
		"""The single execution engine for all translation requests."""
		if not reverse:
			self.manager.request_translation(text, is_manual=True, show_status=show_status)
		else:
			new_from, new_to, error_message = self.manager.get_reverse_languages()
			if error_message:
				ui.message(error_message)
				return
			self.manager.request_translation(
				text,
				is_manual=True,
				show_status=show_status,
				lang_from=new_from,
				lang_to=new_to,
			)

	@script(description=_("Swap source and target languages"))
	def script_swapLanguages(self, gesture: KeyboardInputGesture) -> None:
		log.info("Script 'swapLanguages' triggered.")
		success, message = self.manager.swap_languages()
		ui.message(message)
		if not success:
			tones.beep(220, 120)
			wx.CallAfter(
				gui.mainFrame.popupSettingsDialog,
				gui.settingsDialogs.NVDASettingsDialog,
				settings.TranslationSettingsPanel,
			)

	@script(description=_("Announce current languages"))
	def script_announceLanguages(self, gesture: KeyboardInputGesture) -> None:
		announcement = self.manager.get_current_language_announcement()
		ui.message(announcement)

	@script(description=_("Copy last translation to clipboard"))
	def script_copyLastResult(self, gesture: KeyboardInputGesture) -> None:
		last_result = self.manager.last_translation
		if last_result:
			_unused = api.copyToClip(last_result, notify=True)
		else:
			ui.message(_("No translation result to copy"))

	@script(description=_("Open settings"))
	def script_openSettings(self, gesture: KeyboardInputGesture) -> None:
		wx.CallAfter(
			gui.mainFrame.popupSettingsDialog,
			gui.settingsDialogs.NVDASettingsDialog,
			settings.TranslationSettingsPanel,
		)

	@script(description=_("Toggle auto-translation"))
	def script_toggleAutoTranslate(self, gesture: KeyboardInputGesture) -> None:
		new_state = self.manager.toggle_auto_translate()
		ui.message(_("Auto-translation enabled") if new_state else _("Auto-translation disabled"))

	@script(description=_("Clear cache"))
	def script_clearCache(self, gesture: KeyboardInputGesture) -> None:
		self.manager.clear_cache()
		ui.message(_("Cache cleared"))

	@script(description=_("Translate selection"))
	def script_translateSelection(self, gesture: KeyboardInputGesture) -> None:
		if text := self._get_selected_text():
			self._execute_translation(text, reverse=False, show_status=True)

	@script(description=_("Translate selection (reversed direction)"))
	def script_translateReverseSelection(self, gesture: KeyboardInputGesture) -> None:
		if text := self._get_selected_text():
			self._execute_translation(text, reverse=True, show_status=True)

	@script(description=_("Translate clipboard"))
	def script_translateClipboard(self, gesture: KeyboardInputGesture) -> None:
		if not (text := api.getClipData()):
			ui.message(_("Clipboard is empty"))
			return
		self._execute_translation(text, reverse=False, show_status=True)

	@script(description=_("Translate clipboard (reversed direction)"))
	def script_translateReverseClipboard(self, gesture: KeyboardInputGesture) -> None:
		if not (text := api.getClipData()):
			ui.message(_("Clipboard is empty"))
			return
		self._execute_translation(text, reverse=True, show_status=True)

	@script(description=_("Translate last spoken text"))
	def script_translateLastSpoken(self, gesture: KeyboardInputGesture) -> None:
		if not (text := self.speech_filter.last_spoken_text):
			ui.message(_("No last spoken text"))
			return
		self._execute_translation(text, reverse=False, show_status=True)

	@script(description=_("Translate last spoken text (reversed direction)"))
	def script_translateReverseLastSpoken(self, gesture: KeyboardInputGesture) -> None:
		if not (text := self.speech_filter.last_spoken_text):
			ui.message(_("No last spoken text"))
			return
		self._execute_translation(text, reverse=True, show_status=True)

	@script(description=_("Show command layer help"))
	def script_layerHelp(self, gesture: KeyboardInputGesture) -> None:
		ui.message(self._generate_layer_help_text())

	def _generate_layer_help_text(self) -> str:
		help_items: list[str] = []
		for gesture, script_name in self.__layer_gestures.items():
			_source, key_display_name = KeyboardInputGesture.getDisplayTextForIdentifier(gesture)
			method = getattr(self, f"script_{script_name}")
			description = method.__doc__ or script_name
			help_items.append(f"{key_display_name}: {description}")
		help_items.sort(key=lambda item: (item.startswith("h:"), item))
		return "\n".join(help_items)

	__gestures = {"kb:NVDA+Shift+T": "layer_entry"}
	__layer_gestures = {
		"kb:t": "translateSelection",
		"kb:shift+t": "translateReverseSelection",
		"kb:b": "translateClipboard",
		"kb:shift+b": "translateReverseClipboard",
		"kb:l": "translateLastSpoken",
		"kb:shift+l": "translateReverseLastSpoken",
		"kb:s": "swapLanguages",
		"kb:a": "announceLanguages",
		"kb:c": "copyLastResult",
		"kb:v": "toggleAutoTranslate",
		"kb:o": "openSettings",
		"kb:x": "clearCache",
		"kb:h": "layerHelp",
	}
