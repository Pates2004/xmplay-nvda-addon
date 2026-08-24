"""Build the Polish PO file from the reviewed JSON translation table."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
	ROOT / "addon" / "appModules" / "xmplay" / "__init__.py",
	ROOT / "addon" / "appModules" / "xmplay" / "dialogs.py",
	ROOT / "addon" / "globalPlugins" / "xmplayAccessibility" / "__init__.py",
	ROOT / "addon" / "globalPlugins" / "xmplayAccessibility" / "settingsPanel.py",
]
TRANSLATIONS = ROOT / "translations_pl.json"
OUTPUT = ROOT / "addon" / "locale" / "pl" / "LC_MESSAGES" / "nvda.po"


def extracted_messages() -> set[str]:
	messages: set[str] = set()
	for path in SOURCE_FILES:
		tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
		for node in ast.walk(tree):
			if (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Name)
				and node.func.id == "_"
				and node.args
				and isinstance(node.args[0], ast.Constant)
				and isinstance(node.args[0].value, str)
			):
				messages.add(node.args[0].value)
	return messages


def po_string(value: str) -> str:
	return json.dumps(value, ensure_ascii=False)


def main() -> None:
	translations = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
	messages = extracted_messages()
	missing = sorted(messages - translations.keys())
	extra = sorted(translations.keys() - messages)
	if missing:
		raise SystemExit("Missing Polish translations:\n" + "\n".join(missing))
	if extra:
		raise SystemExit("Obsolete Polish translations:\n" + "\n".join(extra))

	header = (
		'msgid ""\n'
		'msgstr ""\n'
		'"Project-Id-Version: xmplayAccessibility 1.3.0\\n"\n'
		'"PO-Revision-Date: 2026-08-24 00:00+0200\\n"\n'
		'"Last-Translator: Pates and OpenAI Codex\\n"\n'
		'"Language-Team: Polish\\n"\n'
		'"Language: pl_PL\\n"\n'
		'"MIME-Version: 1.0\\n"\n'
		'"Content-Type: text/plain; charset=UTF-8\\n"\n'
		'"Content-Transfer-Encoding: 8bit\\n"\n'
		'"Plural-Forms: nplurals=4; plural=(n==1 ? 0 : (n%10>=2 && n%10<=4) && '
		'(n%100<12 || n%100>14) ? 1 : n!=1 && (n%10>=0 && n%10<=1) || '
		'(n%10>=5 && n%10<=9) || (n%100>=12 && n%100<=14) ? 2 : 3);\\n"\n\n'
	)
	entries = []
	for message in sorted(messages, key=lambda value: (value.casefold(), value)):
		entries.append(f"msgid {po_string(message)}\nmsgstr {po_string(translations[message])}\n")
	OUTPUT.write_text(header + "\n".join(entries), encoding="utf-8", newline="\n")
	print(f"Wrote {OUTPUT} with {len(messages)} translated messages")


if __name__ == "__main__":
	main()
