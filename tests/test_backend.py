from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
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
			factory.assert_called_once_with("info0")
			conversation.request.assert_called_once_with("info0")


if __name__ == "__main__":
	unittest.main()
