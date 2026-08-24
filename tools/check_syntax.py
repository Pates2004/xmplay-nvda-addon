"""Compile project Python sources in memory, without creating cache files."""

from pathlib import Path


root = Path(__file__).resolve().parents[1]
paths = sorted((root / "addon").rglob("*.py")) + sorted((root / "tools").rglob("*.py")) + sorted(
	(root / "tests").rglob("*.py")
)
for path in paths:
	source = path.read_text(encoding="utf-8")
	compile(source, str(path), "exec")
print(f"Syntax OK: {len(paths)} Python files")
