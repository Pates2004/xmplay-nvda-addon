"""Accessible wxPython interfaces for XMPlay."""

from __future__ import annotations

import threading

import addonHandler
import ui
import wx

from globalPlugins.xmplayAccessibility.configuration import get_setting

from .backend import (
	PLAYBACK_PAUSED,
	PLAYBACK_PLAYING,
	PLAYBACK_STOPPED,
	Status,
	Track,
	XMPlayController,
	XMPlayError,
)


addonHandler.initTranslation()


def format_time(milliseconds: int) -> str:
	total_seconds = max(0, int(milliseconds) // 1000)
	hours, remainder = divmod(total_seconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	if hours:
		return f"{hours}:{minutes:02d}:{seconds:02d}"
	return f"{minutes}:{seconds:02d}"


def state_text(state: int) -> str:
	if state == PLAYBACK_PLAYING:
		return _("Playing")
	if state == PLAYBACK_PAUSED:
		return _("Paused")
	if state == PLAYBACK_STOPPED:
		return _("Stopped")
	return _("Unknown")


def balance_text(value: int) -> str:
	if -2 <= value <= 2:
		return _("center")
	if value < 0:
		return _("{percent}% left").format(percent=abs(value))
	return _("{percent}% right").format(percent=value)


def channel_text(channels: int) -> str:
	if channels == 1:
		return _("mono")
	if channels == 2:
		return _("stereo")
	if channels > 2:
		return _("{count} channels").format(count=channels)
	return _("unavailable")


def format_status(status: Status) -> str:
	remaining_ms = max(0, status.length_seconds * 1000 - status.position_ms)
	track_position = (
		_("track {current} of {total}").format(
			current=status.playlist_position + 1,
			total=status.playlist_length,
		)
		if status.playlist_position >= 0
		else _("no current playlist entry")
	)
	lines = [
		_("State: {state}").format(state=state_text(status.state)),
		_("Track: {title}").format(title=status.title or _("No track loaded")),
		_("Elapsed: {elapsed}").format(elapsed=format_time(status.position_ms)),
		_("Remaining: {remaining}").format(remaining=format_time(remaining_ms)),
		_("Total duration: {total}").format(total=format_time(status.length_seconds * 1000)),
		_("Volume: {volume}%; balance: {balance}").format(
			volume=status.volume_percent,
			balance=balance_text(status.balance_percent),
		),
		_("Playlist: {position}").format(position=track_position),
	]
	if status.sample_rate_khz or status.bitrate_kbps or status.channels:
		lines.append(
			_("Audio: {rate} kHz, {bitrate} kbps, {channels}").format(
				rate=status.sample_rate_khz or _("unknown"),
				bitrate=status.bitrate_kbps or _("unknown"),
				channels=channel_text(status.channels),
			)
		)
	return "\r\n".join(lines)


def format_focus_status(status: Status) -> str:
	"""Create a concise, labelled summary for the custom XMPlay main window."""
	parts = [
		_("Track: {title}").format(title=status.title or _("No track loaded")),
		_("State: {state}").format(state=state_text(status.state)),
	]
	if status.length_seconds:
		remaining_ms = max(0, status.length_seconds * 1000 - status.position_ms)
		parts.extend(
			(
				_("Elapsed: {elapsed}").format(elapsed=format_time(status.position_ms)),
				_("Remaining: {remaining}").format(remaining=format_time(remaining_ms)),
				_("Total duration: {total}").format(
					total=format_time(status.length_seconds * 1000),
				),
			)
		)
	return ". ".join(parts)


def localize_info_text(section: int, text: str) -> str:
	"""Translate XMPlay's fixed information-field labels, preserving tag data."""
	if not text:
		return ""
	if text.strip().casefold() == "no instrument/sample text":
		return _("No instrument or sample text is available.")
	if section != 1:
		return text
	labels = {
		"Title": _("Title"),
		"File": _("File"),
		"Path": _("Path"),
		"Size": _("Size"),
		"Modified": _("Modified"),
		"Format": _("Format"),
		"Bit rate": _("Bit rate"),
		"Sample rate": _("Sample rate"),
		"Channels": _("Channels"),
		"Length": _("Length"),
		"Output": _("Output"),
	}
	localized_lines = []
	for line in text.splitlines():
		key, separator, value = line.partition("\t")
		localized_lines.append(f"{labels.get(key, key)}{separator}{value}")
	return "\r\n".join(localized_lines)


class TrackInformationDialog(wx.Dialog):
	def __init__(self, parent, controller: XMPlayController):
		super().__init__(parent, title=_("XMPlay track information"), size=(720, 560))
		self.SetEscapeId(wx.ID_CLOSE)
		panel = wx.Panel(self)
		notebook = wx.Notebook(panel)

		for section, label in ((1, _("General")), (2, _("Message and tags")), (3, _("Samples"))):
			page = wx.Panel(notebook)
			try:
				content = localize_info_text(section, controller.request_info(section).strip())
			except XMPlayError as error:
				content = _("Information is unavailable: {error}").format(error=error)
			if not content:
				content = _("No information is available for this section.")
			text = wx.TextCtrl(
				page,
				value=content,
				name=label,
				style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_RICH2,
			)
			page_sizer = wx.BoxSizer(wx.VERTICAL)
			page_sizer.Add(text, 1, wx.ALL | wx.EXPAND, 10)
			page.SetSizer(page_sizer)
			notebook.AddPage(page, label)

		close_button = wx.Button(panel, id=wx.ID_CLOSE, label=_("&Close"))
		close_button.Bind(wx.EVT_BUTTON, lambda event: self.Close())
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(notebook, 1, wx.ALL | wx.EXPAND, 10)
		sizer.Add(close_button, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 10)
		panel.SetSizer(sizer)


class ControlCenterDialog(wx.Dialog):
	"""A standard, screen-reader-accessible replacement for XMPlay's skinned UI."""

	def __init__(self, parent, controller: XMPlayController):
		super().__init__(parent, title=_("XMPlay accessible control center"), size=(820, 720))
		self.controller = controller
		self.tracks: list[Track] = []
		self.filtered_tracks: list[Track] = []
		self._load_generation = 0
		self._closed = False
		self.SetEscapeId(wx.ID_CLOSE)

		panel = wx.Panel(self)
		self.status = wx.TextCtrl(
			panel,
			name=_("Playback status"),
			style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_RICH2,
			size=(-1, 125),
		)
		self.search = wx.SearchCtrl(panel, name=_("Search playlist"))
		self.search.SetDescriptiveText(_("Type a title or file path"))
		self.playlist = wx.ListBox(panel, name=_("XMPlay playlist"))
		self.selection_details = wx.TextCtrl(
			panel,
			name=_("Selected track details"),
			style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_RICH2,
			size=(-1, 75),
		)

		self.btn_play_selected = wx.Button(panel, label=_("&Play selected"))
		self.btn_play_pause = wx.Button(panel, label=_("Play or &pause"))
		self.btn_stop = wx.Button(panel, label=_("&Stop"))
		self.btn_previous = wx.Button(panel, label=_("Pre&vious"))
		self.btn_next = wx.Button(panel, label=_("&Next"))
		self.btn_back = wx.Button(panel, label=_("Seek &back"))
		self.btn_forward = wx.Button(panel, label=_("Seek &forward"))
		self.btn_volume_down = wx.Button(panel, label=_("Volume &down"))
		self.btn_volume_up = wx.Button(panel, label=_("Volume &up"))
		self.btn_mute = wx.Button(panel, label=_("&Mute"))
		self.btn_loop = wx.Button(panel, label=_("&Loop mode"))
		self.btn_info = wx.Button(panel, label=_("Track &information..."))
		self.btn_add = wx.Button(panel, label=_("&Add files..."))
		self.btn_open = wx.Button(panel, label=_("&Open files and replace playlist..."))
		self.btn_refresh = wx.Button(panel, label=_("&Refresh"))
		self.btn_close = wx.Button(panel, id=wx.ID_CLOSE, label=_("&Close"))

		status_sizer = wx.BoxSizer(wx.HORIZONTAL)
		status_sizer.Add(wx.StaticText(panel, label=_("Current playback:")), 0, wx.RIGHT | wx.ALIGN_TOP, 8)
		status_sizer.Add(self.status, 1, wx.EXPAND)

		search_sizer = wx.BoxSizer(wx.HORIZONTAL)
		search_sizer.Add(wx.StaticText(panel, label=_("Search:")), 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
		search_sizer.Add(self.search, 1, wx.EXPAND)

		transport_sizer = wx.GridSizer(rows=0, cols=4, vgap=7, hgap=7)
		for button in (
			self.btn_play_selected,
			self.btn_play_pause,
			self.btn_stop,
			self.btn_info,
			self.btn_previous,
			self.btn_next,
			self.btn_back,
			self.btn_forward,
			self.btn_volume_down,
			self.btn_volume_up,
			self.btn_mute,
			self.btn_loop,
		):
			transport_sizer.Add(button, 1, wx.EXPAND)

		footer_sizer = wx.BoxSizer(wx.HORIZONTAL)
		footer_sizer.Add(self.btn_add, 0, wx.RIGHT, 7)
		footer_sizer.Add(self.btn_open, 0, wx.RIGHT, 7)
		footer_sizer.Add(self.btn_refresh, 0, wx.RIGHT, 7)
		footer_sizer.AddStretchSpacer(1)
		footer_sizer.Add(self.btn_close, 0)

		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(status_sizer, 0, wx.ALL | wx.EXPAND, 10)
		sizer.Add(search_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		sizer.Add(wx.StaticText(panel, label=_("Playlist:")), 0, wx.LEFT | wx.RIGHT, 10)
		sizer.Add(self.playlist, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		sizer.Add(wx.StaticText(panel, label=_("Selected track:")), 0, wx.LEFT | wx.RIGHT, 10)
		sizer.Add(self.selection_details, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		sizer.Add(transport_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		sizer.Add(footer_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
		panel.SetSizer(sizer)

		self.search.Bind(wx.EVT_TEXT, self._on_filter)
		self.playlist.Bind(wx.EVT_LISTBOX, self._on_selection)
		self.playlist.Bind(wx.EVT_LISTBOX_DCLICK, self._on_play_selected)
		self.btn_play_selected.Bind(wx.EVT_BUTTON, self._on_play_selected)
		self.btn_play_pause.Bind(wx.EVT_BUTTON, lambda event: self._command(80, report="playback"))
		self.btn_stop.Bind(wx.EVT_BUTTON, lambda event: self._command(81, report="playback"))
		self.btn_previous.Bind(wx.EVT_BUTTON, lambda event: self._command(129, report="track"))
		self.btn_next.Bind(wx.EVT_BUTTON, lambda event: self._command(128, report="track"))
		self.btn_back.Bind(wx.EVT_BUTTON, lambda event: self._command(83, report="time"))
		self.btn_forward.Bind(wx.EVT_BUTTON, lambda event: self._command(82, report="time"))
		self.btn_volume_down.Bind(wx.EVT_BUTTON, lambda event: self._command(513, report="volume"))
		self.btn_volume_up.Bind(wx.EVT_BUTTON, lambda event: self._command(512, report="volume"))
		self.btn_mute.Bind(wx.EVT_BUTTON, lambda event: self._command(523, report="volume"))
		self.btn_loop.Bind(wx.EVT_BUTTON, lambda event: self._command(9, _("Loop mode changed")))
		self.btn_info.Bind(wx.EVT_BUTTON, self._on_info)
		self.btn_add.Bind(wx.EVT_BUTTON, lambda event: self._choose_files(False))
		self.btn_open.Bind(wx.EVT_BUTTON, lambda event: self._choose_files(True))
		self.btn_refresh.Bind(wx.EVT_BUTTON, self.refresh_all)
		self.btn_close.Bind(wx.EVT_BUTTON, self._on_close)
		self.Bind(wx.EVT_CLOSE, self._on_close)
		self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

		self.refresh_all()

	def _error(self, error: Exception) -> None:
		message = _("XMPlay operation failed: {error}").format(error=error)
		wx.MessageBox(message, _("XMPlay error"), wx.OK | wx.ICON_ERROR, self)

	def _feedback(self, message: str) -> None:
		if get_setting("announceControlCenterFeedback"):
			ui.message(message)

	def _on_key(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
			return
		event.Skip()

	def _on_close(self, event):
		self._closed = True
		self._load_generation += 1
		self.Destroy()

	def refresh_all(self, event=None):
		self._refresh_status()
		self._load_generation += 1
		generation = self._load_generation
		self.btn_refresh.Disable()
		self.playlist.Clear()
		self.playlist.Append(_("Loading playlist..."))
		self.selection_details.SetValue("")
		threading.Thread(target=self._load_playlist, args=(generation,), daemon=True).start()

	def _load_playlist(self, generation: int):
		try:
			tracks = self.controller.get_playlist()
			error = None
		except Exception as caught_error:
			tracks = []
			error = caught_error
		wx.CallAfter(self._finish_playlist_load, generation, tracks, error)

	def _finish_playlist_load(self, generation: int, tracks: list[Track], error: Exception | None):
		if self._closed or generation != self._load_generation:
			return
		self.btn_refresh.Enable()
		if error:
			self.playlist.Clear()
			self.playlist.Append(_("Playlist unavailable"))
			self._error(error)
			return
		self.tracks = tracks
		self._apply_filter()
		self._feedback(
			_("Playlist loaded: {count} tracks").format(count=len(tracks))
			if tracks
			else _("The playlist is empty")
		)

	def _on_filter(self, event):
		self._apply_filter()

	def _apply_filter(self):
		query = self.search.GetValue().strip().casefold()
		if query:
			self.filtered_tracks = [
				track
				for track in self.tracks
				if query in track.title.casefold() or query in track.path.casefold()
			]
		else:
			self.filtered_tracks = list(self.tracks)
		self.playlist.Clear()
		if not self.filtered_tracks:
			self.playlist.Append(_("No matching tracks"))
			self.selection_details.SetValue("")
			return
		self.playlist.InsertItems(
			[
				_("{number}. {title}").format(
					number=track.index + 1,
					title=track.title or _("Untitled track"),
				)
				for track in self.filtered_tracks
			],
			0,
		)
		selection = 0
		try:
			current = self.controller.playlist_position()
			selection = next(
				index for index, track in enumerate(self.filtered_tracks) if track.index == current
			)
		except (StopIteration, XMPlayError):
			pass
		self.playlist.SetSelection(selection)
		self._update_selection_details()

	def _on_selection(self, event):
		self._update_selection_details()

	def _selected_track(self) -> Track | None:
		selection = self.playlist.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self.filtered_tracks):
			return None
		return self.filtered_tracks[selection]

	def _update_selection_details(self):
		track = self._selected_track()
		if not track:
			self.selection_details.SetValue("")
			return
		self.selection_details.SetValue(
			_("Track {number}\nTitle: {title}\nFile: {path}").format(
				number=track.index + 1,
				title=track.title or _("Untitled track"),
				path=track.path or _("Unavailable"),
			)
		)

	def _refresh_status(self):
		try:
			status = self.controller.status()
		except XMPlayError as error:
			self.status.SetValue(_("XMPlay is unavailable: {error}").format(error=error))
			return None
		self.status.SetValue(format_status(status))
		return status

	def _command(self, key_id: int, announcement: str | None = None, report: str = "status"):
		try:
			self.controller.command(key_id)
		except XMPlayError as error:
			self._error(error)
			return
		self._after_command(announcement, report)

	def _after_command(self, announcement: str | None, report: str):
		if self._closed:
			return
		status = self._refresh_status()
		if announcement:
			self._feedback(announcement)
		elif status and report == "volume":
			self._feedback(_("Volume {volume}%").format(volume=status.volume_percent))
		elif status and report == "track":
			self._feedback(_("Now playing: {title}").format(title=status.title or _("No track loaded")))
		elif status and report == "time":
			remaining_ms = max(0, status.length_seconds * 1000 - status.position_ms)
			self._feedback(
				". ".join(
					(
						_("Elapsed: {elapsed}").format(elapsed=format_time(status.position_ms)),
						_("Remaining: {remaining}").format(remaining=format_time(remaining_ms)),
						_("Total duration: {total}").format(
							total=format_time(status.length_seconds * 1000),
						),
					)
				)
			)
		elif status:
			self._feedback(state_text(status.state))

	def _on_play_selected(self, event):
		track = self._selected_track()
		if not track:
			ui.message(_("Select a track first"))
			return
		self.btn_play_selected.Disable()
		self._feedback(_("Starting {title}").format(title=track.title or _("Untitled track")))
		threading.Thread(target=self._play_selected, args=(track,), daemon=True).start()

	def _play_selected(self, track: Track):
		try:
			self.controller.play_track(track.index)
			error = None
		except Exception as caught_error:
			error = caught_error
		wx.CallAfter(self._finish_play_selected, track, error)

	def _finish_play_selected(self, track: Track, error: Exception | None):
		if self._closed:
			return
		self.btn_play_selected.Enable()
		if error:
			self._error(error)
			return
		wx.CallLater(220, self._after_command, _("Now playing: {title}").format(title=track.title))

	def _on_info(self, event):
		try:
			dialog = TrackInformationDialog(self, self.controller)
		except Exception as error:
			self._error(error)
			return
		dialog.Show()
		dialog.Raise()

	def _choose_files(self, replace: bool):
		if replace:
			confirmation = wx.MessageBox(
				_("This will replace the current XMPlay playlist. Continue?"),
				_("Replace playlist"),
				wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
				self,
			)
			if confirmation != wx.YES:
				return
		dialog = wx.FileDialog(
			self,
			_("Choose audio files"),
			wildcard=_("All files (*.*)|*.*"),
			style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST,
		)
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			paths = dialog.GetPaths()
		finally:
			dialog.Destroy()
		threading.Thread(target=self._open_paths, args=(paths, replace), daemon=True).start()

	def _open_paths(self, paths: list[str], replace: bool):
		try:
			self.controller.open_paths(paths, replace)
			error = None
		except Exception as caught_error:
			error = caught_error
		wx.CallAfter(self._finish_open_paths, len(paths), error)

	def _finish_open_paths(self, count: int, error: Exception | None):
		if self._closed:
			return
		if error:
			self._error(error)
			return
		self._feedback(_("Sent {count} files to XMPlay").format(count=count))
		wx.CallLater(350, self.refresh_all)
