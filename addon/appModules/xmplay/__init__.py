"""NVDA application module for the XMPlay audio player."""

from __future__ import annotations

import addonHandler
import api
import appModuleHandler
import core
import gui
from logHandler import log
from scriptHandler import script
import ui
import wx

from globalPlugins.xmplayAccessibility.configuration import get_setting

from .backend import (
	PLAYBACK_PAUSED,
	PLAYBACK_PLAYING,
	PLAYBACK_STOPPED,
	Status,
	XMPlayController,
	XMPlayError,
)
from .dialogs import (
	ControlCenterDialog,
	TrackInformationDialog,
	balance_text,
	format_status,
	format_time,
	localize_info_text,
	state_text,
)


addonHandler.initTranslation()


SCRIPT_CATEGORY = _("XMPlay")


class AppModule(appModuleHandler.AppModule):
	scriptCategory = SCRIPT_CATEGORY

	def __init__(self, processID: int, appName: str | None = None):
		super().__init__(processID, appName)
		self.controller = XMPlayController(processID)
		self._dialog = None
		self._monitor = None
		self._last_status: Status | None = None
		self._welcomed = False
		self._terminated = False
		self._schedule_monitor()

	def terminate(self):
		self._terminated = True
		if self._monitor and self._monitor.IsRunning():
			self._monitor.Stop()
		self._monitor = None
		if self._dialog:
			try:
				self._dialog.Destroy()
			except RuntimeError:
				pass
			self._dialog = None
		super().terminate()

	def _schedule_monitor(self):
		if not self._terminated:
			self._monitor = wx.CallLater(650, self._poll)

	def _is_xmplay_foreground(self) -> bool:
		try:
			return api.getForegroundObject().processID == self.processID
		except Exception:
			return False

	def _poll(self):
		try:
			if self._is_xmplay_foreground():
				current = self.controller.status()
				previous = self._last_status
				self._last_status = current
				if previous:
					if (
						get_setting("announceTrackChanges")
						and current.title
						and current.title != previous.title
					):
						ui.message(_("Now playing: {title}").format(title=current.title))
					elif get_setting("announcePlaybackState") and current.state != previous.state:
						ui.message(state_text(current.state))
					elif (
						get_setting("announceVolumeChanges")
						and current.volume_percent != previous.volume_percent
					):
						ui.message(_("Volume {volume}%").format(volume=current.volume_percent))
					elif (
						get_setting("announceBalanceChanges")
						and current.balance_percent != previous.balance_percent
					):
						ui.message(
							_("Balance {balance}").format(
								balance=balance_text(current.balance_percent),
							)
						)
		except Exception:
			log.debugWarning("XMPlay status monitor failed", exc_info=True)
		finally:
			if not self._terminated:
				self._schedule_monitor()

	def event_appModule_gainFocus(self):
		try:
			self._last_status = self.controller.status()
		except XMPlayError:
			self._last_status = None
		if not self._welcomed and get_setting("announceWelcome"):
			self._welcomed = True
			core.callLater(
				120,
				ui.message,
				_("XMPlay. Press NVDA+Shift+X for the accessible control center."),
			)

	def event_NVDAObject_init(self, obj):
		window_class = getattr(obj, "windowClassName", "")
		if window_class == "XMPLAY-MAIN":
			existing_name = (getattr(obj, "name", "") or "").strip()
			if existing_name and existing_name.casefold() != "xmplay":
				obj.name = _("XMPlay player: {title}").format(title=existing_name)
			else:
				obj.name = _("XMPlay player")
			obj.description = _(
				"XMPlay uses a custom visual interface. Press NVDA+Shift+X for its accessible controls."
			)
		elif window_class == "XMPLAY-PANEL" and not getattr(obj, "name", ""):
			obj.name = _("XMPlay custom panel")

	def _object_text(self, root) -> str:
		"""Collect exposed and display-model text from an XMPlay window."""
		lines = []
		seen_text = set()
		seen_objects = set()
		pending = [root]
		while pending and len(seen_objects) < 500:
			obj = pending.pop(0)
			identity = id(obj)
			if identity in seen_objects:
				continue
			seen_objects.add(identity)
			for attribute in ("displayText", "name", "value", "description"):
				try:
					text = (getattr(obj, attribute, "") or "").strip()
				except Exception:
					text = ""
				if text and text not in seen_text:
					seen_text.add(text)
					lines.append(text)
			try:
				pending.extend(obj.children)
			except Exception:
				pass
		return "\r\n".join(lines)[:30000]

	def _announce_help_window(self, obj):
		text = self._object_text(obj)
		if text:
			ui.message(text.replace("\r\n", ". "))

	def event_show(self, obj, nextHandler):
		nextHandler()
		if (
			get_setting("announceHelpBubbles")
			and getattr(obj, "windowClassName", "") == "XMPLAY-HELP"
		):
			core.callLater(40, self._announce_help_window, obj)

	def _show_error(self, error: Exception):
		ui.message(_("XMPlay operation failed: {error}").format(error=error))

	def _get_status(self) -> Status | None:
		try:
			status = self.controller.status()
			self._last_status = status
			return status
		except XMPlayError as error:
			self._show_error(error)
			return None

	def _run_command(self, key_id: int, report: str = "status"):
		try:
			self.controller.command(key_id)
		except XMPlayError as error:
			self._show_error(error)
			return
		core.callLater(180, self._report_after_command, report)

	def _report_after_command(self, report: str):
		status = self._get_status()
		if not status:
			return
		if not get_setting("announceCommandFeedback"):
			return
		if report == "volume":
			ui.message(
				_("Volume {volume}%; balance {balance}").format(
					volume=status.volume_percent,
					balance=balance_text(status.balance_percent),
				)
			)
		elif report == "loop":
			ui.message(_("Loop mode changed"))
		else:
			ui.message(
				_("{state}. {title}").format(
					state=state_text(status.state),
					title=status.title or _("No track loaded"),
				)
			)

	def _dialog_destroyed(self, event):
		if event.GetEventObject() is self._dialog:
			self._dialog = None
		event.Skip()

	@script(
		description=_("Opens the accessible XMPlay control center and playlist."),
		gesture="kb:NVDA+shift+x",
		category=SCRIPT_CATEGORY,
	)
	def script_showControlCenter(self, gesture):
		if self._dialog:
			try:
				self._dialog.Show()
				self._dialog.Raise()
				self._dialog.search.SetFocus()
				return
			except RuntimeError:
				self._dialog = None
		try:
			self._dialog = ControlCenterDialog(gui.mainFrame, self.controller)
			self._dialog.Bind(wx.EVT_WINDOW_DESTROY, self._dialog_destroyed)
			self._dialog.Show()
			self._dialog.Raise()
			wx.CallAfter(self._dialog.search.SetFocus)
		except Exception as error:
			self._dialog = None
			self._show_error(error)

	@script(
		description=_("Opens the accessible XMPlay playlist."),
		gesture="kb:NVDA+shift+p",
		category=SCRIPT_CATEGORY,
	)
	def script_showPlaylist(self, gesture):
		self.script_showControlCenter(gesture)

	@script(
		description=_("Announces the current track title and playlist position."),
		gesture="kb:NVDA+shift+i",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_reportTrack(self, gesture):
		status = self._get_status()
		if not status:
			return
		if status.playlist_position >= 0:
			ui.message(
				_("{title}. Track {current} of {total}").format(
					title=status.title or _("Untitled track"),
					current=status.playlist_position + 1,
					total=status.playlist_length,
				)
			)
		else:
			ui.message(status.title or _("No track loaded"))

	@script(
		description=_("Announces elapsed, total, and remaining time."),
		gesture="kb:NVDA+shift+t",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_reportTime(self, gesture):
		status = self._get_status()
		if not status:
			return
		remaining_ms = max(0, status.length_seconds * 1000 - status.position_ms)
		ui.message(
			_("Elapsed {elapsed}; total {total}; remaining {remaining}").format(
				elapsed=format_time(status.position_ms),
				total=format_time(status.length_seconds * 1000),
				remaining=format_time(remaining_ms),
			)
		)

	@script(
		description=_("Announces complete XMPlay playback status."),
		gesture="kb:NVDA+shift+s",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_reportStatus(self, gesture):
		status = self._get_status()
		if status:
			ui.message(format_status(status).replace("\r\n", ". "))

	@script(
		description=_("Announces XMPlay volume and balance."),
		gesture="kb:NVDA+shift+v",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_reportVolume(self, gesture):
		status = self._get_status()
		if status:
			ui.message(
				_("Volume {volume}%; balance {balance}").format(
					volume=status.volume_percent,
					balance=balance_text(status.balance_percent),
				)
			)

	def _show_info_section(self, section: int, title: str):
		try:
			message = localize_info_text(section, self.controller.request_info(section).strip())
		except XMPlayError as error:
			self._show_error(error)
			return
		ui.browseableMessage(
			message or _("No information is available for this section."),
			title,
		)

	@script(
		description=_("Shows general information for the current track."),
		gesture="kb:NVDA+shift+g",
		category=SCRIPT_CATEGORY,
	)
	def script_showGeneralInfo(self, gesture):
		self._show_info_section(1, _("XMPlay general track information"))

	@script(
		description=_("Shows the current track's message and tags."),
		gesture="kb:NVDA+shift+m",
		category=SCRIPT_CATEGORY,
	)
	def script_showMessageInfo(self, gesture):
		self._show_info_section(2, _("XMPlay message and tags"))

	@script(
		description=_("Shows sample and instrument information for the current module."),
		gesture="kb:NVDA+shift+a",
		category=SCRIPT_CATEGORY,
	)
	def script_showSampleInfo(self, gesture):
		self._show_info_section(3, _("XMPlay samples"))

	@script(
		description=_("Opens all available information for the current track."),
		gesture="kb:NVDA+shift+d",
		category=SCRIPT_CATEGORY,
	)
	def script_showAllTrackInfo(self, gesture):
		try:
			dialog = TrackInformationDialog(gui.mainFrame, self.controller)
			dialog.Show()
			dialog.Raise()
		except Exception as error:
			self._show_error(error)

	@script(
		description=_("Shows all text NVDA can detect in the current XMPlay window."),
		gesture="kb:NVDA+shift+o",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_showVisibleWindowText(self, gesture):
		text = self._object_text(api.getForegroundObject())
		ui.browseableMessage(
			text or _("No readable text was detected in this XMPlay window."),
			_("XMPlay window text"),
		)

	@script(
		description=_("Plays or pauses XMPlay."),
		gesture="kb:control+shift+space",
		category=SCRIPT_CATEGORY,
	)
	def script_playPause(self, gesture):
		self._run_command(80)

	@script(
		description=_("Stops XMPlay."),
		gesture="kb:control+shift+s",
		category=SCRIPT_CATEGORY,
	)
	def script_stop(self, gesture):
		self._run_command(81)

	@script(
		description=_("Plays the previous track."),
		gesture="kb:control+shift+leftArrow",
		category=SCRIPT_CATEGORY,
	)
	def script_previous(self, gesture):
		self._run_command(129)

	@script(
		description=_("Plays the next track."),
		gesture="kb:control+shift+rightArrow",
		category=SCRIPT_CATEGORY,
	)
	def script_next(self, gesture):
		self._run_command(128)

	@script(
		description=_("Seeks backward in the current track."),
		gesture="kb:control+shift+pageUp",
		category=SCRIPT_CATEGORY,
	)
	def script_seekBackward(self, gesture):
		self._run_command(83)

	@script(
		description=_("Seeks forward in the current track."),
		gesture="kb:control+shift+pageDown",
		category=SCRIPT_CATEGORY,
	)
	def script_seekForward(self, gesture):
		self._run_command(82)

	@script(
		description=_("Raises XMPlay volume."),
		gesture="kb:control+shift+upArrow",
		category=SCRIPT_CATEGORY,
	)
	def script_volumeUp(self, gesture):
		self._run_command(512, "volume")

	@script(
		description=_("Lowers XMPlay volume."),
		gesture="kb:control+shift+downArrow",
		category=SCRIPT_CATEGORY,
	)
	def script_volumeDown(self, gesture):
		self._run_command(513, "volume")

	@script(
		description=_("Mutes or restores XMPlay volume."),
		gesture="kb:control+shift+m",
		category=SCRIPT_CATEGORY,
	)
	def script_mute(self, gesture):
		self._run_command(523, "volume")

	@script(
		description=_("Cycles XMPlay's track loop mode."),
		gesture="kb:control+shift+l",
		category=SCRIPT_CATEGORY,
	)
	def script_loop(self, gesture):
		self._run_command(9, "loop")
