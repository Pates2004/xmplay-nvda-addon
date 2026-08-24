"""XMPlay Accessibility category in NVDA Settings."""

from __future__ import annotations

import addonHandler
import config
import gui
from gui.settingsDialogs import SettingsPanel
import wx

from .configuration import CONFIG_SECTION, DEFAULTS, ensure_config


addonHandler.initTranslation()


class XMPlaySettingsPanel(SettingsPanel):
	title = _("XMPlay")

	SETTING_LABELS = (
		("announceFocusSummary", _("Speak a detailed playback summary when XMPlay gains &focus")),
		("announceTrackChanges", _("Automatically announce &track changes")),
		("announcePlaybackState", _("Automatically announce play, pause, and &stop")),
		("announceVolumeChanges", _("Automatically announce &volume changes")),
		("announceBalanceChanges", _("Automatically announce &balance changes")),
		("announceHelpBubbles", _("Announce XMPlay &help bubbles and tooltips")),
		("announceCommandFeedback", _("Speak feedback after add-on and XMPlay &keyboard commands")),
		(
			"announceControlCenterFeedback",
			_("Speak confirmations and playlist results in the accessible control &center"),
		),
	)

	def makeSettings(self, settingsSizer):
		ensure_config()
		helper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		helper.addItem(
			wx.StaticText(
				self,
				label=_(
					"Choose which automatic XMPlay messages NVDA should speak. "
					"Manually requested reports and errors are always spoken."
				),
			)
		)
		self._controls = {}
		for key, label in self.SETTING_LABELS:
			control = helper.addItem(wx.CheckBox(self, label=label))
			control.SetValue(bool(config.conf[CONFIG_SECTION][key]))
			self._controls[key] = control
		self._defaultsButton = helper.addItem(wx.Button(self, label=_("Restore &defaults")))
		self._defaultsButton.Bind(wx.EVT_BUTTON, self._on_restore_defaults)

	def postInit(self):
		self._controls["announceFocusSummary"].SetFocus()

	def _on_restore_defaults(self, event):
		for key, default in DEFAULTS.items():
			self._controls[key].SetValue(default)

	def onSave(self):
		for key, control in self._controls.items():
			config.conf[CONFIG_SECTION][key] = control.GetValue()
