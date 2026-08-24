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
