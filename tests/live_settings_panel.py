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
import types


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--nvda-dir", type=Path, default=Path(r"C:\Program Files\NVDA"))
	parser.add_argument("--language", choices=("en", "pl"), required=True)
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
		print(json.dumps(dict(language=args.language, choices=choices, controls=9, hint_toggle_and_defaults=True, wx=wx.version()), ensure_ascii=True))
	finally:
		frame.Destroy()
		app.ProcessPendingEvents()
		dll_directory.close()


if __name__ == "__main__":
	main()
