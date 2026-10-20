"""XMPlay Accessibility category in NVDA Settings."""

from __future__ import annotations

import config
import gui
from gui.settingsDialogs import SettingsPanel
import wx

from .configuration import (
	BOOLEAN_DEFAULTS,
	CONFIG_SECTION,
	LANGUAGE_ENGLISH,
	LANGUAGE_POLISH,
	LANGUAGE_SYSTEM,
	ensure_config,
)
from .localization import _, invalidate_translation_cache


class XMPlaySettingsPanel(SettingsPanel):
	title = _("XMPlay")

	LANGUAGE_OPTIONS = (
		(LANGUAGE_SYSTEM, _("System language (default)")),
		(LANGUAGE_ENGLISH, _("English")),
		(LANGUAGE_POLISH, _("Polish")),
	)

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
		("showUsageHints", _("Show optional usage &hints in add-on settings")),
	)

	def makeSettings(self, settingsSizer):
		ensure_config()
		helper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self._languageChoice = helper.addLabeledControl(
			_("Add-on &language:"),
			wx.Choice,
			choices=[label for value, label in self.LANGUAGE_OPTIONS],
		)
		selected_language = str(config.conf[CONFIG_SECTION]["interfaceLanguage"])
		language_values = [value for value, label in self.LANGUAGE_OPTIONS]
		try:
			self._languageChoice.SetSelection(language_values.index(selected_language))
		except ValueError:
			self._languageChoice.SetSelection(0)
		self._restartHint = helper.addItem(
			wx.StaticText(
				self,
				label=_("Restart NVDA after changing the add-on language."),
			)
		)
		self._usageHint = helper.addItem(
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
		self._controls["showUsageHints"].Bind(wx.EVT_CHECKBOX, self._on_hint_visibility_changed)
		self._update_hint_visibility()
		self._defaultsButton = helper.addItem(wx.Button(self, label=_("Restore &defaults")))
		self._defaultsButton.Bind(wx.EVT_BUTTON, self._on_restore_defaults)

	def postInit(self):
		self._languageChoice.SetFocus()

	def _on_restore_defaults(self, event):
		self._languageChoice.SetSelection(0)
		for key, default in BOOLEAN_DEFAULTS.items():
			self._controls[key].SetValue(default)
		self._update_hint_visibility()

	def _update_hint_visibility(self):
		show = self._controls["showUsageHints"].GetValue()
		self._restartHint.Show(show)
		self._usageHint.Show(show)
		self.Layout()

	def _on_hint_visibility_changed(self, event):
		self._update_hint_visibility()
		event.Skip()

	def onSave(self):
		selection = max(0, self._languageChoice.GetSelection())
		config.conf[CONFIG_SECTION]["interfaceLanguage"] = self.LANGUAGE_OPTIONS[selection][0]
		for key, control in self._controls.items():
			config.conf[CONFIG_SECTION][key] = control.GetValue()
		invalidate_translation_cache()
