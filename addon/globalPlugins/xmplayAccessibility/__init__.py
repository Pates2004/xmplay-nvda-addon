"""Registers XMPlay Accessibility settings with NVDA."""

from __future__ import annotations

import addonHandler
import globalPluginHandler
import gui

from .configuration import ensure_config
from .settingsPanel import XMPlaySettingsPanel


addonHandler.initTranslation()


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
