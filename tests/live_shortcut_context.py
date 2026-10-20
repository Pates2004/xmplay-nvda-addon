"""Check real XMPlay focus contexts using an isolated executable and empty profile.

Pass an executable in a disposable, separately prepared directory. This never
opens the user's normal XMPlay configuration, library or playlist.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest import mock


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("executable", type=Path)
	parser.add_argument("--background", action="store_true", help="Select the test process's active window without taking foreground focus")
	args = parser.parse_args()
	executable = args.executable.resolve()
	path = Path(__file__).resolve().parents[1] / "addon/appModules/xmplay/backend.py"
	spec = importlib.util.spec_from_file_location("live_context_backend", path)
	backend = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = backend
	spec.loader.exec_module(backend)
	user32 = backend._user32
	user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
	user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
	user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
	user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
	user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
	user32.EnumChildWindows.argtypes = (wintypes.HWND, backend._WNDENUMPROC, wintypes.LPARAM)
	process = subprocess.Popen([str(executable)], cwd=executable.parent)
	report = {}
	original_foreground = user32.GetForegroundWindow()
	foreground_patch = None

	def activate(hwnd):
		foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
		current_thread = backend._kernel32.GetCurrentThreadId()
		attached = user32.AttachThreadInput(current_thread, foreground_thread, True)
		try:
			user32.ShowWindow(hwnd, 9)
			user32.SetForegroundWindow(hwnd)
		finally:
			if attached:
				user32.AttachThreadInput(current_thread, foreground_thread, False)

	try:
		controller = backend.XMPlayController(process.pid)
		deadline = time.monotonic() + 5
		while not controller.is_available() and time.monotonic() < deadline:
			time.sleep(0.05)
		main_window = controller._get_window()
		if args.background:
			target_thread = user32.GetWindowThreadProcessId(main_window, None)
			def target_active_window():
				info = backend._GUITHREADINFO(cbSize=ctypes.sizeof(backend._GUITHREADINFO))
				user32.GetGUIThreadInfo(target_thread, ctypes.byref(info))
				return info.hwndActive
			foreground_patch = mock.patch.object(user32, "GetForegroundWindow", side_effect=target_active_window)
			foreground_patch.start()
			report["foreground_lookup_simulated"] = True
			active = target_active_window()
			active_class = ctypes.create_unicode_buffer(64)
			user32.GetClassNameW(active, active_class, len(active_class))
			if active_class.value == "XMPLAY-INFO":
				user32.PostMessageW(main_window, backend.WM_XMPLAY_COMMAND, 256, 0)
		else:
			activate(main_window)
		time.sleep(0.2)
		report["player_allows_commands"] = controller.can_handle_native_shortcuts()
		if not report["player_allows_commands"]:
			info = backend._GUITHREADINFO(cbSize=ctypes.sizeof(backend._GUITHREADINFO))
			user32.GetGUIThreadInfo(0, ctypes.byref(info))
			details = {"main": main_window, "flags": info.flags}
			target_thread = user32.GetWindowThreadProcessId(main_window, None)
			target_info = backend._GUITHREADINFO(cbSize=ctypes.sizeof(backend._GUITHREADINFO))
			user32.GetGUIThreadInfo(target_thread, ctypes.byref(target_info))
			details["target"] = [target_info.flags, target_info.hwndFocus, target_info.hwndActive]
			for label, hwnd in (("foreground", user32.GetForegroundWindow()), ("focus", info.hwndFocus)):
				name = ctypes.create_unicode_buffer(64)
				user32.GetClassNameW(hwnd, name, len(name))
				details[label] = [hwnd, name.value, bool(user32.IsWindowEnabled(hwnd))]
			raise AssertionError(f"Main player did not receive keyboard focus: {details}")
		before_volume = controller.status().volume_percent
		controller.command(513)
		assert controller.status().volume_percent <= before_volume
		report["native_command_and_status"] = True
		user32.PostMessageW(main_window, backend.WM_XMPLAY_COMMAND, 5, 0)
		time.sleep(0.3)
		options = user32.GetForegroundWindow()
		name = ctypes.create_unicode_buffer(64)
		user32.GetClassNameW(options, name, len(name))
		assert name.value == "#32770", name.value
		report["options_blocks_player_commands"] = not controller.can_handle_native_shortcuts()
		assert report["options_blocks_player_commands"]
		checkboxes = []

		@backend._WNDENUMPROC
		def find_checkbox(hwnd, _):
			cls = ctypes.create_unicode_buffer(64)
			user32.GetClassNameW(hwnd, cls, len(cls))
			style = user32.GetWindowLongW(hwnd, -16)
			if cls.value == "Button" and style & 0xF in (2, 3, 5, 6):
				checkboxes.append(hwnd)
			return True

		user32.EnumChildWindows(options, find_checkbox, 0)
		assert checkboxes, "No checkbox found in Options"
		checkbox = checkboxes[0]
		user32.PostMessageW(options, 0x28, checkbox, 1)  # WM_NEXTDLGCTL: focus checkbox.
		time.sleep(0.1)
		assert not controller.can_handle_native_shortcuts()
		state_before = ctypes.c_size_t()
		user32.SendMessageTimeoutW(checkbox, 0xF0, 0, 0, 2, 1000, ctypes.byref(state_before))
		user32.PostMessageW(checkbox, 0x100, 0x20, 0x00390001)
		user32.PostMessageW(checkbox, 0x101, 0x20, 0xC0390001)
		time.sleep(0.1)
		state_after = ctypes.c_size_t()
		user32.SendMessageTimeoutW(checkbox, 0xF0, 0, 0, 2, 1000, ctypes.byref(state_after))
		assert state_before.value != state_after.value, "Space did not toggle the native checkbox"
		report["space_toggles_options_checkbox"] = True
		report["playback_unchanged_in_options"] = controller.playback_state() == 0
		assert report["playback_unchanged_in_options"]
		user32.PostMessageW(options, 0x10, 0, 0)
		time.sleep(0.2)
		if not args.background:
			activate(main_window)
		time.sleep(0.1)
		assert controller.can_handle_native_shortcuts()
		report["player_shortcuts_restored_after_options"] = True
		print(json.dumps(report, indent=2))
	finally:
		try:
			user32.PostMessageW(controller._get_window(), 0x10, 0, 0)
			process.wait(timeout=3)
		except (subprocess.TimeoutExpired, backend.XMPlayError):
			if process.poll() is None:
				process.terminate()
				process.wait(timeout=3)
		if foreground_patch:
			foreground_patch.stop()
		if not args.background and original_foreground and user32.IsWindow(original_foreground):
			activate(original_foreground)


if __name__ == "__main__":
	main()
