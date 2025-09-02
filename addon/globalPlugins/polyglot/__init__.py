# -*- coding: utf-8 -*-

import globalVars
import globalPluginHandler
import ui
import api
import addonHandler
import wx
import gui
import tones
import textInfos
from scriptHandler import script
from keyboardHandler import KeyboardInputGesture
from . import settings
from . import config
from .speech_filter import speech_filter_instance
from .core import manager as translation_manager
from logHandler import log

addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = _("Polyglot")

    def __init__(self):
        super().__init__()
        config.initialize()
        self.is_layer_active = False
        speech_filter_instance.register()
        if not globalVars.appArgs.secure:
            gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(settings.TranslationSettingsPanel)
        log.info("ModernTranslate plugin initialized successfully.")


    def terminate(self): # pyright: ignore[reportImplicitOverride]
        log.info("ModernTranslate plugin terminating...")
        translation_manager.terminate_all_tasks()
        speech_filter_instance.unregister()
        if not globalVars.appArgs.secure:
             if settings.TranslationSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses:
                 gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(settings.TranslationSettingsPanel)
        super().terminate()
        log.info("ModernTranslate plugin terminated.")

    def getScript(self, gesture):
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

    def script_layer_error(self, gesture):
        tones.beep(120, 100)

    @script(description=_("Enter translation command layer"))
    def script_layer_entry(self, gesture):
        if self.is_layer_active:
            self.script_layer_error(gesture)
            return
        self.bindGestures(self.__layer_gestures)
        self.is_layer_active = True
        tones.beep(100, 10)

    @script(description=_("Translate selection"))
    def script_translateSelection(self, gesture):
        log.info("Script 'translateSelection' triggered.")
        try:
            info = api.getCaretObject().makeTextInfo(textInfos.POSITION_SELECTION)
            if not info or info.isCollapsed:
                ui.message(_("Nothing selected"))
                return
            text = info.text
        except NotImplementedError:
            log.warning("Failed to get selected text from the current object.", exc_info=True)
            ui.message(_("Cannot get selected text from the current object"))
            return
        translation_manager.request_translation(text, is_manual=True, show_status=True)

    @script(description=_("Translate clipboard"))
    def script_translateClipboard(self, gesture):
        log.info("Script 'translateClipboard' triggered.")
        text = api.getClipData()
        translation_manager.request_translation(text, is_manual=True, show_status=True)

    @script(description=_("Swap source and target languages"))
    def script_swapLanguages(self, gesture):
        log.info("Script 'swapLanguages' triggered.")
        success, message = translation_manager.swap_languages()
        ui.message(message)
        if not success:
            tones.beep(220, 120)
            wx.CallAfter(gui.mainFrame.popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, settings.TranslationSettingsPanel)

    @script(description=_("Announce current languages"))
    def script_announceLanguages(self, gesture):
        announcement = translation_manager.get_current_language_announcement()
        ui.message(announcement)


    @script(description=_("Copy last translation to clipboard"))
    def script_copyLastResult(self, gesture):
        last_result = translation_manager.last_translation
        if last_result:
            api.copyToClip(last_result, notify=True)
        else:
            ui.message(_("No translation result to copy"))

    @script(description=_("Open settings"))
    def script_openSettings(self, gesture):
        wx.CallAfter(gui.mainFrame.popupSettingsDialog, gui.settingsDialogs.NVDASettingsDialog, settings.TranslationSettingsPanel)

    @script(description=_("Toggle auto-translation"))
    def script_toggleAutoTranslate(self, gesture):
        new_state = translation_manager.toggle_auto_translate()
        ui.message(_("Auto-translation enabled") if new_state else _("Auto-translation disabled"))

    @script(description=_("Translate last spoken text"))
    def script_translateLastSpoken(self, gesture):
        last_spoken = speech_filter_instance.last_spoken_text
        if last_spoken:
            translation_manager.request_translation(last_spoken, is_manual=True, show_status=False)
        else:
            ui.message(_("No last spoken text"))

    @script(description=_("Clear cache"))
    def script_clearCache(self, gesture):
        translation_manager.clear_cache()
        ui.message(_("Cache cleared"))

    @script(description=_("Show command layer help"))
    def script_layerHelp(self, gesture):
        ui.message(self._generate_layer_help_text())

    def _generate_layer_help_text(self) -> str:
        """
        Generate the command layer help string.
        """
        help_items = []
        for gesture, script_name in self.__layer_gestures.items():
            # Get the localized, user-friendly key name
            _source, key_display_name = KeyboardInputGesture.getDisplayTextForIdentifier(gesture)
            # Fetch the script method object.
            method = getattr(self, f'script_{script_name}')
            # Use the script's docstring (__doc__) as its description, falling back to the script name.
            description = method.__doc__ or script_name
            help_items.append(f"{key_display_name}: {description}")
        # Sort items for a consistent order, keeping help ('h') last.
        help_items.sort(key=lambda item: (item.startswith('h:'), item))
        return "\n".join(help_items)


    __gestures = { "kb:NVDA+Shift+T": "layer_entry" }
    __layer_gestures = {
        "kb:t": "translateSelection", "kb:b": "translateClipboard",
        "kb:s": "swapLanguages", "kb:a": "announceLanguages",
        "kb:c": "copyLastResult", "kb:l": "translateLastSpoken",
        "kb:v": "toggleAutoTranslate", "kb:o": "openSettings",
        "kb:x": "clearCache", "kb:h": "layerHelp",
    }
