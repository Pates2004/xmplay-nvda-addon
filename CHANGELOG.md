# Changelog

## 1.4.1 — 2026-11-15

- Refreshed track/time summaries whenever XMPlay regains focus.
- Fixed muted keyboard feedback being repeated by the monitor; combined simultaneous changes and multi-action shortcut feedback.
- Suppressed delayed feedback after leaving XMPlay or terminating the module.
- Prevented concurrent playlist operations, restored controls after failures, and cancelled remaining work on close.
- Implemented Enter on the playlist and fixed remote strings ending near a memory-page boundary.
- Bound DDE conversations to the selected XMPlay process instead of the first available instance.
- Corrected native file-opening syntax and Unicode DDE encoding; covered spaces and Polish filenames with real-player integration checks.
- Made explicit playlist replacement independent of XMPlay's rapid-open batching and Integration default action.
- Covered host-driven dialog destruction and applied the optional-hints setting to the search placeholder.
- Kept archive validation active under optimized Python and added project instruction/audit navigation.

## 1.4.0 — 2026-10-20

- Fixed Space, arrow keys and customized native shortcuts being intercepted in XMPlay Options and other dialogs.
- Added foreground, focused-control and menu checks; dialog-opening actions keep their native behavior.
- Protected against replaying partially executed shortcuts and retained the working shortcut map after transient INI read errors.
- Fixed the Play selected callback, delayed refresh after closing, and stale playlist entries after failed reloads.
- Completed Polish backend error messages and added a persistent switch for optional settings hints.
- Fixed NVDA's translation initialization overriding the add-on's selected language.
- Corrected the full-left balance report from 99% to 100%.
- Moved local final packages into the ignored Installfiles directory and added archive validation.

## 1.3.0 — 2026-08-24

- Added an add-on language selector with Windows system language, English, and Polish choices.
- Made the selected language independent of NVDA's own interface language.
- Clarified that native XMPlay shortcut feedback follows each user's current key assignments.

## 1.2.0 — 2026-08-24

- Replaced the raw XMPlay focus text with a concise, labelled playback summary.
- Removed the redundant player prefix and custom-interface instruction from focus speech.
- Added immediate feedback without the previous 180–650 ms timer delay.
- Added dynamic detection and feedback for shortcuts configured in xmplay.ini.
- Registered all add-on commands globally so the XMPlay category is always available in Input Gestures.

## 1.1.0 — 2026-08-24

- Added an XMPlay category to NVDA Settings.
- Added independent switches for welcome, track, state, volume, balance, tooltip, keyboard-command, and control-center announcements.
- Added a Restore defaults button.
- Documented that every shortcut can be changed in NVDA's Input Gestures dialog.

## 1.0.0 — 2026-08-24

- Initial release with automatic playback announcements.
- Added a fully accessible, searchable playlist and control center.
- Added playback, volume, time, status, and track-information commands.
- Added complete English and Polish interfaces.
