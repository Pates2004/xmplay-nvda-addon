"""Persistent NVDA configuration for XMPlay Accessibility."""

from __future__ import annotations

import config


CONFIG_SECTION = "xmplayAccessibility"

DEFAULTS = {
	"announceFocusSummary": True,
	"announceTrackChanges": True,
	"announcePlaybackState": True,
	"announceVolumeChanges": True,
	"announceBalanceChanges": True,
	"announceHelpBubbles": True,
	"announceCommandFeedback": True,
	"announceControlCenterFeedback": True,
}

CONFIG_SPEC = {
	key: f"boolean(default={'true' if default else 'false'})"
	for key, default in DEFAULTS.items()
}


def ensure_config() -> None:
	"""Register the configuration specification once per NVDA session."""
	if CONFIG_SECTION not in config.conf.spec:
		config.conf.spec[CONFIG_SECTION] = CONFIG_SPEC
	else:
		config.conf.spec[CONFIG_SECTION].update(CONFIG_SPEC)


def get_setting(key: str) -> bool:
	ensure_config()
	return bool(config.conf[CONFIG_SECTION][key])


ensure_config()
