"""Read-only integration checks against a running XMPlay process."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


def load_backend():
	path = Path(__file__).resolve().parents[1] / "addon" / "appModules" / "xmplay" / "backend.py"
	spec = importlib.util.spec_from_file_location("xmplay_backend_live", path)
	module = importlib.util.module_from_spec(spec)
	assert spec.loader
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	return module


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("pid", type=int)
	args = parser.parse_args()
	backend = load_backend()
	controller = backend.XMPlayController(args.pid)
	assert controller.is_available(), "XMPlay window not found"
	status = controller.status()
	assert status.playlist_length >= 0
	print(status)
	if status.playlist_length:
		first = controller.get_track(0)
		assert first.title or first.path
		print(first)
	for section in (1, 2, 3):
		try:
			text = controller.request_info(section)
		except backend.XMPlayError as error:
			text = f"unavailable: {error}"
		print(f"info{section}: {text[:120]!r}")
	print("Live XMPlay checks passed")


if __name__ == "__main__":
	main()
