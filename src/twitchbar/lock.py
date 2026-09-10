"""One running twitchbar per user: a second launch (a double-click, a login item) exits quietly."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import IO


def acquire(path: Path) -> IO[str] | None:
    """Lock ``path`` exclusively: the handle to keep open, or None if another process has it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle
