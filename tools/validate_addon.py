"""Validate the built archive, independent of the source-module unit tests."""

from __future__ import annotations

import argparse
import gettext
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
from string import Formatter
import zipfile


def fields(message: str) -> set[str]:
	return {name for _, name, _, _ in Formatter().parse(message) if name is not None}


def require(condition: bool, message: str) -> None:
	"""Keep validation active when Python is launched with optimization enabled."""
	if not condition:
		raise ValueError(message)


def validate(path: Path) -> dict:
	root = Path(__file__).resolve().parents[1]
	translations = json.loads((root / "translations_pl.json").read_text(encoding="utf-8"))
	with zipfile.ZipFile(path) as archive:
		require(archive.testzip() is None, "Corrupt ZIP member")
		names = archive.namelist()
		require(len(names) == len(set(names)), "Duplicate archive entries")
		files = {name for name in names if not name.endswith("/")}
		expected = {
			file.relative_to(root / "addon").as_posix()
			for file in (root / "addon").rglob("*") if file.is_file()
		}
		require(files == expected, "Package does not match the source file inventory")
		for name in files:
			member = PurePosixPath(name)
			require(not member.is_absolute() and ".." not in member.parts, f"Invalid archive path: {name}")
			require("__pycache__" not in member.parts and member.suffix not in (".pyc", ".pyo"), f"Unexpected Python cache: {name}")
			data = archive.read(name)
			require(data == (root / "addon" / name).read_bytes(), f"Source mismatch: {name}")
			if name.endswith(".py"):
				compile(data.decode("utf-8"), name, "exec")
		for language in ("en", "pl"):
			document = archive.read(f"doc/{language}/readme.html").decode("utf-8")
			require(f'lang="{language}"' in document, f"Wrong documentation language: {language}")
		catalog = gettext.GNUTranslations(io.BytesIO(archive.read("locale/pl/LC_MESSAGES/nvda.mo")))
		for message, translated in translations.items():
			require(catalog.gettext(message) == translated, f"Missing translation: {message}")
			require(fields(message) == fields(translated), f"Translation parameters differ: {message}")
		manifest = archive.read("manifest.ini").decode("utf-8")
		version = next(line.partition("=")[2].strip() for line in manifest.splitlines() if line.startswith("version ="))
		require(path.name == f"xmplayAccessibility-{version}.nvda-addon", "Filename/version mismatch")
	return dict(version=version, files=len(files), translations=len(translations), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("package", type=Path)
	arguments = parser.parse_args()
	print(json.dumps(validate(arguments.package), indent=2))
