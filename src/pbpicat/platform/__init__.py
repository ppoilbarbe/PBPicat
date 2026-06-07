"""Platform-specific file-open helpers. Loaded once at import time."""

import sys

if sys.platform == "win32":  # pragma: no cover
    from ._windows import open_default, open_with
elif sys.platform == "darwin":  # pragma: no cover
    from ._macos import open_default, open_with
else:
    from ._linux import open_default, open_with

__all__ = ["open_default", "open_with"]
