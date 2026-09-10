"""The glue: events arrive from a source thread, the UI thread makes menu text and banners."""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from twitchbar import links
from twitchbar.config import Config
from twitchbar.events import ChatMessage, Event
from twitchbar.notify import Notifier, open_in_browser
from twitchbar.stats import SessionStats
from twitchbar.tray.base import Tray, TrayView

log = logging.getLogger(__name__)

TICK_SECONDS = 0.5


class Source(Protocol):
    """Anything that pushes events into the app from a background thread."""

    def start(self) -> None:
        """Begin producing events."""
        ...

    def stop(self) -> None:
        """Stop producing events."""
        ...


class App:
    """Owns the event queue, the session stats, the notifier and the tray."""

    def __init__(
        self,
        *,
        config: Config,
        stats: SessionStats,
        tray: Tray,
        notifier: Notifier,
        make_source: Callable[[Callable[[Event], None]], Source],
        quiet: bool = False,
        opener: Callable[[str], None] = open_in_browser,
    ) -> None:
        self._config = config
        self._stats = stats
        self._tray = tray
        self._notifier = notifier
        self._queue: queue.Queue[Event] = queue.Queue()
        self._source = make_source(self._queue.put)
        self._opener = opener
        self.quiet = quiet

    def run(self) -> None:
        """Start the source and block on the tray's main loop until quit."""
        self._source.start()
        try:
            self._tray.run(self.tick, TICK_SECONDS)
        finally:
            self._source.stop()

    def tick(self) -> None:
        """UI-thread heartbeat: drain queued events, fire alerts, refresh the menu."""
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                break
            self.handle(event)
        self._tray.render(self.view())

    def handle(self, event: Event) -> None:
        """Fold one event into the stats and show its alerts unless quiet."""
        self._log_event(event)
        for alert in self._stats.apply(event):
            if self.quiet:
                log.info("quiet, skipped %s: %s", alert.title, alert.body)
                continue
            log.info("alert %s: %s", alert.title, alert.body)
            sound = self._config.sounds.get(alert.kind) or None
            self._notifier.notify(alert.title, alert.body, sound, alert.url)

    def view(self) -> TrayView:
        """What the tray should show right now."""
        now = datetime.now(UTC)
        return TrayView(
            title=self._stats.tray_title(),
            badge=self._stats.badge(),
            summary=self._stats.summary_lines(now),
            recent=self._stats.recent_lines(),
            chatters=self._stats.chatter_lines(),
            quiet=self.quiet,
        )

    def toggle_quiet(self) -> None:
        """Flip quiet mode: the menu keeps updating, banners stop."""
        self.quiet = not self.quiet
        log.info("quiet mode %s", "on" if self.quiet else "off")
        self._tray.render(self.view())

    def open_url(self, url: str) -> None:
        """Open ``url`` in the default browser."""
        log.info("open %s", url)
        self._opener(url)

    def open_channel(self) -> None:
        """Open your channel page."""
        self.open_url(
            links.channel(self._stats.login) if self._stats.login else links.stream_manager()
        )

    def open_chat(self) -> None:
        """Open your chat as a popout window."""
        self.open_url(
            links.chat_popout(self._stats.login) if self._stats.login else links.stream_manager()
        )

    def open_dashboard(self) -> None:
        """Open the Twitch stream manager."""
        self.open_url(links.stream_manager(self._stats.login))

    def quit(self) -> None:
        """Stop the source and leave the tray's main loop."""
        self._source.stop()
        self._tray.stop()

    @staticmethod
    def _log_event(event: Event) -> None:
        if isinstance(event, ChatMessage):
            latency_ms = (datetime.now(UTC) - event.sent_at).total_seconds() * 1000
            log.info("chat %s: %s (delivered in %.0f ms)", event.user, event.text, latency_ms)
        else:
            log.info("event %s", event)
