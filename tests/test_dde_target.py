from __future__ import annotations

import ctypes
from unittest import TestCase, mock

from test_backend import backend


class DDETargetTest(TestCase):
	def setUp(self):
		self.patches = []
		self.native = {}
		for name in ("DdeInitializeW", "DdeCreateStringHandleW", "DdeConnectList", "DdeQueryNextServer",
			"DdeQueryConvInfo", "GetWindowThreadProcessId", "DdeDisconnectList", "DdeFreeStringHandle",
			"DdeUninitialize"):
			patch = mock.patch.object(backend._user32, name)
			self.native[name] = patch.start()
			self.addCleanup(patch.stop)
		self.native["DdeInitializeW"].side_effect = self.initialize
		self.native["DdeCreateStringHandleW"].side_effect = [11, 12]
		self.native["DdeConnectList"].return_value = 20
		self.native["DdeQueryNextServer"].side_effect = [30, 40, 0]
		self.native["DdeQueryConvInfo"].side_effect = self.query_info
		self.native["GetWindowThreadProcessId"].side_effect = self.query_pid

	@staticmethod
	def initialize(pointer, *args):
		pointer._obj.value = 10
		return 0

	@staticmethod
	def query_info(conversation, transaction, pointer):
		pointer._obj.hwndPartner = conversation + 100
		return ctypes.sizeof(backend._ConvInfo)

	@staticmethod
	def query_pid(hwnd, pointer):
		pointer._obj.value = 123 if hwnd == 130 else 456
		return 1

	def test_selects_matching_process_even_if_another_server_comes_first(self):
		with backend._DDEConversation("System", 456) as conversation:
			self.assertEqual(conversation._conversation, 40)
		self.native["DdeDisconnectList"].assert_called_once_with(20)
		self.native["DdeUninitialize"].assert_called_once_with(10)

	def test_no_matching_process_never_uses_another_player(self):
		with self.assertRaisesRegex(backend.XMPlayError, "selected XMPlay process"):
			backend._DDEConversation("System", 789)
		self.native["DdeDisconnectList"].assert_called_once_with(20)
		self.native["DdeUninitialize"].assert_called_once_with(10)

	def test_failed_conversation_info_is_not_accepted_as_target(self):
		self.native["DdeQueryConvInfo"].return_value = 0
		self.native["DdeQueryConvInfo"].side_effect = None
		with self.assertRaises(backend.XMPlayError):
			backend._DDEConversation("info0", 123)
		self.native["GetWindowThreadProcessId"].assert_not_called()

	def test_execute_uses_unicode_data_with_a_wide_terminator(self):
		with backend._DDEConversation("System", 123) as conversation:
			command = "[list(D:\\Muzyka\\Żółć fixture.wav)]"
			with mock.patch.object(backend._user32, "DdeClientTransaction", return_value=1) as send:
				conversation.execute(command)
			data, size = send.call_args.args[:2]
			self.assertEqual(ctypes.string_at(data, size), command.encode("utf-16-le") + b"\0\0")
		self.native["DdeCreateStringHandleW"].assert_any_call(10, "XMPlay", 1200)

	def test_file_commands_preserve_spaces_and_unicode_without_literal_quotes(self):
		controller = backend.XMPlayController(123)
		with mock.patch.object(controller, "execute_many") as execute:
			controller.open_paths(["D:\\Muzyka\\Żółć fixture.wav", "D:\\Muzyka\\Other.wav"], replace=True)
		execute.assert_called_once_with([
			"key341", "key370", "[list(D:\\Muzyka\\Żółć fixture.wav)]", "[list(D:\\Muzyka\\Other.wav)]",
			"key346", "key372",
		], cancelled=None)

	def test_adding_files_does_not_clear_existing_playlist(self):
		controller = backend.XMPlayController(123)
		with mock.patch.object(controller, "execute_many") as execute:
			controller.open_paths(["D:\\Muzyka\\Track.wav"], replace=False)
		execute.assert_called_once_with(["[list(D:\\Muzyka\\Track.wav)]"], cancelled=None)

	def test_empty_replace_request_never_clears_playlist(self):
		controller = backend.XMPlayController(123)
		with mock.patch.object(controller, "execute_many") as execute:
			controller.open_paths([], replace=True)
		execute.assert_not_called()
