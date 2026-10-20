from __future__ import annotations

import inspect
import gettext
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "addon" / "appModules" / "xmplay"


def load_dialogs_module(translator=None):
	addon_handler = types.ModuleType("addonHandler")
	def init_translation():
		inspect.currentframe().f_back.f_globals["_"] = lambda value: value
	addon_handler.initTranslation = init_translation
	ui = types.ModuleType("ui")
	wx = types.ModuleType("wx")
	wx.Dialog = type("Dialog", (object,), {})
	wx.FileDropTarget = type("FileDropTarget", (object,), {})
	configuration = types.ModuleType("globalPlugins.xmplayAccessibility.configuration")
	configuration.get_setting = lambda key: True
	localization = types.ModuleType("globalPlugins.xmplayAccessibility.localization")
	localization._ = translator or (lambda value: value)
	global_plugins = types.ModuleType("globalPlugins")
	global_plugins.__path__ = []
	global_plugin_package = types.ModuleType("globalPlugins.xmplayAccessibility")
	global_plugin_package.__path__ = []
	app_modules = types.ModuleType("appModules")
	app_modules.__path__ = []
	package = types.ModuleType("appModules.xmplay")
	package.__path__ = [str(PACKAGE_PATH)]

	backend_spec = importlib.util.spec_from_file_location(
		"appModules.xmplay.backend",
		PACKAGE_PATH / "backend.py",
	)
	backend = importlib.util.module_from_spec(backend_spec)
	assert backend_spec.loader

	stubs = {
		"addonHandler": addon_handler,
		"ui": ui,
		"wx": wx,
		"globalPlugins": global_plugins,
		"globalPlugins.xmplayAccessibility": global_plugin_package,
		"globalPlugins.xmplayAccessibility.configuration": configuration,
		"globalPlugins.xmplayAccessibility.localization": localization,
		"appModules": app_modules,
		"appModules.xmplay": package,
		"appModules.xmplay.backend": backend,
	}
	with mock.patch.dict(sys.modules, stubs):
		backend_spec.loader.exec_module(backend)
		dialogs_spec = importlib.util.spec_from_file_location(
			"appModules.xmplay.dialogs",
			PACKAGE_PATH / "dialogs.py",
		)
		dialogs = importlib.util.module_from_spec(dialogs_spec)
		assert dialogs_spec.loader
		sys.modules[dialogs_spec.name] = dialogs
		dialogs_spec.loader.exec_module(dialogs)
	return backend, dialogs


class PlaybackFormattingTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.backend, cls.dialogs = load_dialogs_module()

	def status(self):
		return self.backend.Status(
			state=self.backend.PLAYBACK_PLAYING,
			title="Artist - Title.mp3",
			position_ms=19800,
			length_seconds=194,
			volume_percent=42,
			balance_percent=0,
			playlist_position=4,
			playlist_length=20,
			sample_rate_khz=48,
			bitrate_kbps=320,
			channels=2,
		)

	def test_focus_summary_is_labelled_and_has_no_redundant_prefix(self):
		self.assertEqual(
			self.dialogs.format_focus_status(self.status()),
			"Track: Artist - Title.mp3. State: Playing. Elapsed: 0:19. "
			"Remaining: 2:54. Total duration: 3:14",
		)

	def test_full_status_splits_elapsed_remaining_and_total_time(self):
		text = self.dialogs.format_status(self.status())
		self.assertIn("Elapsed: 0:19\r\nRemaining: 2:54\r\nTotal duration: 3:14", text)
		self.assertNotIn("Position:", text)

	def test_backend_error_parameters_are_translated_before_formatting(self):
		error = self.backend.XMPlayError("XMPlay did not answer control command {command}", command=80)
		with mock.patch.object(self.dialogs, "_", side_effect=lambda text: {
			"XMPlay did not answer control command {command}": "XMPlay nie odpowiedział na polecenie sterujące {command}",
		}.get(text, text)):
			self.assertEqual(self.dialogs.format_error(error), "XMPlay nie odpowiedział na polecenie sterujące 80")

	def test_selected_polish_language_survives_nvda_host_initialization(self):
		catalog = gettext.translation("nvda", localedir=ROOT / "addon/locale", languages=["pl"])
		backend, dialogs = load_dialogs_module(catalog.gettext)
		self.assertEqual(dialogs.state_text(backend.PLAYBACK_PLAYING), "Odtwarzanie")
		error = backend.XMPlayError("XMPlay did not answer control command {command}", command=80)
		self.assertEqual(dialogs.format_error(error), "XMPlay nie odpowiedział na polecenie sterujące 80")


if __name__ == "__main__":
	unittest.main()
