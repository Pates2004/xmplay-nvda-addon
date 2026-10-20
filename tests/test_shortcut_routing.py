from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
from unittest import TestCase, mock

from test_formatting import load_dialogs_module


def load_app_module():
	backend, dialogs = load_dialogs_module()
	modules = {name: types.ModuleType(name) for name in (
		"addonHandler", "api", "appModuleHandler", "core", "gui", "inputCore",
		"keyboardHandler", "logHandler", "ui", "winUser", "wx",
	)}
	modules["addonHandler"].initTranslation = lambda: None
	modules["appModuleHandler"].AppModule = type("Base", (), {"getScript": lambda self, g: self.script_nativeShortcut})
	modules["logHandler"].log = mock.Mock()
	modules["inputCore"].normalizeGestureIdentifier = lambda value: value
	modules["ui"].message = mock.Mock()
	configuration = types.ModuleType("globalPlugins.xmplayAccessibility.configuration")
	configuration.get_setting = lambda key: True
	localization = types.ModuleType("globalPlugins.xmplayAccessibility.localization")
	localization._ = lambda value: value
	modules.update({
		"globalPlugins.xmplayAccessibility.configuration": configuration,
		"globalPlugins.xmplayAccessibility.localization": localization,
		"appModules.xmplay.backend": backend,
		"appModules.xmplay.dialogs": dialogs,
	})
	path = Path(__file__).resolve().parents[1] / "addon/appModules/xmplay/__init__.py"
	name = "appModules.xmplay"
	spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)])
	module = importlib.util.module_from_spec(spec)
	modules[name] = module
	with mock.patch.dict(sys.modules, modules):
		spec.loader.exec_module(module)
	return module


class ShortcutRoutingTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.module = load_app_module()

	def setUp(self):
		self.app = object.__new__(self.module.AppModule)
		self.app.controller = mock.Mock()
		self.app._native_shortcuts = {"kb:space": (80,), "kb:q": (516,)}
		self.app._report_native_shortcut = mock.Mock()
		self.gesture = mock.Mock(normalizedIdentifiers=["kb:space"])

	def test_space_in_options_is_not_an_addon_script(self):
		self.app.controller.can_handle_native_shortcuts.return_value = False
		self.assertIsNone(self.app.getScript(self.gesture))
		self.app.script_nativeShortcut(self.gesture)
		self.gesture.send.assert_called_once_with()
		self.app.controller.commands.assert_not_called()

	def test_reassigned_action_on_player_still_runs_and_reports_immediately(self):
		self.app.controller.can_handle_native_shortcuts.return_value = True
		self.gesture.normalizedIdentifiers = ["kb:q"]
		self.assertEqual(self.app.getScript(self.gesture), self.app.script_nativeShortcut)
		self.app.script_nativeShortcut(self.gesture)
		self.app.controller.commands.assert_called_once_with((516,))
		self.app._report_native_shortcut.assert_called_once_with((516,))
		self.gesture.send.assert_not_called()

	def test_uncertain_or_partial_execution_never_replays_a_toggle(self):
		self.app._native_shortcuts["kb:space"] = (516, 517)
		self.app.controller.commands.side_effect = self.module.XMPlayError("Timeout")
		self.app._show_error = mock.Mock()
		self.app.script_nativeShortcut(self.gesture)
		self.gesture.send.assert_not_called()
		self.app._show_error.assert_called_once()

	def test_failed_ini_reload_keeps_working_map_and_retries_same_mtime(self):
		self.app._shortcuts_mtime_ns = 1
		self.app._native_shortcut_identifiers = {"kb:space"}
		path = mock.Mock()
		path.stat.return_value.st_mtime_ns = 2
		self.app._shortcut_config_path = lambda: path
		self.app._shortcut_identifier = lambda binding: "kb:q"
		self.app.removeGestureBinding = mock.Mock()
		self.app.bindGesture = mock.Mock()
		binding = self.module.ShortcutBinding(516, 81, 0, 16, False)
		with mock.patch.object(self.module, "load_shortcuts", side_effect=[OSError("busy"), [binding]]) as load:
			self.app._reload_native_shortcuts()
			self.assertEqual(self.app._native_shortcuts["kb:space"], (80,))
			self.assertEqual(self.app._shortcuts_mtime_ns, 1)
			self.app._reload_native_shortcuts()
			self.assertEqual(self.app._native_shortcuts, {"kb:q": (516,)})
			self.assertEqual(load.call_count, 2)
