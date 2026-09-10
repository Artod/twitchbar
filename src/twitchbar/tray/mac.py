"""macOS menu bar via rumps: real text in the bar, native menus, no Dock icon."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import zip_longest

import rumps

from twitchbar.tray.base import MenuLine, TrayActions, TrayView

SUMMARY_SLOTS = 8
CHATTER_SLOTS = 80
GROUP_SUMMARY = "summary"
GROUP_RECENT = "recent"
GROUP_CHATTERS = "chatters"


class MacTray:
    """A status item with a fixed set of menu slots retitled in place (rumps keys items by title).

    Every row that carries a URL opens it on click: the live line opens the channel, messages open
    the chat popout, names in the chatter list open that person's channel.
    """

    def __init__(self, actions: TrayActions, *, recent_slots: int = 10) -> None:
        self._actions = actions
        self._app = rumps.App("twitchbar", title="⏳", quit_button=None)
        self._summary = [self._slot(GROUP_SUMMARY, i) for i in range(SUMMARY_SLOTS)]
        self._recent_menu = rumps.MenuItem("Recent messages")
        self._recent = [self._slot(GROUP_RECENT, i) for i in range(recent_slots)]
        for item in self._recent:
            self._recent_menu.add(item)
        self._chatters_menu = rumps.MenuItem("In chat")
        self._chatters = [self._slot(GROUP_CHATTERS, i) for i in range(CHATTER_SLOTS)]
        for item in self._chatters:
            self._chatters_menu.add(item)
        self._quiet = rumps.MenuItem("Quiet mode", callback=lambda _: actions.toggle_quiet())
        self._app.menu = [
            *self._summary,
            None,
            self._recent_menu,
            self._chatters_menu,
            None,
            rumps.MenuItem("Open channel", callback=lambda _: actions.open_channel()),
            rumps.MenuItem("Open chat popout", callback=lambda _: actions.open_chat()),
            rumps.MenuItem("Open stream manager", callback=lambda _: actions.open_dashboard()),
            None,
            self._quiet,
            None,
            rumps.MenuItem("Quit twitchbar", callback=lambda _: actions.quit()),
        ]
        self._timer: rumps.Timer | None = None
        self._view: TrayView | None = None

    def _slot(self, group: str, index: int) -> rumps.MenuItem:
        # A callback keeps the text black instead of greyed out; a click opens the row's URL if any.
        item = rumps.MenuItem(f"{group} {index}", callback=lambda _: self._click(group, index))
        item.hidden = True
        return item

    def _click(self, group: str, index: int) -> None:
        if self._view is None:
            return
        lines: tuple[MenuLine, ...] = getattr(self._view, group)
        if index < len(lines) and lines[index].url:
            self._actions.open_url(lines[index].url or "")

    def run(self, tick: Callable[[], None], interval: float) -> None:
        """Start the tick timer and enter the Cocoa run loop (blocks until quit)."""
        self._timer = rumps.Timer(lambda _: tick(), interval)
        self._timer.start()
        self._app.run()

    def render(self, view: TrayView) -> None:
        """Retitle the slots that changed."""
        previous, self._view = self._view, view
        if previous == view:
            return
        if previous is None or previous.title != view.title:
            self._app.title = view.title
        if previous is None or previous.summary != view.summary:
            self._fill(self._summary, view.summary)
        if previous is None or previous.recent != view.recent:
            self._fill(self._recent, view.recent)
            self._recent_menu.title = f"Recent messages ({len(view.recent)})"
        if previous is None or previous.chatters != view.chatters:
            self._fill(self._chatters, view.chatters)
            self._chatters_menu.title = f"In chat ({len(view.chatters)})"
        if previous is None or previous.quiet != view.quiet:
            self._quiet.state = 1 if view.quiet else 0

    @staticmethod
    def _fill(slots: Sequence[rumps.MenuItem], lines: Sequence[MenuLine]) -> None:
        for item, line in zip_longest(slots, lines[: len(slots)]):
            if line is None:
                item.hidden = True
            else:
                item.title = line.text
                item.hidden = False

    def stop(self) -> None:
        """Quit the Cocoa application."""
        rumps.quit_application()
