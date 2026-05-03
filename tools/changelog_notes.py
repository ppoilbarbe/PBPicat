#!/usr/bin/env python3
"""Extract the release notes for a given version from CHANGELOG.md.

Usage:
    python tools/changelog_notes.py 1.0.0

Prints the body of the matching ## [VERSION] section to stdout and exits 0.
Exits 1 if the version is not found.
"""

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).parent.parent / "CHANGELOG.md"


def extract(version: str) -> str:
    text = CHANGELOG.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\].*?\n(.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        print(f"error: version {version!r} not found in CHANGELOG.md", file=sys.stderr)
        sys.exit(1)
    return m.group(1).strip()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <version>", file=sys.stderr)
        sys.exit(1)
    print(extract(sys.argv[1]))
