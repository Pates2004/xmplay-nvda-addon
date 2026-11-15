from __future__ import annotations

import types
import threading
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
		dialog._window_id = 42
		dialog._load_generation = 1
		dialog._playlist_loading = False
		dialog._operation_pending = False
		dialog._cancel_event = threading.Event()
		dialog.tracks = []
		dialog.filtered_tracks = []
		dialog.btn_refresh = mock.Mock()
		dialog.btn_play_selected = mock.Mock()
		dialog._operation_controls = (dialog.btn_play_selected,)
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
		dialog.btn_play_selected.Enable.assert_called_once_with(True)
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

	def test_external_destruction_also_cancels_pending_work(self):
		dialog = self.dialog()
		event = mock.Mock()
		event.GetId.return_value = 42
		dialog._on_destroy(event)
		self.assertTrue(dialog._closed)
		self.assertTrue(dialog._cancel_event.is_set())
		self.assertEqual(dialog._load_generation, 2)
		dialog._on_destroy(event)
		self.assertEqual(dialog._load_generation, 2)
		event.Skip.assert_called()

	def test_child_control_destruction_does_not_close_dialog(self):
		dialog = self.dialog()
		event = mock.Mock()
		event.GetId.return_value = 43
		dialog._on_destroy(event)
		self.assertFalse(dialog._closed)
		self.assertFalse(dialog._cancel_event.is_set())

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
		dialog.btn_refresh.Enable.assert_called_once_with(True)
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

	def test_repeated_activation_and_commands_cannot_start_parallel_mutations(self):
		dialog = self.dialog()
		dialog._selected_track = mock.Mock(
			return_value=self.backend.Track(0, "Selected", "selected.mp3"),
		)
		dialog.controller = mock.Mock()
		dialog._refresh_status = mock.Mock()

		with mock.patch.object(self.dialogs.threading, "Thread") as thread:
			dialog._on_play_selected(None)
			dialog._on_play_selected(None)
			dialog._command(80)
			dialog.refresh_all()
			dialog._choose_files(False)

		thread.assert_called_once()
		thread.return_value.start.assert_called_once_with()
		dialog.controller.command.assert_not_called()
		dialog._refresh_status.assert_not_called()
		self.assertTrue(dialog._operation_pending)
		dialog.btn_play_selected.Enable.assert_called_once_with(False)

	def test_refresh_is_single_flight_and_blocks_mutations_while_loading(self):
		dialog = self.dialog()
		dialog._refresh_status = mock.Mock()
		dialog.controller = mock.Mock()
		dialog._selected_track = mock.Mock()

		with mock.patch.object(self.dialogs.threading, "Thread") as thread:
			dialog.refresh_all()
			dialog.refresh_all()
			dialog._on_play_selected(None)
			dialog._command(80)

		thread.assert_called_once()
		dialog._refresh_status.assert_called_once_with()
		dialog._selected_track.assert_not_called()
		dialog.controller.command.assert_not_called()
		self.assertTrue(dialog._playlist_loading)

	def test_worker_start_failure_releases_busy_state_and_controls(self):
		dialog = self.dialog()
		dialog._selected_track = mock.Mock(
			return_value=self.backend.Track(0, "Selected", "selected.mp3"),
		)
		error = RuntimeError("Cannot create a worker")

		with mock.patch.object(self.dialogs.threading, "Thread") as thread:
			thread.return_value.start.side_effect = error
			dialog._on_play_selected(None)

		self.assertFalse(dialog._operation_pending)
		dialog._error.assert_called_once_with(error)
		self.assertEqual(
			dialog.btn_play_selected.Enable.call_args_list,
			[mock.call(False), mock.call(True)],
		)

	def test_failed_mutation_recovers_without_access_after_close(self):
		for closed in (False, True):
			with self.subTest(closed=closed):
				dialog = self.dialog()
				dialog._operation_pending = True
				dialog._closed = closed
				error = self.backend.XMPlayError("Operation failed")
				dialog._finish_play_selected(self.backend.Track(0, "Track", "track.mp3"), error)
				self.assertFalse(dialog._operation_pending)
				if closed:
					dialog._error.assert_not_called()
					self.assertFalse(dialog.btn_play_selected.mock_calls)
					self.assertFalse(dialog.btn_refresh.mock_calls)
				else:
					dialog._error.assert_called_once_with(error)
					dialog.btn_play_selected.Enable.assert_called_once_with(True)

	def test_close_requests_worker_cancellation_and_invalidates_load(self):
		dialog = self.dialog()
		dialog.Destroy = mock.Mock()

		dialog._on_close(None)

		self.assertTrue(dialog._cancel_event.is_set())
		self.assertTrue(dialog._closed)
		self.assertEqual(dialog._load_generation, 2)
		dialog.Destroy.assert_called_once_with()

	def test_file_completion_refreshes_before_old_entries_can_be_activated(self):
		dialog = self.dialog()
		dialog._operation_pending = True
		dialog.refresh_all = mock.Mock()

		dialog._finish_open_paths(3, None)

		self.assertFalse(dialog._operation_pending)
		dialog.refresh_all.assert_called_once_with()

	def test_failed_file_batch_refreshes_after_possible_partial_changes(self):
		dialog = self.dialog()
		dialog._operation_pending = True
		dialog.refresh_all = mock.Mock()
		error = self.backend.XMPlayError("A file could not be added")

		dialog._finish_open_paths(3, error)

		self.assertFalse(dialog._operation_pending)
		dialog._error.assert_called_once_with(error)
		dialog.refresh_all.assert_called_once_with()

	def test_enter_plays_only_from_the_playlist_without_modifiers(self):
		dialog = self.dialog()
		dialog._on_play_selected = mock.Mock()
		window = types.SimpleNamespace(FindFocus=mock.Mock())
		constants = {"WXK_ESCAPE": 27, "WXK_RETURN": 13, "WXK_NUMPAD_ENTER": 370}
		with mock.patch.multiple(self.dialogs.wx, Window=window, create=True, **constants):
			for focus, modified, plays in (
				(dialog.playlist, False, True),
				(object(), False, False),
				(dialog.playlist, True, False),
			):
				with self.subTest(playlist=focus is dialog.playlist, modified=modified):
					window.FindFocus.return_value = focus
					event = mock.Mock()
					event.GetKeyCode.return_value = 13
					event.HasAnyModifiers.return_value = modified
					dialog._on_play_selected.reset_mock()
					dialog._on_key(event)
					if plays:
						dialog._on_play_selected.assert_called_once_with(event)
						event.Skip.assert_not_called()
					else:
						dialog._on_play_selected.assert_not_called()
						event.Skip.assert_called_once_with()


if __name__ == "__main__":
	unittest.main()
