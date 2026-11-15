from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase, mock

from test_shortcut_routing import load_app_module


class FeedbackTest(TestCase):
	@classmethod
	def setUpClass(cls):
		cls.module = load_app_module()

	def setUp(self):
		self.app = object.__new__(self.module.AppModule)
		self.app.controller = mock.Mock()
		self.app._terminated = False
		self.app._help_announcement_counter = 0
		self.app._last_shortcut_check = self.module.time.monotonic()
		self.app._schedule_monitor = mock.Mock()
		self.app._is_xmplay_foreground = lambda: True
		self.status = self.module.Status(1, "Track", 10000, 180, 50, 0, 0, 10, 44, 128, 2)
		self.app._last_status = self.status
		self.module.ui.message.reset_mock()
		self.settings = {}
		self.setting_patch = mock.patch.object(self.module, "get_setting", side_effect=lambda key: self.settings.get(key, True))
		self.setting_patch.start()
		self.addCleanup(self.setting_patch.stop)

	def test_native_command_without_feedback_still_updates_monitor_baseline(self):
		self.settings["announceCommandFeedback"] = False
		self.app.controller.status.return_value = replace(self.status, volume_percent=51)
		self.app._report_native_shortcut((512,))
		self.app._poll()
		self.module.ui.message.assert_not_called()
		self.assertEqual(self.app._last_status.volume_percent, 51)

	def test_monitor_announces_all_enabled_simultaneous_changes(self):
		self.app.controller.status.return_value = replace(self.status, state=3, volume_percent=49, balance_percent=25)
		self.app._poll()
		self.module.ui.message.assert_called_once_with("Paused. Volume 49%. Balance 25% right")

	def test_multi_action_shortcut_reports_each_action_group(self):
		self.app.controller.status.return_value = replace(self.status, state=3, volume_percent=49)
		with mock.patch.object(self.module.core, "callLater", create=True) as later:
			self.app._report_native_shortcut((513, 80, 516))
			self.module.ui.message.assert_called_once_with("Volume 49%. Paused")
			self.assertTrue(later.called, "Effect feedback was dropped after the volume/playback report")

	def test_delayed_effect_feedback_is_silent_after_termination_or_focus_loss(self):
		self.app._terminated = True
		self.app._report_action_fallback(0, ["Equalizer toggled"])
		self.module.ui.message.assert_not_called()
		self.app._terminated = False
		self.app._is_xmplay_foreground = lambda: False
		self.app._report_action_fallback(0, ["Equalizer toggled"])
		self.module.ui.message.assert_not_called()

	def test_focus_refreshes_existing_main_window_summary(self):
		self.app.controller.status.return_value = replace(self.status, title="New track", position_ms=65000)
		obj = SimpleNamespace(windowClassName="XMPLAY-MAIN", name="Old track", description="Old", value="Raw")
		next_handler = mock.Mock()
		self.app.event_gainFocus(obj, next_handler)
		self.assertIn("New track", obj.name)
		self.assertIn("Elapsed: 1:05", obj.name)
		next_handler.assert_called_once_with()
