"""Registers XMPlay Accessibility settings with NVDA."""

from __future__ import annotations

import addonHandler
import api
import globalPluginHandler
import gui
from scriptHandler import script

from .configuration import ensure_config
from .localization import _
from .settingsPanel import XMPlaySettingsPanel


addonHandler.initTranslation()

SCRIPT_CATEGORY = _("XMPlay")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()
		ensure_config()
		categories = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
		if XMPlaySettingsPanel not in categories:
			categories.append(XMPlaySettingsPanel)

	def terminate(self):
		categories = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
		if XMPlaySettingsPanel in categories:
			categories.remove(XMPlaySettingsPanel)
		super().terminate()

	def _dispatch_to_xmplay(self, command_name: str, gesture):
		focus = api.getFocusObject()
		app_module = getattr(focus, "appModule", None)
		if getattr(app_module, "appName", "").casefold() == "xmplay":
			command = getattr(app_module, f"script_{command_name}", None)
			if command:
				command(gesture)
				return
		# Preserve ordinary application shortcuts outside XMPlay. Unassigned NVDA-key
		# combinations remain consumed, as NVDA normally does for its own commands.
		if not any("nvda" in identifier.casefold() for identifier in gesture.identifiers):
			gesture.send()

	@script(
		description=_("Opens the accessible XMPlay control center and playlist."),
		gesture="kb:NVDA+shift+x",
		category=SCRIPT_CATEGORY,
	)
	def script_showControlCenter(self, gesture):
		self._dispatch_to_xmplay("showControlCenter", gesture)

	@script(
		description=_("Opens the accessible XMPlay playlist."),
		gesture="kb:NVDA+shift+p",
		category=SCRIPT_CATEGORY,
	)
	def script_showPlaylist(self, gesture):
		self._dispatch_to_xmplay("showPlaylist", gesture)

	@script(
		description=_("Announces the current track title and playlist position."),
		gesture="kb:NVDA+shift+i",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_reportTrack(self, gesture):
		self._dispatch_to_xmplay("reportTrack", gesture)

	@script(
		description=_("Announces elapsed, total, and remaining time."),
		gesture="kb:NVDA+shift+t",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_reportTime(self, gesture):
		self._dispatch_to_xmplay("reportTime", gesture)

	@script(
		description=_("Announces complete XMPlay playback status."),
		gesture="kb:NVDA+shift+s",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_reportStatus(self, gesture):
		self._dispatch_to_xmplay("reportStatus", gesture)

	@script(
		description=_("Announces XMPlay volume and balance."),
		gesture="kb:NVDA+shift+v",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_reportVolume(self, gesture):
		self._dispatch_to_xmplay("reportVolume", gesture)

	@script(
		description=_("Shows general information for the current track."),
		gesture="kb:NVDA+shift+g",
		category=SCRIPT_CATEGORY,
	)
	def script_showGeneralInfo(self, gesture):
		self._dispatch_to_xmplay("showGeneralInfo", gesture)

	@script(
		description=_("Shows the current track's message and tags."),
		gesture="kb:NVDA+shift+m",
		category=SCRIPT_CATEGORY,
	)
	def script_showMessageInfo(self, gesture):
		self._dispatch_to_xmplay("showMessageInfo", gesture)

	@script(
		description=_("Shows sample and instrument information for the current module."),
		gesture="kb:NVDA+shift+a",
		category=SCRIPT_CATEGORY,
	)
	def script_showSampleInfo(self, gesture):
		self._dispatch_to_xmplay("showSampleInfo", gesture)

	@script(
		description=_("Opens all available information for the current track."),
		gesture="kb:NVDA+shift+d",
		category=SCRIPT_CATEGORY,
	)
	def script_showAllTrackInfo(self, gesture):
		self._dispatch_to_xmplay("showAllTrackInfo", gesture)

	@script(
		description=_("Shows all text NVDA can detect in the current XMPlay window."),
		gesture="kb:NVDA+shift+o",
		category=SCRIPT_CATEGORY,
		speakOnDemand=True,
	)
	def script_showVisibleWindowText(self, gesture):
		self._dispatch_to_xmplay("showVisibleWindowText", gesture)

	@script(
		description=_("Plays or pauses XMPlay."),
		gesture="kb:control+shift+space",
		category=SCRIPT_CATEGORY,
	)
	def script_playPause(self, gesture):
		self._dispatch_to_xmplay("playPause", gesture)

	@script(
		description=_("Stops XMPlay."),
		gesture="kb:control+shift+s",
		category=SCRIPT_CATEGORY,
	)
	def script_stop(self, gesture):
		self._dispatch_to_xmplay("stop", gesture)

	@script(
		description=_("Plays the previous track."),
		gesture="kb:control+shift+leftArrow",
		category=SCRIPT_CATEGORY,
	)
	def script_previous(self, gesture):
		self._dispatch_to_xmplay("previous", gesture)

	@script(
		description=_("Plays the next track."),
		gesture="kb:control+shift+rightArrow",
		category=SCRIPT_CATEGORY,
	)
	def script_next(self, gesture):
		self._dispatch_to_xmplay("next", gesture)

	@script(
		description=_("Seeks backward in the current track."),
		gesture="kb:control+shift+pageUp",
		category=SCRIPT_CATEGORY,
	)
	def script_seekBackward(self, gesture):
		self._dispatch_to_xmplay("seekBackward", gesture)

	@script(
		description=_("Seeks forward in the current track."),
		gesture="kb:control+shift+pageDown",
		category=SCRIPT_CATEGORY,
	)
	def script_seekForward(self, gesture):
		self._dispatch_to_xmplay("seekForward", gesture)

	@script(
		description=_("Raises XMPlay volume."),
		gesture="kb:control+shift+upArrow",
		category=SCRIPT_CATEGORY,
	)
	def script_volumeUp(self, gesture):
		self._dispatch_to_xmplay("volumeUp", gesture)

	@script(
		description=_("Lowers XMPlay volume."),
		gesture="kb:control+shift+downArrow",
		category=SCRIPT_CATEGORY,
	)
	def script_volumeDown(self, gesture):
		self._dispatch_to_xmplay("volumeDown", gesture)

	@script(
		description=_("Mutes or restores XMPlay volume."),
		gesture="kb:control+shift+m",
		category=SCRIPT_CATEGORY,
	)
	def script_mute(self, gesture):
		self._dispatch_to_xmplay("mute", gesture)

	@script(
		description=_("Cycles XMPlay's track loop mode."),
		gesture="kb:control+shift+l",
		category=SCRIPT_CATEGORY,
	)
	def script_loop(self, gesture):
		self._dispatch_to_xmplay("loop", gesture)
