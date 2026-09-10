"""Desktop notifications behind one tiny protocol, with a backend per platform."""

from __future__ import annotations

import logging
import shutil
import subprocess
import webbrowser
from collections.abc import Callable, Sequence
from typing import Protocol

log = logging.getLogger(__name__)

Runner = Callable[[Sequence[str]], None]


def open_in_browser(url: str) -> None:
    """Open ``url`` in the default browser (a ``webbrowser.open`` with a plain signature)."""
    webbrowser.open(url)


class Notifier(Protocol):
    """Anything that can show a banner; ``sound`` names a platform sound, ``url`` opens on click."""

    def notify(
        self, title: str, body: str, sound: str | None = None, url: str | None = None
    ) -> None:
        """Show ``title``/``body`` right now without blocking the caller."""
        ...


def _spawn(command: Sequence[str]) -> None:
    subprocess.Popen(list(command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class NotifySendNotifier:
    """Linux banners via ``notify-send``; the sound name and the URL are ignored."""

    def __init__(self, runner: Runner = _spawn) -> None:
        self._run = runner

    def notify(
        self, title: str, body: str, sound: str | None = None, url: str | None = None
    ) -> None:
        """Show a desktop notification through the freedesktop notification daemon."""
        self._run(["notify-send", "--app-name=twitchbar", title, body])


class CallbackNotifier:
    """Adapter for a tray backend that ships its own notification call (pystray on Windows).

    ``beep`` is called before each banner so there is a sound even where the balloon is silent.
    """

    def __init__(
        self, show: Callable[[str, str], None], beep: Callable[[], None] | None = None
    ) -> None:
        self._show = show
        self._beep = beep

    def notify(
        self, title: str, body: str, sound: str | None = None, url: str | None = None
    ) -> None:
        """Forward to the tray's notification; the platform picks the sound."""
        if self._beep is not None and sound:
            self._beep()
        self._show(title, body)


class LogNotifier:
    """Prints alerts to the log instead of the screen (``--no-notify`` and tests)."""

    def notify(
        self, title: str, body: str, sound: str | None = None, url: str | None = None
    ) -> None:
        """Log the alert at INFO level."""
        log.info("alert: %s — %s", title, body)


def default_notifier(
    platform: str, fallback: Notifier | None = None, opener: Callable[[str], None] | None = None
) -> Notifier:
    """Pick the notifier for ``sys.platform``; ``fallback`` is used where nothing native exists."""
    if platform == "darwin":
        from twitchbar.notify_mac import MacNotifier

        return MacNotifier(opener) if opener else MacNotifier()
    if platform.startswith("linux") and shutil.which("notify-send"):
        return NotifySendNotifier()
    return fallback or LogNotifier()
