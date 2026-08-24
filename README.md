# XMPlay Accessibility for NVDA

An English and Polish NVDA add-on that makes the custom-skinned XMPlay 3.8.x interface accessible. It uses XMPlay's DDE command interface and Winamp-compatible IPC, so support does not depend on screen coordinates, OCR, or the selected skin.

## Features

- Automatic announcements for track, playback state, volume, balance, and help bubbles.
- A concise, labelled focus summary with track, state, elapsed, remaining, and total time.
- Immediate feedback for both add-on commands and shortcuts customized in XMPlay itself.
- An accessible control center with complete playback status and standard Windows controls.
- A searchable accessible playlist with titles, positions, and file paths.
- Playback, seeking, volume, mute, loop, and track-information commands.
- General information, tags, messages, module instruments, and samples in accessible text views.
- An NVDA Settings category where each kind of automatic feedback can be switched independently.
- Fully reassignable commands in NVDA's Input Gestures dialog.
- English and Polish user interfaces selected automatically from NVDA's language.

## Installation

Build the package or download the artifact from a successful GitHub Actions run. Open `xmplayAccessibility-1.2.0.nvda-addon`, confirm installation in NVDA, and restart NVDA. With XMPlay focused, press `NVDA+Shift+X` to open the accessible control center.

## Settings and commands

Open NVDA Settings and select the **XMPlay** category to choose what is announced automatically. The **XMPlay** category is always present in NVDA's **Input Gestures** dialog, where every add-on command can be changed or removed. While XMPlay has focus, the add-on also detects its current `xmplay.ini` shortcut map and announces supported native actions, including volume, playback, equalizer, reverb, DSP bypass, and looping changes.

The complete command reference is available in [English](addon/doc/en/readme.html) and [Polish](addon/doc/pl/readme.html).

## Building

Requirements on Windows:

- Python 3.13
- GNU gettext (`xgettext` and `msgfmt` on `PATH`)
- PowerShell

Run:

```powershell
.\build.ps1
```

The build validates Python syntax, checks that every message has a Polish translation, compiles the gettext catalog, runs the test suite, and creates `xmplayAccessibility-1.2.0.nvda-addon` in the parent workspace.

## Compatibility

- Minimum NVDA version: 2024.1
- Last tested NVDA version: 2026.1
- Tested XMPlay version: 3.8.4

Licensed under GPL-2.0-or-later. See [LICENSE.md](LICENSE.md).
