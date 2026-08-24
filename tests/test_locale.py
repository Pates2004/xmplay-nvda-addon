from __future__ import annotations

import gettext
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PolishLocaleTest(unittest.TestCase):
	def test_compiled_catalog_matches_reviewed_translations(self):
		translations = json.loads((ROOT / "translations_pl.json").read_text(encoding="utf-8"))
		catalog = gettext.translation(
			"nvda",
			localedir=ROOT / "addon" / "locale",
			languages=["pl"],
		)
		for source, expected in translations.items():
			self.assertEqual(catalog.gettext(source), expected, source)


if __name__ == "__main__":
	unittest.main()
