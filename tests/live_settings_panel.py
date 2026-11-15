"""Build the real wx settings controls using an installed NVDA GUI library.

This uses an in-memory NVDA configuration, never the user's running profile.
Run with Python 3.13 matching the installed NVDA runtime.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
from pathlib import Path
import sys
import time
import types
from unittest import mock


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--nvda-dir", type=Path, default=Path(r"C:\Program Files\NVDA"))
	parser.add_argument("--language", choices=("en", "pl"), required=True)
	parser.add_argument("--control-center", action="store_true", help="Also exercise actual control-center widgets with an in-memory controller")
	args = parser.parse_args()
	nvda = args.nvda_dir.resolve()
	dll_directory = os.add_dll_directory(str(nvda))
	sys.path[:0] = [str(nvda / "library.zip"), str(nvda)]
	import wx

	class Configuration(dict):
		spec = {}

	config = types.ModuleType("config")
	config.conf = Configuration()
	addon_handler = types.ModuleType("addonHandler")
	def host_init_translation():
		# NVDA installs '_' directly in the caller module, not in builtins.
		inspect.currentframe().f_back.f_globals["_"] = lambda message: message
	addon_handler.initTranslation = host_init_translation
	gui = types.ModuleType("gui")
	gui.__path__ = [str(nvda / "library.zip" / "gui")]
	settings_dialogs = types.ModuleType("gui.settingsDialogs")
	settings_dialogs.SettingsPanel = wx.Panel
	root = Path(__file__).resolve().parents[1]
	global_plugins = types.ModuleType("globalPlugins")
	global_plugins.__path__ = []
	package = types.ModuleType("globalPlugins.xmplayAccessibility")
	package.__path__ = [str(root / "addon/globalPlugins/xmplayAccessibility")]
	sys.modules.update({
		"config": config, "addonHandler": addon_handler, "gui": gui,
		"gui.settingsDialogs": settings_dialogs, "globalPlugins": global_plugins,
		"globalPlugins.xmplayAccessibility": package,
	})
	gui.guiHelper = importlib.import_module("gui.guiHelper")
	configuration = importlib.import_module("globalPlugins.xmplayAccessibility.configuration")
	config.conf[configuration.CONFIG_SECTION] = dict(configuration.DEFAULTS)
	config.conf[configuration.CONFIG_SECTION]["interfaceLanguage"] = args.language
	settings = importlib.import_module("globalPlugins.xmplayAccessibility.settingsPanel")
	app = wx.App(False)
	frame = wx.Frame(None)
	center = None
	try:
		panel = settings.XMPlaySettingsPanel(frame)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.makeSettings(sizer)
		panel.SetSizer(sizer)
		choices = list(panel._languageChoice.GetItems())
		expected = ["Język systemu (domyślnie)", "Angielski", "Polski"] if args.language == "pl" else ["System language (default)", "English", "Polish"]
		assert choices == expected, choices
		assert panel._languageChoice.GetSelection() == (2 if args.language == "pl" else 1)
		assert len(panel._controls) == 9
		assert all(control.GetLabel() for control in panel._controls.values())
		panel._controls["showUsageHints"].SetValue(False)
		panel._update_hint_visibility()
		assert not panel._usageHint.IsShown() and not panel._restartHint.IsShown()
		panel.onSave()
		assert not config.conf[configuration.CONFIG_SECTION]["showUsageHints"]
		panel._on_restore_defaults(None)
		assert panel._usageHint.IsShown() and panel._restartHint.IsShown()
		assert panel._languageChoice.GetSelection() == 0
		panel.onSave()
		assert config.conf[configuration.CONFIG_SECTION]["interfaceLanguage"] == "system"
		assert config.conf[configuration.CONFIG_SECTION]["showUsageHints"]
		if args.control_center:
			config.conf[configuration.CONFIG_SECTION]["interfaceLanguage"] = args.language
			config.conf[configuration.CONFIG_SECTION]["showUsageHints"] = False
			localization = importlib.import_module("globalPlugins.xmplayAccessibility.localization")
			localization.invalidate_translation_cache()
			app_modules = types.ModuleType("appModules")
			app_modules.__path__ = []
			player_package = types.ModuleType("appModules.xmplay")
			player_package.__path__ = [str(root / "addon/appModules/xmplay")]
			ui = types.ModuleType("ui")
			ui.message = mock.Mock()
			sys.modules.update({"appModules": app_modules, "appModules.xmplay": player_package, "ui": ui})
			dialogs = importlib.import_module("appModules.xmplay.dialogs")
			backend = importlib.import_module("appModules.xmplay.backend")
			controller = mock.Mock()
			controller.status.return_value = backend.Status(1, "Fixture", 1000, 120, 50, 0, 0, 1, 44, 128, 2)
			controller.get_playlist.return_value = [backend.Track(0, "Fixture", "fixture.wav")]
			controller.playlist_position.return_value = 0
			center = dialogs.ControlCenterDialog(frame, controller)
			deadline = time.monotonic() + 2
			while center._playlist_loading and time.monotonic() < deadline:
				app.Yield()
				time.sleep(0.005)
			assert not center._playlist_loading
			assert center.playlist.GetCount() == 1 and "Fixture" in center.playlist.GetString(0)
			assert all(control.GetLabel() for control in center._operation_controls)
			assert center.status.GetName() == localization.translate("Playback status")
			assert center.search.GetDescriptiveText() == ""
			assert center.GetTitle() == localization.translate("XMPlay accessible control center")
			center._on_play_selected(None)
			center._on_play_selected(None)
			while center._operation_pending and time.monotonic() < deadline:
				app.Yield()
				time.sleep(0.005)
			assert not center._operation_pending
			controller.play_track.assert_called_once()
			assert all(control.IsEnabled() for control in center._operation_controls)
			destruction_events = []
			def observe_destruction(event):
				destruction_events.append(event.GetEventObject() is center)
				event.Skip()
			center.Bind(wx.EVT_WINDOW_DESTROY, observe_destruction)
			center.Destroy()  # Also test host-driven destruction rather than just Close.
			wx.CallLater(30, app.ExitMainLoop)
			app.MainLoop()
			assert center._closed and center._cancel_event.is_set(), f"destroy events={destruction_events}, native_alive={bool(center)}"
			center = None
		print(json.dumps(dict(language=args.language, choices=choices, controls=9, hint_toggle_and_defaults=True, control_center=bool(args.control_center), wx=wx.version()), ensure_ascii=True))
	finally:
		if center:
			center.Destroy()
		frame.Destroy()
		app.ProcessPendingEvents()
		dll_directory.close()


if __name__ == "__main__":
	main()
