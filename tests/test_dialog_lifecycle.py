from __future__ import annotations

import types
import unittest
from unittest import mock

from test_formatting import load_dialogs_module


class ControlCenterLifecycleTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.backend, cls.dialogs = load_dialogs_module()

	def dialog(self):
		dialog = self.dialogs.ControlCenterDialog.__new__(
			self.dialogs.ControlCenterDialog,
		)
		dialog._closed = False
		dialog._load_generation = 1
		dialog._playlist_loading = False
		dialog.tracks = []
		dialog.filtered_tracks = []
		dialog.btn_refresh = mock.Mock()
		dialog.btn_play_selected = mock.Mock()
		dialog.playlist = mock.Mock()
		dialog.selection_details = mock.Mock()
		dialog._error = mock.Mock()
		dialog._feedback = mock.Mock()
		return dialog

	def test_play_selected_callback_refreshes_and_reports_current_track(self):
		dialog = self.dialog()
		track = self.backend.Track(2, "Selected track", "selected.mp3")
		dialog._refresh_status = mock.Mock(
			return_value=types.SimpleNamespace(title="Current track"),
		)
		dialog._after_command = mock.Mock(wraps=dialog._after_command)

		def execute_callback(delay, callback, *args):
			return callback(*args)

		with mock.patch.object(
			self.dialogs.wx,
			"CallLater",
			side_effect=execute_callback,
			create=True,
		) as call_later:
			dialog._finish_play_selected(track, None)

		self.assertEqual(call_later.call_args.args[0], 220)
		dialog._after_command.assert_called_once_with(None, "track")
		dialog._refresh_status.assert_called_once_with()
		dialog._feedback.assert_called_once_with("Now playing: Current track")
		dialog.btn_play_selected.Enable.assert_called_once_with()
		dialog._error.assert_not_called()

	def test_refresh_after_close_does_not_touch_controls_or_start_work(self):
		dialog = self.dialog()
		dialog._closed = True
		dialog._refresh_status = mock.Mock()
		dialog._load_playlist = mock.Mock()

		with mock.patch.object(self.dialogs.threading, "Thread") as thread:
			dialog.refresh_all()

		dialog._refresh_status.assert_not_called()
		self.assertEqual(dialog._load_generation, 1)
		self.assertFalse(dialog.btn_refresh.mock_calls)
		self.assertFalse(dialog.playlist.mock_calls)
		self.assertFalse(dialog.selection_details.mock_calls)
		thread.assert_not_called()

	def test_failed_reload_clears_previous_playlist_model(self):
		dialog = self.dialog()
		track = self.backend.Track(0, "Old playlist", "old.mp3")
		dialog.tracks = [track]
		dialog.filtered_tracks = [track]
		dialog._playlist_loading = True
		dialog._apply_filter = mock.Mock()
		error = self.backend.XMPlayError("Playlist read failed")

		dialog._finish_playlist_load(1, [], error)

		self.assertEqual(dialog.tracks, [])
		self.assertEqual(dialog.filtered_tracks, [])
		self.assertFalse(dialog._playlist_loading)
		dialog.playlist.Clear.assert_called_once_with()
		dialog.playlist.Append.assert_called_once_with("Playlist unavailable")
		dialog.btn_refresh.Enable.assert_called_once_with()
		dialog._error.assert_called_once_with(error)
		dialog._apply_filter.assert_not_called()

	def test_filter_during_reload_does_not_restore_previous_entries(self):
		dialog = self.dialog()
		track = self.backend.Track(0, "Old playlist", "old.mp3")
		dialog.tracks = [track]
		dialog.filtered_tracks = [track]
		dialog._playlist_loading = True
		dialog.search = mock.Mock()
		dialog.search.GetValue.return_value = "old"
		dialog.controller = mock.Mock()
		dialog._update_selection_details = mock.Mock()
		dialog._apply_filter = mock.Mock(wraps=dialog._apply_filter)

		dialog._on_filter(mock.Mock())

		dialog._apply_filter.assert_not_called()
		self.assertFalse(dialog.playlist.mock_calls)
		dialog.search.GetValue.assert_not_called()
		dialog._update_selection_details.assert_not_called()


if __name__ == "__main__":
	unittest.main()
