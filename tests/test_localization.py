from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LOCALIZATION_PATH = (
	ROOT
	/ "addon"
	/ "globalPlugins"
	/ "xmplayAccessibility"
	/ "localization.py"
)


def load_localization_module():
	global_plugins = types.ModuleType("globalPlugins")
	global_plugins.__path__ = []
	package = types.ModuleType("globalPlugins.xmplayAccessibility")
	package.__path__ = [str(LOCALIZATION_PATH.parent)]
	configuration = types.ModuleType("globalPlugins.xmplayAccessibility.configuration")
	configuration.LANGUAGE_ENGLISH = "en"
	configuration.LANGUAGE_POLISH = "pl"
	configuration.LANGUAGE_SYSTEM = "system"
	configuration.get_interface_language = lambda: "system"
	name = "globalPlugins.xmplayAccessibility.localization"
	spec = importlib.util.spec_from_file_location(name, LOCALIZATION_PATH)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader
	with mock.patch.dict(
		sys.modules,
		{
			"globalPlugins": global_plugins,
			"globalPlugins.xmplayAccessibility": package,
			"globalPlugins.xmplayAccessibility.configuration": configuration,
			name: module,
		},
	):
		spec.loader.exec_module(module)
	return module


class LocalizationTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.module = load_localization_module()

	def test_explicit_language_ignores_system_language(self):
		self.assertEqual(self.module.resolve_language("en", "pl-PL"), "en")
		self.assertEqual(self.module.resolve_language("pl", "en-US"), "pl")

	def test_system_language_selects_polish_or_english(self):
		self.assertEqual(self.module.resolve_language("system", "pl-PL"), "pl")
		self.assertEqual(self.module.resolve_language("system", "en-US"), "en")
		self.assertEqual(self.module.resolve_language("system", "de-DE"), "en")

	def test_unknown_saved_value_falls_back_to_english(self):
		self.assertEqual(self.module.resolve_language("unknown", "pl-PL"), "en")

	def test_selected_catalog_is_used_for_runtime_messages(self):
		with mock.patch.object(self.module, "get_interface_language", return_value="pl"):
			self.module.invalidate_translation_cache()
			self.assertEqual(self.module.translate("English"), "Angielski")
		with mock.patch.object(self.module, "get_interface_language", return_value="en"):
			self.module.invalidate_translation_cache()
			self.assertEqual(self.module.translate("English"), "English")


if __name__ == "__main__":
	unittest.main()
