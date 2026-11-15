from __future__ import annotations

import importlib.util
import ctypes
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock


BACKEND_PATH = (
	Path(__file__).resolve().parents[1] / "addon" / "appModules" / "xmplay" / "backend.py"
)
SPEC = importlib.util.spec_from_file_location("xmplay_backend_test", BACKEND_PATH)
backend = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = backend
SPEC.loader.exec_module(backend)


class BackendHelpersTest(unittest.TestCase):
	def test_signed_32_bit_results(self):
		self.assertEqual(backend._signed32(0), 0)
		self.assertEqual(backend._signed32(0x7FFFFFFF), 0x7FFFFFFF)
		self.assertEqual(backend._signed32(0xFFFFFFFF), -1)

	def test_utf8_is_preferred(self):
		self.assertEqual(backend._decode_xmplay("Zażółć".encode("utf-8") + b"\0ignored"), "Zażółć")

	def test_time_independent_data_classes(self):
		track = backend.Track(4, "Title", r"D:\\Music\\file.mp3")
		self.assertEqual(track.index, 4)
		self.assertEqual(track.title, "Title")

	def test_xmplay_shortcut_records_are_decoded(self):
		bindings = backend.parse_shortcuts(
			"0002000026004803"  # Volume up on Up Arrow.
			"0402000045001202"  # Equalizer toggle on E.
		)
		self.assertEqual(
			bindings,
			[
				backend.ShortcutBinding(512, 0x26, 0, 0x48, True),
				backend.ShortcutBinding(516, 0x45, 0, 0x12, False),
			],
		)

	def test_action_is_not_tied_to_a_fixed_key(self):
		binding = backend.parse_shortcuts(
			"0402000051001002"  # Equalizer toggle reassigned to Q.
		)[0]
		self.assertEqual(binding.command, 516)
		self.assertEqual(binding.vk_code, 0x51)

	def test_invalid_xmplay_shortcut_records_are_rejected(self):
		with self.assertRaisesRegex(ValueError, "hexadecimal"):
			backend.parse_shortcuts("not hex")
		with self.assertRaisesRegex(ValueError, "incomplete"):
			backend.parse_shortcuts("0002")

	def test_control_commands_use_xmplays_low_latency_message(self):
		controller = backend.XMPlayController(123)
		with (
			mock.patch.object(controller, "_get_window", return_value=456),
			mock.patch.object(backend._user32, "SendMessageTimeoutW", return_value=1) as send,
		):
			controller.command(516)
		args = send.call_args.args
		self.assertEqual(args[0], 456)
		self.assertEqual(args[1], backend.WM_XMPLAY_COMMAND)
		self.assertEqual(args[2], 516)

	def test_documented_info_pages_map_to_xmplay_38_topics(self):
		conversation = mock.MagicMock()
		conversation.__enter__.return_value = conversation
		conversation.request.return_value = "details"
		with mock.patch.object(backend, "_DDEConversation", return_value=conversation) as factory:
			controller = backend.XMPlayController(123)
			self.assertEqual(controller.request_info(1), "details")
			factory.assert_called_once_with("info0", 123)
			conversation.request.assert_called_once_with("info0")

	def test_remote_string_does_not_read_past_its_final_page(self):
		controller = backend.XMPlayController(123)
		address = 0x10000 + backend.mmap.PAGESIZE - 16

		def read_memory(handle, pointer, buffer, size, bytes_read):
			if size > 16:
				return 0
			data = b"Valid title\0"
			ctypes.memmove(buffer, data, len(data))
			ctypes.cast(bytes_read, ctypes.POINTER(ctypes.c_size_t)).contents.value = len(data)
			return 1

		with mock.patch.object(backend._kernel32, "ReadProcessMemory", side_effect=read_memory) as read:
			self.assertEqual(controller._read_remote_string(999, address), "Valid title")
		read.assert_called_once()
		self.assertEqual(read.call_args.args[3], 16)

	def test_remote_utf8_text_can_cross_a_page_boundary(self):
		controller = backend.XMPlayController(123)
		address = 0x10000 + backend.mmap.PAGESIZE - 1
		data = "Żółć".encode("utf-8") + b"\0"

		def read_memory(handle, pointer, buffer, size, bytes_read):
			offset = pointer.value - address
			chunk = data[offset:offset + size]
			ctypes.memmove(buffer, chunk, len(chunk))
			ctypes.cast(bytes_read, ctypes.POINTER(ctypes.c_size_t)).contents.value = len(chunk)
			return 1

		with mock.patch.object(backend._kernel32, "ReadProcessMemory", side_effect=read_memory) as read:
			self.assertEqual(controller._read_remote_string(999, address), "Żółć")
		self.assertEqual(read.call_count, 2)

	def test_unterminated_remote_string_has_a_bounded_read(self):
		controller = backend.XMPlayController(123)

		def read_memory(handle, pointer, buffer, size, bytes_read):
			ctypes.memset(buffer, ord("x"), size)
			ctypes.cast(bytes_read, ctypes.POINTER(ctypes.c_size_t)).contents.value = size
			return 1

		with mock.patch.object(backend._kernel32, "ReadProcessMemory", side_effect=read_memory) as read:
			self.assertEqual(controller._read_remote_string(999, 0x10000), "")
		self.assertEqual(sum(call.args[3] for call in read.call_args_list), 65536)

	def test_playlist_cancellation_discards_partial_result_and_closes_handle(self):
		controller = backend.XMPlayController(123)
		cancel_event = threading.Event()

		def read_track(index, handle):
			cancel_event.set()
			return backend.Track(index, "Track", "track.mp3")

		with (
			mock.patch.object(controller, "playlist_length", return_value=3),
			mock.patch.object(controller, "_open_process", return_value=999),
			mock.patch.object(controller, "_track_with_handle", side_effect=read_track) as read,
			mock.patch.object(backend._kernel32, "CloseHandle") as close,
		):
			self.assertEqual(controller.get_playlist(cancelled=cancel_event.is_set), [])
		read.assert_called_once_with(0, 999)
		close.assert_called_once_with(999)

	def test_dde_batch_cancellation_stops_before_the_next_command(self):
		controller = backend.XMPlayController(123)
		cancel_event = threading.Event()
		conversation = mock.MagicMock()
		conversation.__enter__.return_value = conversation
		conversation.execute.side_effect = lambda command: cancel_event.set()
		with mock.patch.object(backend, "_DDEConversation", return_value=conversation):
			controller.execute_many(("key340", "key337", "key372"), cancelled=cancel_event.is_set)
		conversation.execute.assert_called_once_with("key340")
		conversation.__exit__.assert_called_once()

	def test_cancelled_actions_do_not_open_a_dde_connection(self):
		controller = backend.XMPlayController(123)
		with mock.patch.object(backend, "_DDEConversation") as conversation:
			controller.execute_many(("key340",), cancelled=lambda: True)
		conversation.assert_not_called()


if __name__ == "__main__":
	unittest.main()
