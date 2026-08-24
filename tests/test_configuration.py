from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


CONFIGURATION_PATH = (
	Path(__file__).resolve().parents[1]
	/ "addon"
	/ "globalPlugins"
	/ "xmplayAccessibility"
	/ "configuration.py"
)


class FakeConfiguration(dict):
	def __init__(self):
		super().__init__()
		self.spec = {}


class ConfigurationTest(unittest.TestCase):
	def _load_module(self):
		fake_config = types.ModuleType("config")
		fake_config.conf = FakeConfiguration()
		spec = importlib.util.spec_from_file_location("xmplay_configuration_test", CONFIGURATION_PATH)
		module = importlib.util.module_from_spec(spec)
		assert spec.loader
		with mock.patch.dict(sys.modules, {"config": fake_config}):
			sys.modules[spec.name] = module
			spec.loader.exec_module(module)
		return module, fake_config.conf

	def test_all_options_default_to_enabled(self):
		module, fake_conf = self._load_module()
		self.assertEqual(len(module.DEFAULTS), 8)
		self.assertTrue(all(module.DEFAULTS.values()))
		self.assertIn("announceFocusSummary", module.DEFAULTS)
		self.assertNotIn("announceWelcome", module.DEFAULTS)
		self.assertEqual(set(fake_conf.spec[module.CONFIG_SECTION]), set(module.DEFAULTS))

	def test_get_setting_uses_current_nvda_profile(self):
		module, fake_conf = self._load_module()
		fake_conf[module.CONFIG_SECTION] = dict(module.DEFAULTS)
		fake_conf[module.CONFIG_SECTION]["announceVolumeChanges"] = False
		self.assertFalse(module.get_setting("announceVolumeChanges"))


if __name__ == "__main__":
	unittest.main()
