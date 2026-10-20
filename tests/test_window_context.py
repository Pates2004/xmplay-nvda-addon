from __future__ import annotations

from unittest import TestCase, mock

from test_backend import backend


class WindowContextTest(TestCase):
	def allowed(self, foreground_class="XMPLAY-MAIN", focus_class="XMPLAY-MAIN", flags=0,
		process_id=123, enabled=True, info_ok=True):
		def process(hwnd, pointer):
			pointer._obj.value = process_id
			return 7

		def gui_info(thread, pointer):
			pointer._obj.hwndFocus = 20
			pointer._obj.flags = flags
			return info_ok

		def class_name(hwnd, buffer, size):
			buffer.value = focus_class if hwnd == 20 else foreground_class
			return len(buffer.value)

		with (
			mock.patch.object(backend._user32, "GetForegroundWindow", return_value=10),
			mock.patch.object(backend._user32, "GetWindowThreadProcessId", side_effect=process),
			mock.patch.object(backend._user32, "GetGUIThreadInfo", side_effect=gui_info),
			mock.patch.object(backend._user32, "GetAncestor", return_value=10),
			mock.patch.object(backend._user32, "IsWindowEnabled", return_value=enabled),
			mock.patch.object(backend._user32, "GetClassNameW", side_effect=class_name),
		):
			return backend.XMPlayController(123).can_handle_native_shortcuts()

	def test_main_player_and_skinned_panel_allow_native_feedback(self):
		self.assertTrue(self.allowed())
		self.assertTrue(self.allowed("XMPLAY-PANEL", "XMPLAY-PANEL"))

	def test_options_file_dialogs_and_information_windows_keep_their_keys(self):
		for window_class in ("#32770", "XMPLAY-INFO", "ComboLBox"):
			with self.subTest(window_class=window_class):
				self.assertFalse(self.allowed(window_class, "Button"))

	def test_embedded_standard_controls_keep_space_arrows_and_typing(self):
		for control_class in ("Edit", "Button", "ComboBox", "SysTreeView32", "RichEdit20W"):
			with self.subTest(control_class=control_class):
				self.assertFalse(self.allowed(focus_class=control_class))

	def test_open_menus_and_disabled_windows_do_not_run_commands(self):
		for flags in (0x04, 0x08, 0x10):
			self.assertFalse(self.allowed(flags=flags))
		self.assertFalse(self.allowed(enabled=False))

	def test_another_process_and_failed_focus_query_are_passed_through(self):
		self.assertFalse(self.allowed(process_id=456))
		self.assertFalse(self.allowed(info_ok=False))

	def test_balance_reaches_both_endpoints_and_center(self):
		controller = backend.XMPlayController(123)
		for raw, expected in ((0, -100), (127, 0), (255, 100)):
			def ipc(parameter, command):
				return raw if command == backend.IPC_SETPANNING else 0
			with (
				self.subTest(raw=raw),
				mock.patch.object(controller, "_send_ipc", side_effect=ipc),
				mock.patch.object(controller, "current_title", return_value=""),
			):
				self.assertEqual(controller.status().balance_percent, expected)
