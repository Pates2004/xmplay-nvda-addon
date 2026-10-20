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
- English and Polish interfaces with a setting for the Windows system language (default), English, or Polish.

## Installation

Download the package from [GitHub Releases](https://github.com/Pates2004/xmplay-nvda-addon/releases/latest) or build it locally. Open `xmplayAccessibility-1.4.0.nvda-addon`, confirm installation in NVDA, and restart NVDA. With XMPlay focused, press `NVDA+Shift+X` to open the accessible control center.

## Settings and commands

Open NVDA Settings and select the **XMPlay** category to choose the add-on language and what is announced automatically. Restart NVDA after changing the language so every command description and panel label is reloaded. The **XMPlay** category is always present in NVDA's **Input Gestures** dialog, where every add-on command can be changed or removed. While XMPlay has focus, the add-on reads the current `xmplay.ini` shortcut map, regardless of the keys assigned, and announces supported native actions including volume, playback, equalizer, reverb, DSP bypass, and looping changes.

The complete command reference is available in [English](addon/doc/en/readme.html) and [Polish](addon/doc/pl/readme.html).

Native keyboard feedback applies only to XMPlay's main skinned player and panels. In Options, file dialogs, text fields, information windows, and menus, Space, arrows, letters and other keys keep their normal behavior. Actions that open dialogs or edit the playlist are handled directly by XMPlay. Playback shortcuts assigned in NVDA are also suspended in XMPlay dialogs; manually requested information remains available.

Polish covers the add-on's controls, status reports, command descriptions, and backend errors. It does not translate the original visual XMPlay settings or third-party plugin windows. Optional settings hints can be hidden with a persistent checkbox in the XMPlay settings category.

## Building

Requirements on Windows:

- Python 3.13
- GNU gettext (`xgettext` and `msgfmt` on `PATH`)
- PowerShell

Run:

```powershell
.\build.ps1
```

The build validates Python syntax, checks that every message has a Polish translation, compiles the gettext catalog, runs the test suite, and creates `Installfiles/xmplayAccessibility-1.4.0.nvda-addon` inside the repository. A second validator checks the archive, source parity, compiled catalog and translation parameters. Existing packages are never overwritten; move a previous build before rebuilding.

## Compatibility

- Minimum NVDA version: 2024.1
- Last tested NVDA version: 2026.1
- Tested XMPlay version: 3.8.4

Licensed under GPL-2.0-or-later. See [LICENSE.md](LICENSE.md).
