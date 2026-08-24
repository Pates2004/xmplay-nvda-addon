"""Language selection independent of NVDA's own interface language."""

from __future__ import annotations

import ctypes
import gettext
import locale
from pathlib import Path

from .configuration import (
	LANGUAGE_ENGLISH,
	LANGUAGE_POLISH,
	LANGUAGE_SYSTEM,
	get_interface_language,
)


_ADDON_ROOT = Path(__file__).resolve().parents[2]
_POLISH_PRIMARY_LANGUAGE_ID = 0x15
_translation_cache: dict[str, gettext.NullTranslations] = {}


def system_language() -> str:
	"""Resolve the Windows display language to one of the bundled languages."""
	try:
		language_id = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
		if language_id & 0x3FF == _POLISH_PRIMARY_LANGUAGE_ID:
			return LANGUAGE_POLISH
		return LANGUAGE_ENGLISH
	except (AttributeError, OSError, ValueError):
		# This fallback is mainly useful when running the unit tests outside Windows.
		language_name = (locale.getlocale()[0] or "").casefold()
		return LANGUAGE_POLISH if language_name.startswith("pl") else LANGUAGE_ENGLISH


def resolve_language(selected: str, detected_system_language: str | None = None) -> str:
	"""Resolve a saved selection to an installed language."""
	if selected == LANGUAGE_POLISH:
		return LANGUAGE_POLISH
	if selected == LANGUAGE_ENGLISH:
		return LANGUAGE_ENGLISH
	if selected == LANGUAGE_SYSTEM:
		detected = detected_system_language or system_language()
		return LANGUAGE_POLISH if detected.casefold().startswith("pl") else LANGUAGE_ENGLISH
	return LANGUAGE_ENGLISH


def current_language() -> str:
	return resolve_language(get_interface_language())


def _translation() -> gettext.NullTranslations:
	language = current_language()
	translation = _translation_cache.get(language)
	if translation is None:
		translation = gettext.translation(
			"nvda",
			localedir=_ADDON_ROOT / "locale",
			languages=[language],
			fallback=True,
		)
		_translation_cache[language] = translation
	return translation


def translate(message: str) -> str:
	return _translation().gettext(message)


def invalidate_translation_cache() -> None:
	_translation_cache.clear()


_ = translate
