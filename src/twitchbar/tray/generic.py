"""System tray via pystray for Windows and Linux: the viewer count is drawn into the icon itself.

Experimental: written and smoke-tested on macOS, where pystray also runs; not yet verified on
Windows.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator

import pystray
from PIL import Image, ImageDraw, ImageFont

from twitchbar.tray.base import MenuLine, TrayActions, TrayView

ICON_SIZE = 64
TWITCH_PURPLE = (145, 70, 255, 255)
EMPTY_VIEW = TrayView(title="twitchbar", badge="…", summary=(), recent=(), chatters=(), quiet=False)


def draw_badge(text: str, size: int = ICON_SIZE) -> Image.Image:
    """A purple rounded square with ``text`` centred in white; the tray icon."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(image)
    canvas.rounded_rectangle((1, 1, size - 2, size - 2), radius=size // 5, fill=TWITCH_PURPLE)
    font = ImageFont.load_default(size=size * (5 if len(text) <= 2 else 3) // 8)
    left, top, right, bottom = canvas.textbbox((0, 0), text, font=font)
    x = (size - (right - left)) / 2 - left
    y = (size - (bottom - top)) / 2 - top
    canvas.text((x, y), text, font=font, fill="white")
    return image


class GenericTray:
    """A pystray icon whose menu is rebuilt from the current view each time it opens."""

    def __init__(self, actions: TrayActions) -> None:
        self._actions = actions
        self._view = EMPTY_VIEW
        self._stop = threading.Event()
        self._icon = pystray.Icon(
            "twitchbar",
            icon=draw_badge(EMPTY_VIEW.badge),
            title=EMPTY_VIEW.title,
            menu=pystray.Menu(self._items),
        )

    def _row(self, line: MenuLine) -> pystray.MenuItem:
        if line.url is None:
            return pystray.MenuItem(line.text, None, enabled=False)
        url = line.url
        return pystray.MenuItem(line.text, lambda: self._actions.open_url(url))

    def _open_chat(self) -> None:
        # The default item also runs on a plain left click of the icon (Windows): that is the
        # moment the user looked, so the unread count resets too.
        self._actions.menu_opened()
        self._actions.open_chat()

    def _items(self) -> Iterator[pystray.MenuItem]:
        view = self._view
        for line in view.summary:
            yield self._row(line)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem(
            "Recent messages", pystray.Menu(*(self._row(line) for line in view.recent))
        )
        yield pystray.MenuItem(
            f"In chat ({len(view.chatters)})",
            pystray.Menu(*(self._row(line) for line in view.chatters)),
        )
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Open channel", lambda: self._actions.open_channel())
        yield pystray.MenuItem("Open chat popout", self._open_chat, default=True)
        yield pystray.MenuItem("Open stream manager", lambda: self._actions.open_dashboard())
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem(
            "Quiet mode", lambda: self._actions.toggle_quiet(), checked=lambda _: self._view.quiet
        )
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Quit twitchbar", lambda: self._actions.quit())

    def run(self, tick: Callable[[], None], interval: float) -> None:
        """Enter pystray's loop; ``tick`` runs on pystray's setup thread every ``interval`` s."""

        def setup(icon: pystray.Icon) -> None:
            icon.visible = True
            while not self._stop.is_set():
                tick()
                self._stop.wait(interval)

        self._icon.run(setup=setup)

    def render(self, view: TrayView) -> None:
        """Redraw the icon when the badge changes and refresh the menu."""
        previous, self._view = self._view, view
        if previous == view:
            return
        if previous.badge != view.badge:
            self._icon.icon = draw_badge(view.badge)
        if previous.title != view.title:
            self._icon.title = view.title
        self._icon.update_menu()

    def notify(self, title: str, body: str) -> None:
        """Show a notification through pystray (a balloon on Windows)."""
        self._icon.notify(body, title)

    def stop(self) -> None:
        """Leave pystray's loop."""
        self._stop.set()
        self._icon.stop()
