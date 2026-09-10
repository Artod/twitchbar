"""What a tray backend must provide, and the immutable view it renders."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MenuLine:
    """One menu row: its text and, when clicking it should open a page, the URL."""

    text: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class TrayView:
    """One frame of the menu: bar text, a short badge, summary rows, recent messages, chatters."""

    title: str
    badge: str
    summary: tuple[MenuLine, ...]
    recent: tuple[MenuLine, ...]
    chatters: tuple[MenuLine, ...]
    quiet: bool


@dataclass(frozen=True, slots=True)
class TrayActions:
    """What the menu's clickable items do."""

    menu_opened: Callable[[], None]
    open_url: Callable[[str], None]
    open_channel: Callable[[], None]
    open_chat: Callable[[], None]
    open_dashboard: Callable[[], None]
    toggle_quiet: Callable[[], None]
    quit: Callable[[], None]


class Tray(Protocol):
    """A menu bar / system tray presence driven from the UI thread."""

    def run(self, tick: Callable[[], None], interval: float) -> None:
        """Block on the platform's main loop; ``tick`` runs every ``interval`` s, UI thread."""
        ...

    def render(self, view: TrayView) -> None:
        """Show ``view``; cheap when nothing changed."""
        ...

    def stop(self) -> None:
        """Leave the main loop."""
        ...
