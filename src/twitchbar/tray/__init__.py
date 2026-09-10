"""Tray backends: native menu bar on macOS (rumps), pystray everywhere else."""

from __future__ import annotations

import sys

from twitchbar.tray.base import Tray, TrayActions


def build_tray(kind: str, actions: TrayActions, *, recent_slots: int) -> Tray:
    """Instantiate the backend named by ``kind`` ("auto", "mac" or "generic")."""
    if kind == "auto":
        kind = "mac" if sys.platform == "darwin" else "generic"
    if kind == "mac":
        from twitchbar.tray.mac import MacTray

        return MacTray(actions, recent_slots=recent_slots)
    from twitchbar.tray.generic import GenericTray

    return GenericTray(actions)
