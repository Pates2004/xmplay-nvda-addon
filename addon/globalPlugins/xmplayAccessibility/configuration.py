"""Persistent NVDA configuration for XMPlay Accessibility."""

from __future__ import annotations

import config


CONFIG_SECTION = "xmplayAccessibility"

LANGUAGE_SYSTEM = "system"
LANGUAGE_ENGLISH = "en"
LANGUAGE_POLISH = "pl"
LANGUAGE_CHOICES = (LANGUAGE_SYSTEM, LANGUAGE_ENGLISH, LANGUAGE_POLISH)

BOOLEAN_DEFAULTS = {
	"announceFocusSummary": True,
	"announceTrackChanges": True,
	"announcePlaybackState": True,
	"announceVolumeChanges": True,
	"announceBalanceChanges": True,
	"announceHelpBubbles": True,
	"announceCommandFeedback": True,
	"announceControlCenterFeedback": True,
}

DEFAULTS = {
	"interfaceLanguage": LANGUAGE_SYSTEM,
	**BOOLEAN_DEFAULTS,
}

CONFIG_SPEC = {
	key: f"boolean(default={'true' if default else 'false'})"
	for key, default in BOOLEAN_DEFAULTS.items()
}
CONFIG_SPEC["interfaceLanguage"] = "option(system, en, pl, default=system)"


def ensure_config() -> None:
	"""Register the configuration specification once per NVDA session."""
	if CONFIG_SECTION not in config.conf.spec:
		config.conf.spec[CONFIG_SECTION] = CONFIG_SPEC
	else:
		config.conf.spec[CONFIG_SECTION].update(CONFIG_SPEC)


def get_setting(key: str) -> bool:
	ensure_config()
	return bool(config.conf[CONFIG_SECTION][key])


def get_interface_language() -> str:
	"""Return the selected add-on language, falling back to the system language."""
	ensure_config()
	value = str(config.conf[CONFIG_SECTION]["interfaceLanguage"])
	return value if value in LANGUAGE_CHOICES else LANGUAGE_SYSTEM


ensure_config()
