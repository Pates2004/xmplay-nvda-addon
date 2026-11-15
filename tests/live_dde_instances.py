"""Validate DDE targeting against two explicitly prepared, isolated XMPlay profiles.

Each directory must contain its own xmplay.exe and xmplay.ini, not a user's
normal profile. The fixture writes only two generated short silent WAV files.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import wave


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("first", type=Path)
	parser.add_argument("second", type=Path)
	args = parser.parse_args()
	roots = [args.first.resolve(), args.second.resolve()]
	if roots[0] == roots[1]:
		raise ValueError("Two separate fixture profiles are required")
	for root in roots:
		if root.is_symlink() or root.is_junction():
			raise ValueError("Fixture roots must not be links")
		allowed = {"xmplay.exe", "xmplay.ini", "xmplay.library", "xmplay.library~", "xmplay.pls",
			"isolated-instance-1.wav", "isolated-instance-2.wav",
			"isolated-instance-1 Żółć (fixture).wav", "isolated-instance-2 Żółć (fixture).wav",
			"spaces Żółć fixture.wav", "spaces Żółć (live) fixture.wav"}
		if not {item.name for item in root.iterdir()} <= allowed:
			raise ValueError(f"Unexpected data in the isolated fixture: {root}")
		if "MultiInstance=1" not in (root / "xmplay.ini").read_text():
			raise ValueError("Fixture must enable separate instances")
	path = Path(__file__).resolve().parents[1] / "addon/appModules/xmplay/backend.py"
	spec = importlib.util.spec_from_file_location("dde_live_backend", path)
	backend = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = backend
	spec.loader.exec_module(backend)
	processes = []
	controllers = []
	files = []
	try:
		for index, root in enumerate(roots):
			file = root / f"isolated-instance-{index + 1} Żółć (fixture).wav"
			if not file.exists():
				with wave.open(str(file), "wb") as audio:
					audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
					audio.writeframes(b"\0\0" * 1600)
			files.append(file)
			startup = subprocess.STARTUPINFO()
			startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
			startup.wShowWindow = 0
			process = subprocess.Popen([str(root / "xmplay.exe")], cwd=root, startupinfo=startup)
			processes.append(process)
			controller = backend.XMPlayController(process.pid)
			controllers.append(controller)
			deadline = time.monotonic() + 5
			while not controller.is_available() and time.monotonic() < deadline:
				time.sleep(0.05)
			if not controller.is_available():
				raise RuntimeError("Fixture process failed to start")
		for controller, file in zip(controllers, files):
			controller.open_paths([str(file)], replace=True)
			deadline = time.monotonic() + 4
			while not controller.playlist_length() and time.monotonic() < deadline:
				time.sleep(0.1)
		for controller, file in zip(controllers, files):
			tracks = controller.get_playlist()
			if len(tracks) != 1 or Path(tracks[0].path).resolve() != file:
				raise AssertionError(f"DDE wrote to the wrong instance: {tracks}")
			general = controller.request_info(1)
			if file.name not in general:
				raise AssertionError(f"DDE information came from the wrong instance: {general}")
			controller.play_track(0)
		controllers[0].open_paths([str(files[1])], replace=False)
		if controllers[0].playlist_length() != 2 or controllers[1].playlist_length() != 1:
			raise AssertionError("Append affected the wrong playlist")
		# Exercise replacement again immediately, without waiting for XMPlay's
		# native file-open batching window to expire.
		controllers[0].open_paths([str(files[0])], replace=True)
		if controllers[0].playlist_length() != 1 or Path(controllers[0].get_track(0).path).resolve() != files[0]:
			raise AssertionError("Immediate replacement was merged into the old playlist")
		print(json.dumps(dict(instances=2, playlist_writes_targeted=True, information_targeted=True,
			selected_track_played=True, unicode_spaces_parentheses=True, append_and_immediate_replace=True)))
	finally:
		for controller, process in zip(controllers, processes):
			if process.poll() is None:
				try:
					controller.command(10)
					process.wait(timeout=3)
				except (backend.XMPlayError, subprocess.TimeoutExpired):
					if process.poll() is None:
						process.terminate()
						process.wait(timeout=3)


if __name__ == "__main__":
	main()
