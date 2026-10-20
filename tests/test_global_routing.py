from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


GLOBAL_PLUGIN_PATH = (
	Path(__file__).resolve().parents[1]
	/ "addon"
	/ "globalPlugins"
	/ "xmplayAccessibility"
	/ "__init__.py"
)


def load_global_plugin():
	addon_handler = types.ModuleType("addonHandler")
	addon_handler.initTranslation = lambda: None
	api = types.ModuleType("api")
	api.getFocusObject = mock.Mock()
	plugin_handler = types.ModuleType("globalPluginHandler")
	plugin_handler.GlobalPlugin = type("GlobalPlugin", (object,), {})
	gui = types.ModuleType("gui")
	gui.settingsDialogs = types.SimpleNamespace(
		NVDASettingsDialog=types.SimpleNamespace(categoryClasses=[]),
	)
	script_handler = types.ModuleType("scriptHandler")
	script_handler.script = lambda **kwargs: lambda function: function
	configuration = types.ModuleType("globalPlugins.xmplayAccessibility.configuration")
	configuration.ensure_config = lambda: None
	localization = types.ModuleType("globalPlugins.xmplayAccessibility.localization")
	localization._ = lambda value: value
	settings_panel = types.ModuleType("globalPlugins.xmplayAccessibility.settingsPanel")
	settings_panel.XMPlaySettingsPanel = type("XMPlaySettingsPanel", (object,), {})
	global_plugins = types.ModuleType("globalPlugins")
	global_plugins.__path__ = []
	name = "globalPlugins.xmplayAccessibility"
	spec = importlib.util.spec_from_file_location(
		name,
		GLOBAL_PLUGIN_PATH,
		submodule_search_locations=[str(GLOBAL_PLUGIN_PATH.parent)],
	)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader
	with mock.patch.dict(
		sys.modules,
		{
			"addonHandler": addon_handler,
			"api": api,
			"globalPluginHandler": plugin_handler,
			"gui": gui,
			"scriptHandler": script_handler,
			"globalPlugins": global_plugins,
			name: module,
			f"{name}.configuration": configuration,
			f"{name}.localization": localization,
			f"{name}.settingsPanel": settings_panel,
		},
	):
		spec.loader.exec_module(module)
	return module


class GlobalRoutingTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.module = load_global_plugin()

	def setUp(self):
		self.plugin = self.module.GlobalPlugin.__new__(self.module.GlobalPlugin)
		self.app_module = types.SimpleNamespace(
			appName="xmplay",
			controller=mock.Mock(),
			script_playPause=mock.Mock(),
			script_reportTime=mock.Mock(),
		)
		self.module.api.getFocusObject.reset_mock()
		self.module.api.getFocusObject.return_value = types.SimpleNamespace(
			appModule=self.app_module,
		)
		self.gesture = mock.Mock(identifiers=["kb:control+shift+space"])

	def test_playback_shortcut_passes_through_in_settings(self):
		self.app_module.controller.can_handle_native_shortcuts.return_value = False

		self.plugin._dispatch_to_xmplay("playPause", self.gesture)

		self.gesture.send.assert_called_once_with()
		self.app_module.script_playPause.assert_not_called()
		self.app_module.controller.can_handle_native_shortcuts.assert_called_once_with()

	def test_playback_shortcut_runs_in_player_window(self):
		self.app_module.controller.can_handle_native_shortcuts.return_value = True

		self.plugin._dispatch_to_xmplay("playPause", self.gesture)

		self.app_module.script_playPause.assert_called_once_with(self.gesture)
		self.gesture.send.assert_not_called()

	def test_time_report_remains_available_in_settings(self):
		self.app_module.controller.can_handle_native_shortcuts.return_value = False
		self.gesture.identifiers = ["kb:NVDA+shift+t"]

		self.plugin._dispatch_to_xmplay("reportTime", self.gesture)

		self.app_module.script_reportTime.assert_called_once_with(self.gesture)
		self.app_module.controller.can_handle_native_shortcuts.assert_not_called()
		self.gesture.send.assert_not_called()

	def test_ordinary_shortcut_passes_through_outside_xmplay(self):
		self.app_module.appName = "notepad"

		self.plugin._dispatch_to_xmplay("playPause", self.gesture)

		self.gesture.send.assert_called_once_with()
		self.app_module.script_playPause.assert_not_called()
		self.app_module.controller.can_handle_native_shortcuts.assert_not_called()


if __name__ == "__main__":
	unittest.main()
