"""NVDA application module for the XMPlay audio player."""

from __future__ import annotations

from pathlib import Path
import time

import addonHandler
import api
import appModuleHandler
import core
import gui
import inputCore
import keyboardHandler
from logHandler import log
import ui
import winUser
import wx

from globalPlugins.xmplayAccessibility.configuration import get_setting
from globalPlugins.xmplayAccessibility.localization import _

from .backend import (
	PLAYBACK_PAUSED,
	PLAYBACK_PLAYING,
	PLAYBACK_STOPPED,
	ShortcutBinding,
	Status,
	XMPlayController,
	XMPlayError,
	load_shortcuts,
)
from .dialogs import (
	ControlCenterDialog,
	TrackInformationDialog,
	balance_text,
	format_status,
	format_focus_status,
	format_time,
	localize_info_text,
	state_text,
)


addonHandler.initTranslation()


SCRIPT_CATEGORY = _("XMPlay")

MONITOR_INTERVAL_MS = 250
SHORTCUT_RELOAD_INTERVAL_SECONDS = 2

_VOLUME_ACTIONS = frozenset((512, 513, 523))
_BALANCE_ACTIONS = frozenset((519, 520))
_PLAYBACK_ACTIONS = frozenset((80, 81, 84))
_TRACK_ACTIONS = frozenset((128, 129, 130, 131))
_ACTION_FEEDBACK = {
	9: _("Track looping changed"),
	313: _("Random play order changed"),
	402: _("Playlist looping changed"),
	516: _("Equalizer toggled"),
	517: _("Reverb toggled"),
	522: _("Auto amplification changed"),
	524: _("ReplayGain mode changed"),
	525: _("Crossfade toggled"),
	526: _("DSP bypass toggled"),
}


class AppModule(appModuleHandler.AppModule):
	scriptCategory = SCRIPT_CATEGORY

	def __init__(self, processID: int, appName: str | None = None):
		super().__init__(processID, appName)
		self.controller = XMPlayController(processID)
		self._dialog = None
		self._monitor = None
		self._last_status: Status | None = None
		self._terminated = False
		self._native_shortcuts: dict[str, tuple[int, ...]] = {}
		self._native_shortcut_identifiers: set[str] = set()
		self._shortcuts_mtime_ns: int | None = None
		self._last_shortcut_check = 0.0
		self._help_announcement_counter = 0
		self._reload_native_shortcuts(force=True)
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
			self._monitor = wx.CallLater(MONITOR_INTERVAL_MS, self._poll)

	def _is_xmplay_foreground(self) -> bool:
		try:
			return api.getForegroundObject().processID == self.processID
		except Exception:
			return False

	def _poll(self):
		try:
			if self._is_xmplay_foreground():
				if time.monotonic() - self._last_shortcut_check >= SHORTCUT_RELOAD_INTERVAL_SECONDS:
					self._reload_native_shortcuts()
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
		self._reload_native_shortcuts()
		try:
			self._last_status = self.controller.status()
		except XMPlayError:
			self._last_status = None

	def event_NVDAObject_init(self, obj):
		window_class = getattr(obj, "windowClassName", "")
		if window_class == "XMPLAY-MAIN":
			try:
				status = self.controller.status()
				self._last_status = status
				obj.name = (
					format_focus_status(status)
					if get_setting("announceFocusSummary")
					else status.title or _("XMPlay")
				)
			except XMPlayError:
				obj.name = _("XMPlay")
			obj.description = None
			obj.value = None
		elif window_class == "XMPLAY-PANEL" and not getattr(obj, "name", ""):
			obj.name = _("XMPlay custom panel")

	def _shortcut_config_path(self) -> Path | None:
		app_path = getattr(self, "appPath", None)
		return Path(app_path).with_name("xmplay.ini") if app_path else None

	@staticmethod
	def _shortcut_identifier(binding: ShortcutBinding) -> str:
		modifiers = set()
		if binding.modifier_flags & 1:
			modifiers.add((winUser.VK_SHIFT, False))
		if binding.modifier_flags & 2:
			modifiers.add((winUser.VK_CONTROL, False))
		if binding.modifier_flags & 4:
			modifiers.add((winUser.VK_MENU, False))
		if binding.modifier_flags & 8:
			modifiers.add((keyboardHandler.VK_WIN, False))
		gesture = keyboardHandler.KeyboardInputGesture(
			modifiers,
			binding.vk_code,
			binding.scan_code,
			binding.is_extended,
		)
		return gesture.identifiers[-1]

	def _reload_native_shortcuts(self, force: bool = False):
		self._last_shortcut_check = time.monotonic()
		path = self._shortcut_config_path()
		try:
			mtime_ns = path.stat().st_mtime_ns if path else None
		except OSError:
			mtime_ns = None
		if not force and mtime_ns == self._shortcuts_mtime_ns:
			return
		self._shortcuts_mtime_ns = mtime_ns
		for identifier in self._native_shortcut_identifiers:
			try:
				self.removeGestureBinding(identifier)
			except KeyError:
				pass
		self._native_shortcut_identifiers.clear()
		self._native_shortcuts.clear()
		if not path or mtime_ns is None:
			return
		try:
			bindings = load_shortcuts(path)
		except (OSError, ValueError):
			log.debugWarning("Could not load XMPlay shortcuts", exc_info=True)
			return
		grouped: dict[str, list[int]] = {}
		for binding in bindings:
			try:
				identifier = self._shortcut_identifier(binding)
			except (KeyError, LookupError):
				log.debugWarning("Could not identify an XMPlay shortcut", exc_info=True)
				continue
			normalized = inputCore.normalizeGestureIdentifier(identifier)
			grouped.setdefault(normalized, []).append(binding.command)
		for normalized, actions in grouped.items():
			self.bindGesture(normalized, "nativeShortcut")
			self._native_shortcut_identifiers.add(normalized)
			self._native_shortcuts[normalized] = tuple(actions)

	def _native_actions_for_gesture(self, gesture) -> tuple[int, ...]:
		for identifier in gesture.normalizedIdentifiers:
			actions = self._native_shortcuts.get(identifier)
			if actions:
				return actions
		return ()

	def script_nativeShortcut(self, gesture):
		actions = self._native_actions_for_gesture(gesture)
		if not actions or not self._is_xmplay_foreground():
			gesture.send()
			return
		try:
			self.controller.commands(actions)
		except XMPlayError:
			log.debugWarning("Direct XMPlay shortcut execution failed", exc_info=True)
			gesture.send()
			return
		self._report_native_shortcut(actions)

	def _report_native_shortcut(self, actions: tuple[int, ...]):
		if not get_setting("announceCommandFeedback"):
			return
		action_set = set(actions)
		if action_set & (_VOLUME_ACTIONS | _BALANCE_ACTIONS | _PLAYBACK_ACTIONS | _TRACK_ACTIONS):
			status = self._get_status()
			if not status:
				return
			if action_set & _VOLUME_ACTIONS:
				ui.message(_("Volume {volume}%").format(volume=status.volume_percent))
			elif action_set & _BALANCE_ACTIONS:
				ui.message(_("Balance {balance}").format(balance=balance_text(status.balance_percent)))
			elif action_set & _TRACK_ACTIONS:
				ui.message(_("Now playing: {title}").format(title=status.title or _("No track loaded")))
			else:
				ui.message(state_text(status.state))
			return
		feedback = [_ACTION_FEEDBACK[action] for action in actions if action in _ACTION_FEEDBACK]
		if feedback:
			counter = self._help_announcement_counter
			core.callLater(120, self._report_action_fallback, counter, feedback)

	def _report_action_fallback(self, help_counter: int, feedback: list[str]):
		if help_counter == self._help_announcement_counter:
			ui.message(". ".join(feedback))

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
			self._help_announcement_counter += 1
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
		self._report_after_command(report)

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

	def script_showPlaylist(self, gesture):
		self.script_showControlCenter(gesture)

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

	def script_reportTime(self, gesture):
		status = self._get_status()
		if not status:
			return
		remaining_ms = max(0, status.length_seconds * 1000 - status.position_ms)
		ui.message(
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

	def script_reportStatus(self, gesture):
		status = self._get_status()
		if status:
			ui.message(format_status(status).replace("\r\n", ". "))

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

	def script_showGeneralInfo(self, gesture):
		self._show_info_section(1, _("XMPlay general track information"))

	def script_showMessageInfo(self, gesture):
		self._show_info_section(2, _("XMPlay message and tags"))

	def script_showSampleInfo(self, gesture):
		self._show_info_section(3, _("XMPlay samples"))

	def script_showAllTrackInfo(self, gesture):
		try:
			dialog = TrackInformationDialog(gui.mainFrame, self.controller)
			dialog.Show()
			dialog.Raise()
		except Exception as error:
			self._show_error(error)

	def script_showVisibleWindowText(self, gesture):
		text = self._object_text(api.getForegroundObject())
		ui.browseableMessage(
			text or _("No readable text was detected in this XMPlay window."),
			_("XMPlay window text"),
		)

	def script_playPause(self, gesture):
		self._run_command(80)

	def script_stop(self, gesture):
		self._run_command(81)

	def script_previous(self, gesture):
		self._run_command(129)

	def script_next(self, gesture):
		self._run_command(128)

	def script_seekBackward(self, gesture):
		self._run_command(83)

	def script_seekForward(self, gesture):
		self._run_command(82)

	def script_volumeUp(self, gesture):
		self._run_command(512, "volume")

	def script_volumeDown(self, gesture):
		self._run_command(513, "volume")

	def script_mute(self, gesture):
		self._run_command(523, "volume")

	def script_loop(self, gesture):
		self._run_command(9, "loop")
