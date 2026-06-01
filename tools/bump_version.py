#!/usr/bin/env python3
"""Bump or set the project version across all version-bearing files.

Usage:
    python tools/bump_version.py major          # x.y.z → (x+1).0.0
    python tools/bump_version.py minor          # x.y.z → x.(y+1).0
    python tools/bump_version.py patch          # x.y.z → x.y.(z+1)
    python tools/bump_version.py set <x.y.z>   # force an explicit version

Files updated:
    pyproject.toml
    src/pbpicat/__main__.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

_FILES = [
    (ROOT / "pyproject.toml", re.compile(r'(version\s*=\s*")[0-9]+\.[0-9]+\.[0-9]+(")'), r"\g<1>{version}\g<2>"),
    (
        ROOT / "src/pbpicat/__main__.py",
        re.compile(r'(setApplicationVersion\(")[0-9]+\.[0-9]+\.[0-9]+("\))'),
        r"\g<1>{version}\g<2>",
    ),
]


def current_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', text)
    if not m:
        sys.exit("error: could not read current version from pyproject.toml")
    return m.group(1)


def bump(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    sys.exit(f"error: unknown part {part!r}")


def apply(new_version: str) -> None:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", new_version):
        sys.exit(f"error: {new_version!r} is not a valid semver (x.y.z)")
    for path, pattern, replacement in _FILES:
        text = path.read_text(encoding="utf-8")
        new_text, n = pattern.subn(replacement.format(version=new_version), text)
        if n == 0:
            print(f"  warning: no match in {path.relative_to(ROOT)}", file=sys.stderr)
        else:
            path.write_text(new_text, encoding="utf-8")
            print(f"  updated {path.relative_to(ROOT)}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)

    old = current_version()

    if args[0] in ("major", "minor", "patch"):
        new = bump(old, args[0])
    elif args[0] == "set":
        if len(args) < 2:
            sys.exit("error: 'set' requires a version argument (e.g. set 2.0.0)")
        new = args[1]
    else:
        sys.exit(f"error: unknown command {args[0]!r}")

    print(f"{old} → {new}")
    apply(new)


if __name__ == "__main__":
    main()
