"""Repository-wide checks for UTF-8 text and accidental mojibake."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}
BINARY_SUFFIXES = {".ico"}
MOJIBAKE_PATTERN = re.compile(
    "(?:"
    + chr(0x00C3) + r"[^\x00-\x7F]|"
    + chr(0x00C2) + r"[^\x00-\x7F]|"
    + chr(0x00E2) + "[" + chr(0x20AC) + chr(0x2020) + chr(0x201D) + "]|"
    + chr(0x00F0) + chr(0x0178) + "|"
    + chr(0xFFFD)
    + ")"
)


def test_repository_text_files_are_utf8_and_free_of_mojibake():
    """Catch common encoding damage before it reaches the default branch."""
    issues = []

    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue

        raw = path.read_bytes()
        if b"\x00" in raw:
            continue

        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            issues.append(f"{path.relative_to(ROOT)}: invalid UTF-8 ({exc})")
            continue

        if chr(0xFEFF) in content:
            issues.append(f"{path.relative_to(ROOT)}: unexpected UTF-8 byte-order mark")

        for line_number, line in enumerate(content.splitlines(), start=1):
            if MOJIBAKE_PATTERN.search(line):
                issues.append(
                    f"{path.relative_to(ROOT)}:{line_number}: possible mojibake"
                )

    assert not issues, "Repository text encoding issues found:\n" + "\n".join(issues)
