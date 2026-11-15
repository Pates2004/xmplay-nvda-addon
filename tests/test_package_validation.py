from __future__ import annotations

import importlib.util
import io
from pathlib import Path
from unittest import TestCase, mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("addon_package_validation", ROOT / "tools/validate_addon.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class PackageValidationTest(TestCase):
	def archive(self, altered=None, omitted=None):
		buffer = io.BytesIO()
		with zipfile.ZipFile(buffer, "w") as package:
			for path in (ROOT / "addon").rglob("*"):
				if not path.is_file():
					continue
				name = path.relative_to(ROOT / "addon").as_posix()
				if name != omitted:
					package.writestr(name, (altered or {}).get(name, path.read_bytes()))
		return buffer.getvalue()

	def validate_memory(self, data, name=None):
		version = next(line.partition("=")[2].strip() for line in (ROOT / "addon/manifest.ini").read_text().splitlines() if line.startswith("version ="))
		path = mock.Mock(name=name or f"xmplayAccessibility-{version}.nvda-addon")
		path.name = name or f"xmplayAccessibility-{version}.nvda-addon"
		path.read_bytes.return_value = data
		with zipfile.ZipFile(io.BytesIO(data)) as package, mock.patch.object(validator.zipfile, "ZipFile", return_value=package):
			return validator.validate(path)

	def test_ready_archive_matches_sources_and_catalog(self):
		result = self.validate_memory(self.archive())
		self.assertGreater(result["files"], 10)
		self.assertGreater(result["translations"], 100)

	def test_modified_python_is_rejected(self):
		with self.assertRaisesRegex(ValueError, "Source mismatch"):
			self.validate_memory(self.archive(altered={"appModules/xmplay/backend.py": b"raise RuntimeError('broken')"}))

	def test_missing_document_is_rejected(self):
		with self.assertRaisesRegex(ValueError, "inventory"):
			self.validate_memory(self.archive(omitted="doc/pl/readme.html"))

	def test_wrong_release_filename_is_rejected(self):
		with self.assertRaisesRegex(ValueError, "Filename/version"):
			self.validate_memory(self.archive(), "wrong.nvda-addon")
