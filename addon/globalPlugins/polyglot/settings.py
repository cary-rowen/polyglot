# -*- coding: utf-8 -*-

import addonHandler
import wx
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel
from . import config
from . import engine_manager
from .cache import TranslationCache
from . import ui_factory
from collections import OrderedDict
from logHandler import log
from typing import Dict, Any

addonHandler.initTranslation()

class TranslationSettingsPanel(SettingsPanel):
    title = _("Polyglot")

    def __init__(self, parent):
        self.engines = OrderedDict((e.id, e) for e in engine_manager.get_all_engines())
        self.cache = TranslationCache()
        self.ui_model: Dict[str, Any] = {}
        
        self.dynamic_controls: Dict[str, Dict[str, Any]] = {} 
        self.engine_panels_cache: Dict[str, wx.Panel] = {}
        self.active_engine_panel: wx.Panel = None
        
        # --- DEBOUNCING STRATEGY: Timer for smooth engine switching ---
        self._engine_switch_timer: wx.CallLater = None
        
        super().__init__(parent)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

    def makeSettings(self, sizer):
        sHelper = guiHelper.BoxSizerHelper(self, sizer=sizer)

        self.engine_choice = sHelper.addLabeledControl(_("Translation &engine:"), wx.Choice)
        sHelper.addItem(wx.StaticLine(self, style=wx.LI_HORIZONTAL))

        self.engine_panel_container_sizer = wx.BoxSizer(wx.VERTICAL)
        sHelper.addItem(self.engine_panel_container_sizer, proportion=1, flag=wx.EXPAND)

        sHelper.addItem(wx.StaticLine(self, style=wx.LI_HORIZONTAL))

        common_box = wx.StaticBox(self, label=_("Common Settings"))
        common_sizer = wx.StaticBoxSizer(common_box, wx.VERTICAL)
        common_sHelper = guiHelper.BoxSizerHelper(self, sizer=common_sizer)

        self.copy_result_checkbox = common_sHelper.addItem(wx.CheckBox(self, label=_("Copy manual translation results to clipboard")))
        self.clear_cache_button = common_sHelper.addItem(wx.Button(self, label=_("Clear Cache")))
        sHelper.addItem(common_sizer, flag=wx.EXPAND)
        
        self.engine_choice.Bind(wx.EVT_CHOICE, self.on_engine_changed)
        self.copy_result_checkbox.Bind(wx.EVT_CHECKBOX, self.on_any_control_changed)
        self.clear_cache_button.Bind(wx.EVT_BUTTON, self.on_clear_cache)

        self._populate_initial_state()
        
    def _on_destroy(self, event):
        """Ensure the timer is stopped when the panel is destroyed."""
        if self._engine_switch_timer and self._engine_switch_timer.IsRunning():
            self._engine_switch_timer.Stop()
        event.Skip()

    def onSave(self):
        conf = config.get_config()
        self._sync_model_from_ui()
        
        conf['engine'] = self.ui_model['engine']
        conf['copyResult'] = self.ui_model['copyResult']

        for engine_id, controls in self.dynamic_controls.items():
            if not controls: continue
            if engine_id not in conf['engines']:
                conf['engines'][engine_id] = {}
            engine_conf = conf['engines'][engine_id]
            for cid, info in controls.items():
                info['handler'].save_to_config(info['control'], engine_conf, info['spec'])


    def on_engine_changed(self, event):
        """Debounce the engine switch event to avoid stutter on rapid changes."""
        # If a switch is already scheduled, cancel it.
        if self._engine_switch_timer and self._engine_switch_timer.IsRunning():
            self._engine_switch_timer.Stop()
        
        # Schedule the actual switch to happen after a short delay (200ms).
        self._engine_switch_timer = wx.CallLater(200, self._perform_engine_switch)

    def _perform_engine_switch(self):
        """The actual logic that switches the panel, called by the timer."""
        self.Freeze()
        try:
            self._switch_engine_panel()
        finally:
            self.Thaw()

    def on_any_control_changed(self, event=None):
        if event:
            event.Skip()
            
        self._sync_model_from_ui()
        
        engine = self._get_selected_engine()
        if not engine: return
        try:
            ui_states = engine.get_ui_states(self.ui_model)
            self._apply_ui_states(ui_states)
        except Exception as e:
            log.error(f"Error executing get_ui_states for engine '{engine.id}'.", exc_info=True)

    def _populate_initial_state(self):
        self.Freeze()
        try:
            conf = config.get_config()
            for engine_id, engine in self.engines.items():
                self.engine_choice.Append(engine.name, engine_id)
            engine_id = conf.get('engine', list(self.engines.keys())[0] if self.engines else None)
            if engine_id and engine_id in self.engines:
                self.engine_choice.SetStringSelection(self.engines[engine_id].name)

            self.copy_result_checkbox.SetValue(conf.get('copyResult', True))

            self._switch_engine_panel()
        finally:
            self.Thaw()

    def _switch_engine_panel(self):
        """Show the panel for the selected engine, creating it if necessary."""
        engine_id = self._get_selected_engine_id()
        if not engine_id: return

        if self.active_engine_panel:
            self.active_engine_panel.Hide()

        if engine_id in self.engine_panels_cache:
            panel = self.engine_panels_cache[engine_id]
            panel.Show()
            self.active_engine_panel = panel
        else:
            panel = self._create_engine_panel(engine_id)
            self.engine_panels_cache[engine_id] = panel
            self.engine_panel_container_sizer.Add(panel, 1, wx.EXPAND)
            self.active_engine_panel = panel

        self.on_any_control_changed()
        self.Layout()

    def _create_engine_panel(self, engine_id):
        """Create and populate the settings panel for a specific engine ONCE."""
        panel = wx.Panel(self)
        engine = self.engines.get(engine_id)
        if not engine: return panel

        engine_conf = config.get_config()['engines'].get(engine.id, {})
        config_spec_list = engine.get_config_spec()
        
        self.dynamic_controls[engine_id] = {}

        box = wx.StaticBox(panel, label=_("Current Engine Settings"))
        container_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        if not config_spec_list:
            no_settings_text = wx.StaticText(panel, label=_("This engine requires no additional configuration."))
            container_sizer.Add(no_settings_text, 0, wx.ALL, 5)
            panel.SetSizer(container_sizer)
            return panel

        grid_sizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        grid_sizer.AddGrowableCol(1)

        for spec in config_spec_list:
            handler = ui_factory.get_control_handler(spec['type'])
            label_control, control = handler.create_control_pair(panel, spec)
            
            handler.load_from_config(control, engine_conf, spec)
            handler.bind_event(control, self.on_any_control_changed)

            if label_control is None:
                grid_sizer.Add(control, 1, wx.EXPAND)
                grid_sizer.AddSpacer(0)
            else:
                grid_sizer.Add(label_control, 0, wx.ALIGN_CENTER_VERTICAL)
                grid_sizer.Add(control, 1, wx.EXPAND)

            self.dynamic_controls[engine_id][spec['id']] = {
                'control': control, 'handler': handler, 'spec': spec,
                'label_control': label_control
            }
        
        container_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(container_sizer)
        return panel

    def _apply_ui_states(self, ui_states: Dict[str, Dict[str, Any]]):
        engine_id = self._get_selected_engine_id()
        if not engine_id or engine_id not in self.dynamic_controls:
            return

        for cid, states in ui_states.items():
            info = self.dynamic_controls[engine_id].get(cid)
            if not info: continue
            handler = info['handler']
            for prop, value in states.items():
                handler.update_control_state(
                    info['control'], info['label_control'], prop, value
                )
        
        self.Layout()

    def _sync_model_from_ui(self):
        engine_id = self._get_selected_engine_id()
        if not engine_id: return

        self.ui_model = {
            'engine': engine_id,
            'copyResult': self.copy_result_checkbox.IsChecked(),
        }
        
        if engine_id in self.dynamic_controls:
            for cid, info in self.dynamic_controls[engine_id].items():
                self.ui_model[cid] = info['handler'].get_value_from_control(info['control'])

    def onPanelActivated(self):
        super().onPanelActivated()
        self._update_cache_button()

    def _get_selected_engine_id(self) -> str | None:
        selection = self.engine_choice.GetSelection()
        if selection == wx.NOT_FOUND: return None
        return self.engine_choice.GetClientData(selection)

    def _get_selected_engine(self) -> Any | None:
        engine_id = self._get_selected_engine_id()
        if not engine_id: return None
        return self.engines.get(engine_id)

    def on_clear_cache(self, event):
        self.cache.clear()
        self._update_cache_button()
        wx.CallAfter(self.clear_cache_button.SetFocus)

    def _update_cache_button(self):
        self.clear_cache_button.SetLabel(_("Clear Cache (Items: {})").format(self.cache.get_item_count()))