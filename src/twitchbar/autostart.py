"""Start twitchbar at login: a LaunchAgent on macOS, instructions elsewhere."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

LABEL = "io.github.artod.twitchbar"


def launch_agent_path() -> Path:
    """Where the macOS LaunchAgent lives."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def command() -> list[str]:
    """The command the agent runs: ``twitchbar`` if installed, else ``python -m twitchbar``."""
    binary = shutil.which("twitchbar")
    return [binary] if binary else [sys.executable, "-m", "twitchbar"]


def enable(log_dir: Path) -> Path:
    """Write and load the LaunchAgent; returns its path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LABEL,
        "ProgramArguments": command(),
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(log_dir / "launchd.out.log"),
        "StandardErrorPath": str(log_dir / "launchd.err.log"),
    }
    path = launch_agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(plist, handle)
    subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], capture_output=True, check=False
    )
    subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], check=True)
    return path


def disable() -> Path | None:
    """Unload and delete the LaunchAgent; returns the removed path, or None if there was none."""
    path = launch_agent_path()
    if not path.exists():
        return None
    subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], capture_output=True, check=False
    )
    path.unlink()
    return path
