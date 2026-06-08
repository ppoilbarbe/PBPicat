"""Platform-specific helpers. Loaded once at import time."""

import sys

if sys.platform == "win32":  # pragma: no cover
    from ._windows import config_dir, open_default, open_with
elif sys.platform == "darwin":  # pragma: no cover
    from ._macos import config_dir, open_default, open_with
else:
    from ._linux import config_dir, open_default, open_with

__all__ = ["config_dir", "open_default", "open_with"]
