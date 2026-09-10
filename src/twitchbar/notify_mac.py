"""macOS banners from a plain Python process, plus the alert sound.

Notification Center only talks to processes that have a bundle identifier, which a bare Python
interpreter lacks. twitchbar gives its main bundle a stable identifier at runtime (the classic
NSBundle swizzle), which is enough for NSUserNotificationCenter; macOS then asks once, under the
interpreter's name, whether banners are allowed. The sound is played through NSSound directly, so
it is heard even before that question is answered or if banners are declined.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections import deque
from collections.abc import Callable, Sequence
from typing import Any

import objc
from AppKit import NSSound
from Foundation import NSBundle, NSObject, NSUserNotification, NSUserNotificationCenter

from twitchbar.notify import open_in_browser

log = logging.getLogger(__name__)


def _spawn(command: Sequence[str]) -> None:
    subprocess.Popen(list(command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


BUNDLE_ID = "io.github.artod.twitchbar"
URL_KEY = "url"
_bundle_patched = False


def install_bundle_identifier() -> None:
    """Give the main bundle ``BUNDLE_ID`` unless the process already runs from a real .app."""
    global _bundle_patched
    if _bundle_patched or NSBundle.mainBundle().bundleIdentifier():
        return
    original = NSBundle.instanceMethodForSelector_(b"bundleIdentifier")

    def bundle_identifier(self: Any) -> Any:
        return BUNDLE_ID if self == NSBundle.mainBundle() else original(self)

    objc.classAddMethod(
        NSBundle,
        b"bundleIdentifier",
        objc.selector(bundle_identifier, selector=original.selector, signature=original.signature),
    )
    _bundle_patched = True


class _Delegate(NSObject):  # type: ignore[misc]
    """Shows banners even while twitchbar is the active app, and opens the alert's link on click."""

    def initWithOpener_(self, opener: Callable[[str], None]) -> Any:
        """Objective-C style initializer."""
        self = objc.super(_Delegate, self).init()
        if self is not None:
            self._opener = opener
        return self

    def userNotificationCenter_shouldPresentNotification_(
        self, center: Any, notification: Any
    ) -> bool:
        """Always present, even when we are frontmost."""
        return True

    def userNotificationCenter_didActivateNotification_(
        self, center: Any, notification: Any
    ) -> None:
        """The user clicked the banner: open the page it points at."""
        info = notification.userInfo() or {}
        url = info.get(URL_KEY)
        if url:
            self._opener(str(url))


def terminal_notifier_command(binary: str, title: str, body: str, url: str | None) -> list[str]:
    """The ``terminal-notifier`` invocation for one banner (no sound: twitchbar plays its own)."""
    command = [binary, "-title", title, "-message", body, "-group", "twitchbar"]
    if url:
        command += ["-open", url]
    return command


class MacNotifier:
    """Notification Center banners with a system sound per alert; a click opens the alert's URL.

    Banners go through ``terminal-notifier`` when it is installed (``brew install
    terminal-notifier``): it is a signed application, so macOS asks for permission properly and
    lists it in System Settings. Without it, the banner is posted from this process, which recent
    macOS versions accept but often never show.
    """

    def __init__(
        self,
        opener: Callable[[str], None] = open_in_browser,
        terminal_notifier: str | None = None,
        spawn: Callable[[Sequence[str]], None] | None = None,
    ) -> None:
        self._terminal_notifier = terminal_notifier or shutil.which("terminal-notifier")
        self._spawn = spawn or _spawn
        install_bundle_identifier()
        self._center = NSUserNotificationCenter.defaultUserNotificationCenter()
        self._delegate = _Delegate.alloc().initWithOpener_(opener)
        self._center.setDelegate_(self._delegate)
        self._playing: deque[Any] = deque(maxlen=8)  # keeps NSSound objects alive while they play
        self._missing: set[str] = set()

    def notify(
        self, title: str, body: str, sound: str | None = None, url: str | None = None
    ) -> None:
        """Play ``sound`` and post the banner."""
        self.play(sound)
        if self._terminal_notifier:
            self._spawn(terminal_notifier_command(self._terminal_notifier, title, body, url))
            return
        notification = NSUserNotification.alloc().init()
        notification.setTitle_(title)
        notification.setInformativeText_(body)
        if url:
            notification.setUserInfo_({URL_KEY: url})
        self._center.deliverNotification_(notification)

    def play(self, sound: str | None) -> None:
        """Play a macOS system sound by name (Pop, Hero, Glass, ...); unknown names are skipped."""
        if not sound:
            return
        player = NSSound.soundNamed_(sound)
        if player is None:
            if sound not in self._missing:
                self._missing.add(sound)
                log.warning("unknown sound %r; see the [sounds] section of the config", sound)
            return
        self._playing.append(player)
        player.play()
